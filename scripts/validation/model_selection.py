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
    require(root_pair == {"model": root_config.get("model"), "effort": root_config.get("model_reasoning_effort")}, "manifest Root selected_pair を actual config と一致させてください。")
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
        "fixed_pair_per_role: true",
        "dynamic_effort_allowed: false",
        "one_level_lower_comparison_required: true",
        "xhigh_requires_max_comparison: true",
        "migration_same_effort_comparison_required: true",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "focus_reviewer",
        "gpt-5.3-codex-spark",
        "official_guidance",
        "contract_fixtures",
        "estimated_cost",
        "external_data_ack_required: true",
        "approved_isolation_wrapper_sha256: []",
        "approved_isolation_profile_sha256: []",
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
        "noninferiority_margin",
        "expected_jobs",
        "secrets.token_hex",
        "continue",
    ):
        require(token in runner, f"model selection runner に `{token}` が必要です。")
    build_prompt = runner[runner.index("def _build_prompt"):runner.index("def _redact")]
    require("required_evidence" not in build_prompt, "candidate prompt に grader required_evidence を渡さないでください。")

    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp)
        provenance_root = session_dir / "provenance"
        grading_root = session_dir / "grading"
        provenance_root.mkdir()
        grading_root.mkdir()
        role = "focus_reviewer"
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
        for case_id in role_data["cases"]:
            case = cases[case_id]
            repetition_key = "safety_case_pilot_repetitions" if case["risk"] == "safety" else "normal_case_pilot_repetitions"
            for pair in module._candidate_list(role_data):
                for run_index in range(1, int(run_policy[repetition_key]) + 1):
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
                    }
                    expected_jobs.append(expected_job)
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
                    total_tokens = 50 if pair["model"] == "gpt-5.6-terra" and pair["effort"] == "high" else 100
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
        require(summary.get("efficiency_proxy_recommendation") == "gpt-5.6-terra/high", "model selection summary は eligible / noninferior pair を集計してください。")
        require(summary.get("configured_pair_matches_efficiency_proxy") is True, "model selection summary は configured pair との一致を検証してください。")
        grading_package = module._export_grading_package(session_dir, session_dir / "grader-only-export")
        require(not (grading_package / "provenance").exists(), "grader export にmodel provenanceを含めないでください。")
        require((grading_package / "grading-package.json").exists(), "grader export manifest が必要です。")
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
