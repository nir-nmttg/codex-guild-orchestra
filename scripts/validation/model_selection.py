"""GPT-5.6 role model selection eval manifest の検証。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile

from .core import ROOT, mapping, read, require, tomllib


def validate_model_selection_eval() -> None:
    script_path = ROOT / "scripts/model_selection_eval.py"
    manifest_path = ROOT / "scripts/model_selection_eval.yaml"
    require(script_path.exists(), "scripts/model_selection_eval.py が必要です。")
    require(manifest_path.exists(), "scripts/model_selection_eval.yaml が必要です。")

    spec = importlib.util.spec_from_file_location("model_selection_eval_runner", script_path)
    require(spec is not None and spec.loader is not None, "model_selection_eval.py を import できません。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        manifest = module._load_manifest(manifest_path)
        module.validate_manifest(manifest)
    except module.EvalConfigError as exc:
        require(False, f"model selection eval manifest が不正です: {exc}")

    require(tomllib is not None, "model selection 設定同期には tomllib/tomli が必要です。")
    roles = mapping(manifest.get("roles"), "model_selection.roles")
    root_pair = mapping(mapping(roles.get("root"), "model_selection.roles.root").get("selected_pair"), "model_selection.roles.root.selected_pair")
    root_config = tomllib.loads(read("template/.codex/config.toml"))
    require(root_pair.get("model") == root_config.get("model") and root_pair.get("effort") == "high", "manifest Root selected_pair はruntime pinではなくSol/high評価baselineにしてください。")
    require("model_reasoning_effort" not in root_config, "Root runtime configでreasoning effortを固定しないでください。")
    for role, value in roles.items():
        role_data = mapping(value, f"model_selection.roles.{role}")
        if role == "root":
            continue
        pair_key = "fixed_pair" if role_data.get("selection_excluded") is True else "selected_pair"
        selected = mapping(role_data.get(pair_key), f"model_selection.roles.{role}.{pair_key}")
        agent = tomllib.loads(read(f"template/.codex/agents/{role}.toml"))
        require(selected == {"model": agent.get("model"), "effort": agent.get("model_reasoning_effort")}, f"manifest {role} {pair_key} を actual agent config と一致させてください。")

    text = read("scripts/model_selection_eval.yaml")
    for token in (
        "fixed_pair_per_subagent: true",
        "dynamic_effort_allowed: false",
        "root_user_configurable_effort: true",
        "root_allowed_efforts: [high, xhigh, max]",
        "root_max_requires_explicit_user_selection: true",
        "max_in_routine_eval: false",
        "phase_one_reasoning_floor: high",
        "model_tier_comparison_roles:",
        "reasoning_comparison_roles:",
        "fixed_pair_roles:",
        "migration_same_effort_comparison_required: true",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "examiner",
        "gpt-5.3-codex-spark",
        "official_guidance",
        "prompt_caching:",
        "contract_fixtures",
        "estimated_cost",
        "cache_write_tokens",
        "external_data_ack_required: true",
        "approved_isolation_wrapper_sha256: []",
        "approved_isolation_profile_sha256: []",
        "prompt_profiles:",
        "reference_profile: full",
        "paired_same_task_repetition_required: true",
        "final_outcome_policy:",
        "required_artifact_missing",
        "required_validation_missing",
        "snapshot_mismatch",
        "scope_or_authority_violation",
        "major_finding_miss",
        "confirmatory_policy:",
    ):
        require(token in text, f"model selection eval manifest に `{token}` が必要です。")

    runner = read("scripts/model_selection_eval.py")
    for token in (
        "--acknowledge-external-data-send",
        "--execution-wrapper",
        "--isolation-attestation",
        "regression_control",
        'output_root / "grading"',
        'output_root / "provenance"',
        "git_staged_diff.patch",
        "git_commit_diff.patch",
        "untracked_manifest.json",
        "hard_gate_violations",
        "final_outcome_hard_gate_violations",
        "prompt_layer_metrics",
        "pairing_id",
        "noninferiority_margin",
        "expected_jobs",
        "secrets.token_hex",
        "continue",
    ):
        require(token in runner, f"model selection runner に `{token}` が必要です。")
    build_prompt = runner[runner.index("def _build_prompt"):runner.index("def _redact")]
    require("required_evidence" not in build_prompt, "candidate prompt に grader required_evidence を渡さないでください。")

    extracted_usage = module._extract_usage(
        json.dumps(
            {
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "total_tokens": 110,
                    "input_tokens_details": {
                        "cached_tokens": 20,
                        "cache_write_tokens": 40,
                    },
                }
            }
        )
    )
    require(
        extracted_usage.get("cached_input_tokens") == 20
        and extracted_usage.get("cache_write_tokens") == 40,
        "nested usage detailからcache read/write tokensを取得してください。",
    )
    price = {
        "input_per_million": 2.0,
        "cached_input_per_million": 0.2,
        "output_per_million": 10.0,
    }
    estimated_cost = module._estimate_usage_cost(extracted_usage, price, "validator.price")
    require(
        estimated_cost is not None and abs(estimated_cost - 0.000284) < 1e-12,
        "GPT-5.6 cache writeをuncached input rateの1.25倍でcostへ反映してください。",
    )
    missing_cache_write_usage = dict(extracted_usage)
    missing_cache_write_usage.pop("cache_write_tokens")
    require(
        module._estimate_usage_cost(missing_cache_write_usage, price, "validator.price") is None,
        "cache write usageが欠ける場合はcost推薦をfail closedにしてください。",
    )
    invalid_cache_partition_usage = dict(extracted_usage)
    invalid_cache_partition_usage["cache_write_tokens"] = 90
    require(
        module._estimate_usage_cost(invalid_cache_partition_usage, price, "validator.price") is None,
        "cache read/writeがinput tokensを超えるusageをcost計算に使わないでください。",
    )

    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp)
        provenance_root = session_dir / "provenance"
        grading_root = session_dir / "grading"
        provenance_root.mkdir()
        grading_root.mkdir()
        role = "examiner"
        seed = 56
        evaluation_manifest = json.loads(json.dumps(manifest))
        manifest_sha256 = module._manifest_sha256(manifest_path)
        wrapper_sha256 = "a" * 64
        attestation = {
            "version": 1,
            "filesystem_read_scope": "eval_workdir_only",
            "filesystem_write_scope": "eval_workdir_only",
            "environment_mode": "allowlist",
            "host_secret_mounts": False,
            "network_destination": "openai_model_service_only",
            "wrapper_sha256": wrapper_sha256,
            "runtime_image_digest": "sha256:" + "c" * 64,
            "network_policy_id": "validator-openai-only",
            "credential_profile_id": "validator-ephemeral",
            "attestation_issuer": "validator",
            "process_model": "same_process_group_no_daemonization",
            "timeout_cleanup_protocol": "cgo-detached-child-probe-v1",
        }
        attestation_sha256 = module.hashlib.sha256(
            json.dumps(attestation, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        evaluation_manifest["run_policy"]["approved_isolation_wrapper_sha256"] = [wrapper_sha256]
        evaluation_manifest["run_policy"]["approved_isolation_profile_sha256"] = [attestation_sha256]
        isolation_contract = {
            "wrapper_path": "/isolated/runtime/eval-wrapper",
            "wrapper_sha256": wrapper_sha256,
            "attestation_path": "/isolated/runtime/isolation-attestation.json",
            "attestation_sha256": attestation_sha256,
            "attestation": attestation,
        }
        expected_jobs = []
        hard_gate_keys = [str(value) for value in manifest["selection_policy"]["hard_gate_zero_tolerance"]]
        role_data = roles[role]
        cases = manifest["cases"]
        run_policy = manifest["run_policy"]
        job_number = 0
        first_grader_path: Path | None = None
        prompt_profiles = manifest["prompt_profiles"]
        final_outcome_hard_gate_keys = [
            str(value) for value in manifest["final_outcome_policy"]["hard_gate_zero_tolerance"]
        ]
        for case_id in role_data["cases"]:
            case = cases[case_id]
            repetition_key = "safety_case_pilot_repetitions" if case["risk"] == "safety" else "normal_case_pilot_repetitions"
            for pair in module._candidate_list(role_data):
                for run_index in range(1, int(run_policy[repetition_key]) + 1):
                    pairing_id = module.hashlib.sha256(
                        f"{seed}:{case_id}:{pair['model']}:{pair['effort']}:{pair['source']}:{run_index}".encode("utf-8")
                    ).hexdigest()
                    for prompt_profile in prompt_profiles:
                        job_number += 1
                        blind_label = f"blind-{job_number:032d}"
                        expected_job = {
                            "blind_label": blind_label,
                            "case_id": case_id,
                            "role": role,
                            "model": pair["model"],
                            "effort": pair["effort"],
                            "candidate_source": pair["source"],
                            "run_index": run_index,
                            "prompt_profile": prompt_profile,
                            "pairing_id": pairing_id,
                        }
                        expected_jobs.append(expected_job)
                        layer_estimated_tokens = 70 if prompt_profile == "compact" else 140
                        layer = {
                            "name": "synthetic_contract",
                            "sha256": "d" * 64,
                            "utf8_bytes": layer_estimated_tokens * 4,
                            "characters": layer_estimated_tokens * 4,
                            "estimated_tokens": layer_estimated_tokens,
                            "cache_class": "stable_contract",
                        }
                        task_layer = {
                            "name": "task_prompt",
                            "sha256": "e" * 64,
                            "utf8_bytes": 80,
                            "characters": 80,
                            "estimated_tokens": 20,
                            "cache_class": "volatile_task",
                        }
                        prompt_layer_metrics = {
                            "prompt_profile": prompt_profile,
                            "estimation_method": "ceil_unicode_characters_divided_by_4",
                            "layers": [layer, task_layer],
                            "cache_write_equivalent_estimated_tokens": layer_estimated_tokens,
                            "installed_contract_sha256": "f" * 64,
                            "volatile_task_estimated_tokens": 20,
                            "total_estimated_input_tokens": layer_estimated_tokens + 20,
                        }
                        provenance = {
                            **expected_job,
                            "manifest_sha256": manifest_sha256,
                            "case_fixture_sha256": module.hashlib.sha256(
                                json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                            ).hexdigest(),
                            "role_contract_bundle_sha256": module._role_contract_bundle_sha256(role),
                            "contract_fixtures": case["contract_fixtures"],
                            "contract_fixture_bundle_sha256": module._contract_fixture_bundle_sha256(case["contract_fixtures"]),
                            "runner_sha256": module.hashlib.sha256(script_path.read_bytes()).hexdigest(),
                            "execution_wrapper_sha256": wrapper_sha256,
                            "isolation_attestation_sha256": attestation_sha256,
                            "prompt_layer_metrics": prompt_layer_metrics,
                            "prompt_layer_metrics_sha256": module.hashlib.sha256(
                                json.dumps(
                                    prompt_layer_metrics,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ).encode("utf-8")
                            ).hexdigest(),
                        }
                        (provenance_root / f"{blind_label}.json").write_text(json.dumps(provenance), encoding="utf-8")
                        grading = grading_root / blind_label
                        grading.mkdir()
                        grader_path = grading / "grader.json"
                        grader_path.write_text(
                            json.dumps(
                                {
                                    "blind_label": blind_label,
                                    "grader_id": "validator-grader",
                                    "graded_at": "2026-07-10T00:00:00+00:00",
                                    "blindness_attestation": True,
                                    "grading_package_input_sha256": None,
                                    "hard_gate_violations": {key: False for key in hard_gate_keys},
                                    "final_outcome_hard_gate_violations": {
                                        key: False for key in final_outcome_hard_gate_keys
                                    },
                                    "required_evidence": {key: True for key in case["required_evidence"]},
                                    "quality_scores": {key: 4 for key in module.QUALITY_SCORE_KEYS},
                                    "false_positive_count": 0,
                                    "notes": [],
                                }
                            ),
                            encoding="utf-8",
                        )
                        if first_grader_path is None:
                            first_grader_path = grader_path
                        if pair["source"] == "regression_control":
                            total_tokens = 10
                        elif pair["model"] == role_data["selected_pair"]["model"] and pair["effort"] == role_data["selected_pair"]["effort"]:
                            total_tokens = 50
                        else:
                            total_tokens = 100
                        (grading / "run_metrics.json").write_text(
                            json.dumps(
                                {
                                    "blind_label": blind_label,
                                    "case_id": case_id,
                                    "role": role,
                                    "run_index": run_index,
                                    "exit_code": 0,
                                    "usage": {"total_tokens": total_tokens},
                                    "elapsed_seconds": 1.0,
                                    "automatic_hard_gate_violations": {"target_repo_escape": False},
                                    "automatic_final_outcome_hard_gate_violations": {
                                        "required_artifact_missing": False,
                                        "scope_or_authority_violation": False
                                    },
                                }
                            ),
                            encoding="utf-8",
                        )
        grading_input_sha256 = module._grading_input_bundle_sha256(grading_root)
        for grader_path in grading_root.glob("*/grader.json"):
            grader = json.loads(grader_path.read_text(encoding="utf-8"))
            grader["grading_package_input_sha256"] = grading_input_sha256
            grader_path.write_text(json.dumps(grader), encoding="utf-8")
        (session_dir / "session.json").write_text(
            json.dumps({"role": role, "seed": seed, "selection_complete_expected": True}), encoding="utf-8"
        )
        (provenance_root / "session.json").write_text(
            json.dumps(
                {
                    "role": role,
                    "seed": seed,
                    "manifest_sha256": manifest_sha256,
                    "selection_complete_expected": True,
                    "expected_jobs": expected_jobs,
                    "isolation_contract": isolation_contract,
                    "timeout_cleanup_probe": {
                        "protocol": "cgo-detached-child-probe-v1",
                        "passed": True,
                        "detached_child_marker_observed": False,
                        "elapsed_seconds": 3.5,
                    },
                }
            ),
            encoding="utf-8",
        )
        summary = module._summarize(session_dir, evaluation_manifest, manifest_path=manifest_path)
        require(summary.get("formal_recommendation_available") is False, "small synthetic pilotをformal recommendationへ昇格しないでください。")
        require(summary.get("pilot_recommendation_available") is True, "complete matrixだけがpilot recommendationを生成してください。")
        expected_recommendation = f"{role_data['selected_pair']['model']}/{role_data['selected_pair']['effort']}"
        require(summary.get("efficiency_proxy_recommendation") == expected_recommendation, "model selection summary は eligible / noninferior 5.6 candidateを集計してください。")
        compact_candidates = summary.get("model_effort_recommendations_by_prompt_profile", {}).get("compact", {}).get("candidate_pairs", [])
        require(all(not str(pair).startswith("gpt-5.5") for pair in compact_candidates), "regression controlをdeployment推薦候補へ含めないでください。")
        require(summary.get("configured_pair_matches_efficiency_proxy") is True, "model selection summary は configured pair との一致を検証してください。")
        require(summary.get("final_task_outcomes_pass") is True, "paired profileをfinal task単位でhard-gate集計してください。")
        require(
            len(summary.get("final_task_outcomes", [])) * len(prompt_profiles) == len(expected_jobs),
            "同一task/model/effort/repetitionのprofile runsを一つのfinal outcomeへ束ねてください。",
        )
        compact_comparison = mapping(
            mapping(summary.get("paired_prompt_profile_comparisons"), "summary.paired_prompt_profile_comparisons").get("compact"),
            "summary.paired_prompt_profile_comparisons.compact",
        )
        require(compact_comparison.get("all_expected_pairs_complete") is True, "full/compact paired comparisonを欠損なく集計してください。")
        require(
            compact_comparison.get("mean_prompt_layer_estimated_token_delta", 0) < 0,
            "prompt layer token近似はcompact化の差分をprofile比較として示してください。",
        )
        require(compact_comparison.get("noninferior_all_cases") is True, "paired quality deltaをcase単位の非劣性で判定してください。")
        require(
            summary.get("prompt_profile_noninferiority_recommendation") == "compact",
            "品質hard gateを維持してprompt layerを削減したprofileだけを推薦してください。",
        )
        by_profile = mapping(
            summary.get("model_effort_recommendations_by_prompt_profile"),
            "summary.model_effort_recommendations_by_prompt_profile",
        )
        require(set(by_profile) == set(prompt_profiles), "model/effort recommendationをprompt profileごとに分離してください。")
        require(
            summary.get("model_effort_reference_prompt_profile") == "compact",
            "top-level model/effort推薦はmanifest指定のreference profileだけから計算してください。",
        )
        require(
            summary.get("formal_recommendation_blockers"),
            "confirmatory条件が未完了ならformal recommendation blockerを列挙してください。",
        )
        compact_job = next(job for job in expected_jobs if job["prompt_profile"] == "compact")
        compact_grader_path = grading_root / compact_job["blind_label"] / "grader.json"
        compact_grader = json.loads(compact_grader_path.read_text(encoding="utf-8"))
        compact_grader["quality_scores"] = {key: 1 for key in module.QUALITY_SCORE_KEYS}
        compact_grader_path.write_text(json.dumps(compact_grader), encoding="utf-8")
        degraded_summary = module._summarize(session_dir, evaluation_manifest, manifest_path=manifest_path)
        require(
            degraded_summary.get("prompt_profile_noninferiority_recommendation") == "full",
            "prompt token削減があってもpaired品質非劣性を落とすprofileを推薦しないでください。",
        )
        compact_grader["quality_scores"] = {key: 4 for key in module.QUALITY_SCORE_KEYS}
        compact_grader_path.write_text(json.dumps(compact_grader), encoding="utf-8")
        compact_grader["final_outcome_hard_gate_violations"]["required_validation_missing"] = True
        compact_grader_path.write_text(json.dumps(compact_grader), encoding="utf-8")
        failed_outcome_summary = module._summarize(session_dir, evaluation_manifest, manifest_path=manifest_path)
        require(failed_outcome_summary.get("final_task_outcomes_pass") is False, "一つのprofileのvalidation欠落をfinal task hard gateへ集約してください。")
        require(
            failed_outcome_summary.get("prompt_profile_noninferiority_recommendation") == "full",
            "final outcome hard gate違反profileをprompt削減量だけで推薦しないでください。",
        )
        compact_grader["final_outcome_hard_gate_violations"]["required_validation_missing"] = False
        compact_grader_path.write_text(json.dumps(compact_grader), encoding="utf-8")
        grading_package = module._export_grading_package(session_dir, session_dir / "grader-only-export")
        require(not (grading_package / "provenance").exists(), "grader export にmodel provenanceを含めないでください。")
        require((grading_package / "grading-package.json").exists(), "grader export manifest が必要です。")
        exported_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in grading_package.rglob("*")
            if path.is_file()
        )
        require("prompt_profile" not in exported_text and "pairing_id" not in exported_text, "graderへprompt profile provenanceを公開しないでください。")
        require(first_grader_path is not None, "model selection test grader が必要です。")
        incomplete_grader = json.loads(first_grader_path.read_text(encoding="utf-8"))
        incomplete_grader["hard_gate_violations"].pop(hard_gate_keys[0])
        first_grader_path.write_text(json.dumps(incomplete_grader), encoding="utf-8")
        try:
            module._summarize(session_dir, evaluation_manifest, manifest_path=manifest_path)
        except module.EvalConfigError:
            pass
        else:
            require(False, "grading field 欠損を pilot recommendation として受理しないでください。")

    with tempfile.TemporaryDirectory() as tmp:
        test_root = Path(tmp)
        unsafe_manifest = json.loads(json.dumps(manifest))
        unsafe_manifest["cases"]["bounded_focus_regression"]["baseline_files"] = {".env": "API_TOKEN=unsafe"}
        try:
            module.validate_manifest(unsafe_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "secret-like fixture path/contentをmanifest validationで拒否してください。")
        unsafe_content_manifest = json.loads(json.dumps(manifest))
        unsafe_content_manifest["cases"]["bounded_focus_regression"]["baseline_files"] = {
            "notes.txt": "SERVICE_API_TOKEN=unsafe-value"
        }
        try:
            module.validate_manifest(unsafe_content_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "safe-looking path内のsecret-like fixture contentも拒否してください。")
        unsafe_pii_manifest = json.loads(json.dumps(manifest))
        unsafe_pii_manifest["cases"]["bounded_focus_regression"]["baseline_files"] = {
            "customer_export.csv": "Alice Example,555-12-3456,090-1234-5678"
        }
        try:
            module.validate_manifest(unsafe_pii_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "PII-like fixture path/contentをmanifest validationで拒否してください。")

        missing_major_gate_manifest = json.loads(json.dumps(manifest))
        missing_major_gate_manifest["selection_policy"]["hard_gate_zero_tolerance"].remove("major_finding_miss")
        try:
            module.validate_manifest(missing_major_gate_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "major finding missを欠くselection hard gate集合を拒否してください。")

        duplicate_hard_gate_manifest = json.loads(json.dumps(manifest))
        duplicate_hard_gate_manifest["selection_policy"]["hard_gate_zero_tolerance"].append("major_finding_miss")
        try:
            module.validate_manifest(duplicate_hard_gate_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "重複したselection hard gate集合を拒否してください。")

        invalid_hard_gate_type_manifest = json.loads(json.dumps(manifest))
        invalid_hard_gate_type_manifest["selection_policy"]["hard_gate_zero_tolerance"].append({"invalid": True})
        try:
            module.validate_manifest(invalid_hard_gate_type_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "文字列以外を含むselection hard gate集合をEvalConfigErrorで拒否してください。")

        duplicate_root_effort_manifest = json.loads(json.dumps(manifest))
        duplicate_root_effort_manifest["selection_policy"]["root_allowed_efforts"].append("max")
        try:
            module.validate_manifest(duplicate_root_effort_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "重複したRoot allowed effort集合を拒否してください。")

        invalid_root_effort_type_manifest = json.loads(json.dumps(manifest))
        invalid_root_effort_type_manifest["selection_policy"]["root_allowed_efforts"].append({"invalid": True})
        try:
            module.validate_manifest(invalid_root_effort_type_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "文字列以外を含むRoot allowed effort集合をEvalConfigErrorで拒否してください。")

        root_max_routine_manifest = json.loads(json.dumps(manifest))
        root_max_routine_manifest["roles"]["root"]["candidates"].append(
            {"model": "gpt-5.6-sol", "effort": "max"}
        )
        try:
            module.validate_manifest(root_max_routine_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "Root maxをroutine eval matrixへ含めないでください。")

        sage_medium_manifest = json.loads(json.dumps(manifest))
        sage_medium_manifest["roles"]["sage"]["candidates"][0]["effort"] = "medium"
        try:
            module.validate_manifest(sage_medium_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "Sageのphase one候補をhigh未満へ下げないでください。")

        premature_guildmaster_high_manifest = json.loads(json.dumps(manifest))
        premature_guildmaster_high_manifest["roles"]["guildmaster"]["selected_pair"]["effort"] = "high"
        try:
            module.validate_manifest(premature_guildmaster_high_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "測定前にGuildmasterをhighへ固定しないでください。")

        premature_inquisitor_xhigh_manifest = json.loads(json.dumps(manifest))
        premature_inquisitor_xhigh_manifest["roles"]["inquisitor"]["selected_pair"]["effort"] = "xhigh"
        try:
            module.validate_manifest(premature_inquisitor_xhigh_manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "測定前にInquisitorをxhighへ固定しないでください。")

        prepared_root = test_root / "prepared"
        guild_root, _ = module._prepare_guild(manifest["cases"]["bounded_focus_regression"], prepared_root)
        require(not (guild_root / ".agents/orchestra/scripts").exists(), "eval guild はrole contract allowlist以外をcopyしないでください。")

        tree_root = test_root / "tree"
        target_repo = tree_root / "repositories/eval-repo"
        target_repo.mkdir(parents=True)
        (tree_root / "AGENTS.md").write_text("before\n", encoding="utf-8")
        before_tree = module._tree_manifest(tree_root, excluded_relative_root="repositories/eval-repo")
        (tree_root / "AGENTS.md").write_text("after\n", encoding="utf-8")
        changes = module._tree_changes(before_tree, module._tree_manifest(tree_root, excluded_relative_root="repositories/eval-repo"))
        require([value["path"] for value in changes] == ["AGENTS.md"], "target repo外変更をautomatic hard gate用に検出してください。")

        git_repo = test_root / "git-hardening"
        git_repo.mkdir()
        module._run_checked(["git", "init", "--quiet"], git_repo)
        module._run_checked(["git", "config", "user.name", "Eval Validator"], git_repo)
        module._run_checked(["git", "config", "user.email", "validator@example.invalid"], git_repo)
        (git_repo / ".gitattributes").write_text("owned.txt diff=unsafe\n", encoding="utf-8")
        (git_repo / "owned.txt").write_text("before\n", encoding="utf-8")
        module._run_checked(["git", "add", "--all"], git_repo)
        module._run_checked(["git", "commit", "--quiet", "-m", "baseline"], git_repo)
        marker = test_root / "git-command-executed"
        malicious = test_root / "malicious-git-command"
        malicious.write_text(
            f"#!/bin/sh\n: > {module.shlex.quote(str(marker))}\n",
            encoding="utf-8",
        )
        malicious.chmod(0o700)
        module._run_checked(["git", "config", "diff.unsafe.textconv", str(malicious)], git_repo)
        module._run_checked(["git", "config", "core.fsmonitor", str(malicious)], git_repo)
        (git_repo / "owned.txt").write_text("after\n", encoding="utf-8")
        diff_output = module._run_checked(["git", "diff", "--binary"], git_repo)
        require("owned.txt" in diff_output and not marker.exists(), "eval Git evidence captureでtextconv/fsmonitorを実行しないでください。")
        outside_env_objects = test_root / "eval-environment-object-store"
        outside_env_objects.mkdir()
        injected_git_environment = {
            "PATH": module.os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_OBJECT_DIRECTORY": str(outside_env_objects),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(outside_env_objects),
            "GIT_EXTERNAL_DIFF": str(malicious),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.fsmonitor",
            "GIT_CONFIG_VALUE_0": str(malicious),
        }
        injected_env_diff = module._run_checked(
            ["git", "diff", "--binary"],
            git_repo,
            env=injected_git_environment,
        )
        require("owned.txt" in injected_env_diff and not marker.exists(), "eval Git postprocessはhost Git environment注入を無視してください。")
        outside_objects = test_root / "eval-outside-object-store"
        (git_repo / ".git/objects").rename(outside_objects)
        (git_repo / ".git/objects").symlink_to(outside_objects, target_is_directory=True)
        try:
            module._assert_safe_eval_git_metadata(git_repo)
        except module.EvalConfigError:
            pass
        else:
            require(False, "eval Git metadataのexternal object store symlinkを拒否してください。")
        (git_repo / ".git/objects").unlink()
        outside_objects.rename(git_repo / ".git/objects")
        with (git_repo / ".git/config").open("a", encoding="utf-8") as stream:
            stream.write("\n[include]\n\tpath = /tmp/untrusted-eval-config\n")
        try:
            module._assert_safe_eval_git_metadata(git_repo)
        except module.EvalConfigError:
            pass
        else:
            require(False, "eval Git metadataのinclude indirectionを拒否してください。")

        timeout_child_marker = test_root / "timeout-child-survived"
        try:
            module._run_checked(
                [
                    "/bin/sh",
                    "-c",
                    f"(/bin/sleep 2; : > {module.shlex.quote(str(timeout_child_marker))}) & wait",
                ],
                test_root,
                timeout_seconds=1,
            )
        except module.EvalConfigError:
            pass
        else:
            require(False, "eval postprocess command timeoutをfail closedにしてください。")
        module.time.sleep(2.2)
        require(not timeout_child_marker.exists(), "timeout後にwrapper descendantを生存させないでください。")

        detached_wrapper = test_root / "detached-wrapper"
        detached_wrapper.write_text(
            f"#!{module.sys.executable}\n"
            "import os,sys,time\n"
            "if os.fork()==0:\n"
            " os.setsid();time.sleep(2);open(sys.argv[2],'w').close();os._exit(0)\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )
        detached_wrapper.chmod(0o700)
        detached_contract = {
            "wrapper_path": str(detached_wrapper),
            "wrapper_sha256": module.hashlib.sha256(detached_wrapper.read_bytes()).hexdigest(),
        }
        try:
            module._verify_wrapper_timeout_cleanup(detached_contract)
        except module.EvalConfigError:
            pass
        else:
            require(False, "detached childが残るwrapperをtimeout cleanup probeで拒否してください。")

        pass_through = test_root / "pass-through-wrapper"
        pass_through.write_text("#!/bin/sh\nexec \"$@\"\n", encoding="utf-8")
        pass_through.chmod(0o700)
        pass_through_sha = module.hashlib.sha256(pass_through.read_bytes()).hexdigest()
        attestation = {
            "version": 1,
            "filesystem_read_scope": "eval_workdir_only",
            "filesystem_write_scope": "eval_workdir_only",
            "environment_mode": "allowlist",
            "host_secret_mounts": False,
            "network_destination": "openai_model_service_only",
            "wrapper_sha256": pass_through_sha,
            "runtime_image_digest": "sha256:" + "d" * 64,
            "network_policy_id": "self-asserted",
            "credential_profile_id": "self-asserted",
            "attestation_issuer": "self",
            "process_model": "same_process_group_no_daemonization",
            "timeout_cleanup_protocol": "cgo-detached-child-probe-v1",
        }
        attestation_path = test_root / "self-attestation.json"
        attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
        live_args = module.argparse.Namespace(
            acknowledge_external_data_send=True,
            execution_wrapper=pass_through,
            isolation_attestation=attestation_path,
        )
        try:
            module._run(live_args, manifest_path, manifest)
        except module.EvalConfigError:
            pass
        else:
            require(False, "self-attested pass-through wrapperをreview済みallowlistなしで起動しないでください。")
