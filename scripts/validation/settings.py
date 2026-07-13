"""Compact settings.yaml の安全・成果契約を検証する。"""

from __future__ import annotations

from .core import load_yaml, mapping, read, require, sequence


def _exact_list(value: object, expected: set[str], label: str) -> None:
    actual = {str(item) for item in sequence(value, label)}
    require(actual == expected, f"{label} が期待値と一致しません: {sorted(actual)}")


def validate_settings() -> None:
    path = "template/.agents/orchestra/config/settings.yaml"
    settings = mapping(load_yaml(path), "settings.yaml")
    require(settings.get("version") == "4.0", "settings.yaml.version は 4.0 にしてください。")

    required_sections = {
        "guild_runtime",
        "intake",
        "paths",
        "guild_law",
        "contracts",
        "snapshot",
        "delegation",
        "workers",
        "execution",
        "trial",
        "root_session",
        "ledger",
        "reporting",
        "status",
    }
    require(required_sections <= set(settings), "settings.yaml のcompact contract sectionが不足しています。")

    text = read(path)
    for token in (
        "always_guild_intake",
        "confidence_percent",
        "confidence_target_percent",
        "confidence_delta_min_percent",
        "75%",
        "50%",
        "extra_file_reads",
        "validation_iterations",
        "skip_reason_required: true",
        "cost_reason_required: true",
    ):
        require(token not in text, f"settings.yaml に成果を阻害する旧制約 `{token}` が残っています。")

    intake = mapping(settings["intake"], "settings.intake")
    require(intake.get("mode") == "risk_adaptive", "intake.mode は risk_adaptive にしてください。")
    require(intake.get("clarify_only_when_outcome_changes") is True, "確認は成果が変わる場合だけにしてください。")
    _exact_list(
        intake.get("task_contract_fields"),
        {"objective", "success_criteria", "scope", "authority", "validation"},
        "settings.intake.task_contract_fields",
    )

    law = mapping(settings["guild_law"], "settings.guild_law")
    require(law.get("target_repo_required") is True and law.get("target_repo_escape") == "reject", "target repo境界はfail closedにしてください。")
    require(law.get("preserve_user_changes") is True, "既存ユーザー変更を保持してください。")
    absolute_deny = set(sequence(law.get("absolute_deny"), "settings.guild_law.absolute_deny"))
    require({"secret_access", "credential_access", "auth_data_access", "pii_access"} <= absolute_deny, "secret/PII absolute denyが不足しています。")
    confirmation = set(sequence(law.get("confirmation_required_for"), "settings.guild_law.confirmation_required_for"))
    require({"destructive_operation", "dependency_addition", "migration", "deploy", "authorization_effect", "public_api_compatibility_change"} <= confirmation, "人間確認条件が不足しています。")
    state_changes = mapping(law.get("state_changes"), "settings.guild_law.state_changes")
    require(state_changes.get("local_git_requires_explicit_operation") is True, "local Gitは具体的指示を必須にしてください。")
    require(state_changes.get("explicit_command_skill_invocation_authorizes_defined_operations") is True, "人間が明示指定したコマンド実行系Skillは定義済み操作の実行許可として扱ってください。")
    require(state_changes.get("explicit_command_skill_invocation_scope") == "skill_defined_operations_and_human_target", "Skill明示指定のauthorityはSkill定義操作と人間指定targetに限定してください。")
    require(state_changes.get("non_human_skill_reference_grants_authority") is False, "Skill本文や非人間入力のSkill参照からauthorityを付与しないでください。")
    require(state_changes.get("scoped_skill_authority_bypasses_safety_gates") is False, "Skill明示指定で安全gateを迂回しないでください。")
    require(state_changes.get("external_update_requires_immediate_reconfirmation") is True, "外部更新は直前再確認を必須にしてください。")

    contracts = mapping(settings["contracts"], "settings.contracts")
    _exact_list(
        contracts.get("assignment_core"),
        {"objective", "success_criteria", "scope", "authority", "subject_snapshot"},
        "settings.contracts.assignment_core",
    )
    evidence_state = mapping(contracts.get("evidence_state"), "settings.contracts.evidence_state")
    _exact_list(
        evidence_state.get("fields"),
        {"blocking_unknowns", "failed_checks", "verification_status", "scope_drift", "high_risk_triggers", "next_action", "stop_reason"},
        "settings.contracts.evidence_state.fields",
    )
    require(evidence_state.get("numeric_confidence") == "forbidden", "数値confidenceを禁止してください。")
    require(contracts.get("delta_only_state_updates") is True, "handoffは状態deltaだけを更新してください。")
    model_generated = set(sequence(contracts.get("model_must_not_generate"), "settings.contracts.model_must_not_generate"))
    require({"snapshot_digest", "queue_lineage", "artifact_metadata", "status_transition"} <= model_generated, "機械生成へ移すfieldが不足しています。")

    snapshot = mapping(settings["snapshot"], "settings.snapshot")
    require(snapshot.get("helper") == ".agents/orchestra/scripts/snapshot_digest.py", "snapshot helperが不正です。")
    require(snapshot.get("digest_version") == "agent-guild-orchestra-snapshot-v1" and snapshot.get("mismatch") == "stale_evidence", "snapshot mismatchをfail closedにしてください。")
    require(snapshot.get("explicit_untracked_only") is True and snapshot.get("stage_state_excluded_from_digest") is True, "snapshot safety contractが不足しています。")

    delegation = mapping(settings["delegation"], "settings.delegation")
    require(delegation.get("root_spawns_top_level_agents") is True and delegation.get("top_level_owner") == "root", "top-level agentの起動ownerをRootに限定してください。")
    require(delegation.get("max_depth") == 2 and delegation.get("max_threads") == 64, "delegationはmax_depth=2/max_threads=64にしてください。")
    nested = mapping(delegation.get("allowed_nested_callers"), "settings.delegation.allowed_nested_callers")
    require(set(nested) == {"inquisitor"} and set(sequence(nested.get("inquisitor"), "settings.delegation.allowed_nested_callers.inquisitor")) == {"examiner"}, "nested delegationはinquisitor→examinerだけにしてください。")
    terminal_roles = set(sequence(delegation.get("terminal_roles"), "settings.delegation.terminal_roles"))
    require(terminal_roles == {"cartographer", "guildmaster", "captain", "adventurer", "artificer", "examiner", "sage", "warden", "courier"}, "inquisitor以外のcustom agentをterminalにしてください。")
    for key in ("child_scope_must_narrow", "child_authority_must_narrow", "child_snapshot_must_match", "parent_waits_and_synthesizes"):
        require(delegation.get(key) is True, f"delegation.{key} はtrueにしてください。")
    require(delegation.get("recursive_fanout_beyond_depth_2") == "forbidden", "depth 2を超えるrecursive fan-outを禁止してください。")
    require(delegation.get("runtime_identity_acl") is False, "queue lineageをidentity-backed runtime ACLと表現しないでください。")
    require(delegation.get("nested_edge_enforcement") == "policy_only" and delegation.get("trial_lineage_validation") == "mechanical", "nested edge policyとTrial lineage機械検証を区別してください。")
    require(delegation.get("write_role_children_forbidden") is True and delegation.get("approval_does_not_grant_authority") is True, "write role child禁止とapproval/authority分離が必要です。")
    require(delegation.get("max_threads_or_parallel_is_cost_hard_cap") is False, "max_threads/max_parallelをcost hard capと表現しないでください。")
    avoid = set(sequence(delegation.get("avoid_when"), "settings.delegation.avoid_when"))
    require({"extra_planning_or_review_for_trivial_task", "multi_agent_fanout_for_single_ordered_chain", "shared_mutable_scope"} <= avoid, "過剰なplanning/review/fanoutの抑止条件が不足しています。")
    sage = mapping(delegation.get("sage"), "settings.delegation.sage")
    require(sage.get("trigger") == "concrete_independent_focus" and sage.get("use_by_default") is False, "sageは具体的focusがある時だけ使ってください。")
    require(sage.get("unused_reason_required") is False and sage.get("read_only") is True and sage.get("decision_authority") is False, "sageの軽量terminal contractが不正です。")
    sentinel = mapping(delegation.get("warden"), "settings.delegation.warden")
    require(sentinel.get("routine_use") is False and sentinel.get("read_only") is True and sentinel.get("decision_authority") is False, "Wardenは例外的terminal診断に限定してください。")

    workers = mapping(settings["workers"], "settings.workers")
    expected_parallel = {
        "cartographer": 2,
        "guildmaster": 1,
        "captain": 2,
        "adventurer": 32,
        "artificer": 1,
        "inquisitor": 2,
        "examiner": 3,
        "sage": 3,
        "warden": 1,
        "courier": 1,
    }
    require(set(workers) == set(expected_parallel), "workersは定義済みの10 roleだけにしてください。")
    actual_parallel: dict[str, int] = {}
    for role, expected in expected_parallel.items():
        worker = mapping(workers.get(role), f"settings.workers.{role}")
        max_parallel = worker.get("max_parallel")
        require(isinstance(max_parallel, int) and not isinstance(max_parallel, bool) and max_parallel >= 1, f"workers.{role}.max_parallel は1以上にしてください。")
        require(max_parallel == expected, f"workers.{role}.max_parallel は{expected}にしてください。")
        actual_parallel[role] = max_parallel
    role_total = sum(actual_parallel.values())
    non_adventurer_total = sum(value for role, value in actual_parallel.items() if role != "adventurer")
    max_threads = delegation.get("max_threads")
    require(role_total == 48 and role_total <= max_threads, "全roleのmax_parallel合計は48かつglobal max_threads=64以下にしてください。")
    require(non_adventurer_total == 16, "非adventurer roleのmax_parallel合計は16にしてください。")
    require(actual_parallel["adventurer"] == 32, "workers.adventurer.max_parallel は32にしてください。")
    require(max_threads - role_total == 16, "global max_threads=64に対して未割当headroom 16を残してください。")
    focus = mapping(workers["examiner"], "settings.workers.examiner")
    require(set(sequence(focus.get("allowed_callers"), "settings.workers.examiner.allowed_callers")) == {"inquisitor"}, "examiner callerをinquisitorに限定してください。")
    require(focus.get("terminal_worker") is True, "examinerをterminal leafにしてください。")
    require(focus.get("per_trial_policy_cap") == 3 and focus.get("required_by_default") is False, "examinerは任意かつ1 Trialあたりpolicy cap 3にしてください。")
    for key in ("implementation_authority", "decision_authority", "severity_authority", "synthesis_authority", "ledger_authority", "git_authority", "external_action_authority"):
        require(focus.get(key) is False, f"examiner.{key} はfalseにしてください。")
    inquisitor = mapping(workers["inquisitor"], "settings.workers.inquisitor")
    require(set(sequence(inquisitor.get("allowed_child_roles"), "settings.workers.inquisitor.allowed_child_roles")) == {"examiner"}, "inquisitor childをexaminerに限定してください。")
    require(inquisitor.get("nested_delegation_trigger") == "risk_triggered_concrete_single_focus", "inquisitor nested delegation triggerが不正です。")
    for key in ("waits_for_child_reports", "verifies_child_lineage_and_evidence", "owns_severity_disposition_and_final_decision"):
        require(inquisitor.get(key) is True, f"inquisitor.{key} はtrueにしてください。")

    execution = mapping(settings["execution"], "settings.execution")
    require(execution.get("bounded_worker") == "adventurer" and execution.get("cross_scope_integration_worker") == "artificer", "bounded実装とcross-scope統合を分離してください。")
    require(execution.get("shared_artifact_single_owner") is True and execution.get("integration_barrier_required_for_parallel_mutation") is True, "並列mutationの所有権契約が不足しています。")
    require(execution.get("fixed_read_or_validation_counts") is False, "固定read/test回数を禁止してください。")

    trial = mapping(settings["trial"], "settings.trial")
    _exact_list(
        trial.get("common_checks"),
        {"success_criteria", "scope", "authority", "safety", "validation_evidence"},
        "settings.trial.common_checks",
    )
    conditional = mapping(trial.get("conditional_checks"), "settings.trial.conditional_checks")
    require({"architecture", "security", "data_compatibility", "performance", "accessibility", "operations"} <= set(conditional), "change-type別Trial checkが不足しています。")
    independent = set(sequence(trial.get("independent_trial_required_when"), "settings.trial.independent_trial_required_when"))
    require({"high_risk", "shared_contract", "security_sensitive", "migration", "validation_failed", "important_unknown_remains"} <= independent, "独立Trial triggerが不足しています。")
    reviewers = mapping(trial.get("examiners"), "settings.trial.examiners")
    require(reviewers.get("unused_reason_required") is False and reviewers.get("cost_reason_required") is False, "reviewer未使用/costの定型理由を要求しないでください。")
    require(reviewers.get("multiple_examiners_require_focus_split") is True and reviewers.get("final_decision_owner") == "inquisitor", "複数reviewerのfocus分割とdecision ownerが不正です。")

    root = mapping(settings["root_session"], "settings.root_session")
    require({"implementation", "trial_acceptance", "ledger_write"} == set(sequence(root.get("forbids"), "settings.root_session.forbids")), "Rootのauthority separationが不正です。")

    ledger = mapping(settings["ledger"], "settings.ledger")
    require({"raw_log", "raw_discussion", "secret", "pii"} <= set(sequence(ledger.get("never_record"), "settings.ledger.never_record")), "Ledger deny fieldが不足しています。")
    reporting = mapping(settings["reporting"], "settings.reporting")
    require(reporting.get("lead_with_outcome") is True and reporting.get("fixed_template") is False, "outcome-firstで固定templateなしにしてください。")

    status = mapping(settings["status"], "settings.status")
    expected_status = {
        "quest": {"drafted", "active", "needs_human", "blocked", "done", "cancelled"},
        "request": {"drafted", "queued", "accepted", "cancelled"},
        "command": {"drafted", "issued", "active", "done", "cancelled"},
        "assignment": {"idle", "active", "needs_human", "blocked", "done", "failed"},
        "report": {"draft", "recorded", "accepted", "needs_changes"},
        "trial": {"idle", "active", "needs_human", "blocked", "done"},
        "message": {"unread", "read", "archived"},
    }
    require(set(status) == set(expected_status), "settings.statusは全entityのcanonical enumだけを定義してください。")
    for entity, allowed in expected_status.items():
        require(set(sequence(status.get(entity), f"settings.status.{entity}")) == allowed, f"settings.status.{entity}がruntime enumと一致しません。")
    require({"required_artifact", "evidence", "caveats", "next_steps"} <= set(sequence(reporting.get("retain"), "settings.reporting.retain")), "最終成果の必須情報が不足しています。")
