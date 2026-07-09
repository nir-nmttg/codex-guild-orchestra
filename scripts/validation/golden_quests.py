"""golden Quest fixture の静的検証。"""

from __future__ import annotations

from .core import ROOT, load_yaml, mapping, require, sequence


GOLDEN_ROOT = "scripts/validation/fixtures/golden_quests"
EXPECTED_FIXTURES = {
    "advisor_dialogue_same_focus_stop.yaml",
    "advisor_owner_synthesis.yaml",
    "claude_helper_only_disposition.yaml",
    "courier_explicit_git_postcondition.yaml",
    "focus_reviewer_bounded_contract.yaml",
    "focused_trial_reviewer_budget.yaml",
    "focused_trial_revision_bound_input.yaml",
    "guild_quest_routing.yaml",
    "ledger_injection_negative.yaml",
    "mapmaking_readonly_no_edit.yaml",
    "party_integration_barrier_stable_revision.yaml",
    "quest_awareness_confidence_below_50_stop.yaml",
    "quest_awareness_confidence_below_75.yaml",
    "quest_awareness_contradictory_evidence.yaml",
    "quest_awareness_failed_check_first_failure.yaml",
    "quest_awareness_memory_prevention_artifact.yaml",
    "quest_awareness_scope_drift.yaml",
    "quest_awareness_security_sensitive.yaml",
    "quest_sentinel_calibration.yaml",
    "safety_approval_scope_absolute_deny.yaml",
    "safety_gate_needs_human.yaml",
    "solo_small_fix_no_git.yaml",
}


def _fixture(rel_name: str) -> dict[str, object]:
    return mapping(load_yaml(f"{GOLDEN_ROOT}/{rel_name}"), rel_name)


def _authority(value: object, label: str) -> dict[str, object]:
    authority = mapping(value, label)
    require(set(authority) == {"read", "edit", "validate", "local_git", "external_actions"}, f"{label} は authority 5項目を持つ必要があります。")
    for key, item in authority.items():
        require(isinstance(item, bool), f"{label}.{key} は bool にしてください。")
    return authority


def _forbidden(value: object, label: str) -> dict[str, object]:
    forbidden = mapping(value, label)
    require(forbidden, f"{label} は空にできません。")
    for key, item in forbidden.items():
        require(item is True, f"{label}.{key} は true にしてください。")
    return forbidden


def _required_next_action(value: object, label: str) -> str:
    require(isinstance(value, str) and value, f"{label} は空でない文字列にしてください。")
    return value


def _base_fixture(doc: dict[str, object], rel_name: str) -> dict[str, object]:
    require(doc.get("id") == rel_name.removesuffix(".yaml"), f"{rel_name}.id は filename と一致させてください。")
    require(doc.get("fixture_mode") == "static_contract_example", f"{rel_name}.fixture_mode は static_contract_example にしてください。")
    require(isinstance(doc.get("summary"), str) and doc["summary"], f"{rel_name}.summary が必要です。")
    require("input" in doc and "expected" in doc, f"{rel_name} は input / expected が必要です。")
    return mapping(doc["expected"], f"{rel_name}.expected")


def validate_golden_quests() -> None:
    root = ROOT / GOLDEN_ROOT
    require(root.exists(), "golden Quest fixture directory が必要です。")
    actual = {path.name for path in root.glob("*.yaml")}
    require(actual == EXPECTED_FIXTURES, "golden Quest fixture 一覧が期待値と一致しません: " + ", ".join(sorted(actual)))

    mapmaking = _base_fixture(_fixture("mapmaking_readonly_no_edit.yaml"), "mapmaking_readonly_no_edit.yaml")
    require(mapmaking.get("rank") == "mapmaking", "mapmaking fixture は rank=mapmaking にしてください。")
    require(mapmaking.get("assignment_kind") == "mapmaking", "mapmaking fixture は assignment_kind=mapmaking にしてください。")
    require(mapmaking.get("worker_id") == "cartographer", "mapmaking fixture は cartographer にしてください。")
    mapmaking_authority = _authority(mapmaking.get("authority"), "mapmaking.expected.authority")
    require(mapmaking_authority == {"read": True, "edit": False, "validate": False, "local_git": False, "external_actions": False}, "mapmaking fixture は read-only にしてください。")
    advisor = mapping(mapmaking.get("advisor"), "mapmaking.expected.advisor")
    require(advisor.get("considered") is True and advisor.get("decision_authority") is False, "mapmaking fixture は advisor 検討と decision_authority=false を要求してください。")
    _forbidden(mapmaking.get("forbidden"), "mapmaking.expected.forbidden")

    solo = _base_fixture(_fixture("solo_small_fix_no_git.yaml"), "solo_small_fix_no_git.yaml")
    require(solo.get("rank") == "solo_quest" and solo.get("worker_id") == "adventurer", "solo fixture は solo_quest / adventurer にしてください。")
    solo_authority = _authority(solo.get("authority"), "solo.expected.authority")
    require(solo_authority["edit"] is True and solo_authority["validate"] is True, "solo fixture は edit / validate を許可してください。")
    require(solo_authority["local_git"] is False and solo_authority["external_actions"] is False, "solo fixture は local git / external action を禁止してください。")
    solo_handoff = mapping(solo.get("handoff_sufficiency"), "solo.expected.handoff_sufficiency")
    solo_required = set(sequence(solo_handoff.get("owner_to_trial_ready_requires"), "solo.expected.handoff_sufficiency.owner_to_trial_ready_requires"))
    require({"changed_files", "decisions_made", "intent_alignment", "quest_awareness", "control_decision", "validation_evidence", "research_evidence", "risks", "base_snapshot", "result_snapshot"} <= solo_required, "solo fixture は owner_to_trial の required evidence を要求してください。")
    self_check = mapping(solo.get("self_check"), "solo.expected.self_check")
    require(self_check.get("owner_validation_attestation") is True and self_check.get("owner_accept_authority") is False and self_check.get("root_quality_decision_authority") is False, "solo self_check は owner attestation と decision authority を分離してください。")
    require(self_check.get("independent_trial_may_be_skipped_only_if_all_gates_pass") is True and self_check.get("escalation_depth") == "peer_review", "solo self_check は全gate成立時だけ省略し、不成立ならpeer_reviewへ上げてください。")
    require({"single_owned_scope", "low_uncertainty", "low_coupling", "bounded_blast_radius", "no_safety_item", "no_confirmation_needed", "no_public_api_or_data_compatibility_change", "no_scope_drift", "no_blocking_unknown", "targeted_validation_passed", "success_criteria_directly_evidenced", "snapshot_matched"} == set(sequence(self_check.get("required_gates"), "solo.expected.self_check.required_gates")), "solo self_check gate が不足しています。")
    report_required = mapping(solo.get("report_required"), "solo.expected.report_required")
    require(report_required.get("intent_alignment") is True and report_required.get("validation_evidence") is True and report_required.get("research_evidence") is True and report_required.get("risks") is True, "solo fixture は intent_alignment / validation_evidence / research_evidence / risks を要求してください。")
    solo_forbidden = _forbidden(solo.get("forbidden"), "solo.expected.forbidden")
    require({"owner_accept_decision", "root_quality_accept_decision"} <= set(solo_forbidden), "solo self_check は owner / Root の品質acceptを禁止してください。")

    party_doc = _fixture("party_integration_barrier_stable_revision.yaml")
    party_input = mapping(party_doc.get("input"), "party_integration.expected.input")
    party = _base_fixture(party_doc, "party_integration_barrier_stable_revision.yaml")
    require(party.get("rank") == "party_quest", "party integration fixture は party_quest にしてください。")
    integration_barrier = mapping(party.get("integration_barrier"), "party_integration.expected.integration_barrier")
    require(integration_barrier.get("required") is True and integration_barrier.get("all_required_reports_complete") is True, "party integration fixture は required report 完了 barrier を要求してください。")
    require(integration_barrier.get("single_integration_owner_required") is True and integration_barrier.get("integration_before_barrier_allowed") is False, "party integration fixture は単一 integration owner と barrier 前 integration 禁止を要求してください。")
    require(integration_barrier.get("integration_owner") == party_input.get("integration_owner"), "party integration fixture は明示した adventurer integration owner に固定してください。")
    required_assignment_ids = sequence(party_input.get("required_assignment_ids"), "party_integration.input.required_assignment_ids")
    require(sequence(integration_barrier.get("required_assignment_ids"), "party_integration.expected.integration_barrier.required_assignment_ids") == required_assignment_ids, "party integration fixture は全 required assignment を barrier に固定してください。")
    require(sequence(integration_barrier.get("required_report_ids"), "party_integration.expected.integration_barrier.required_report_ids") == sequence(party_input.get("completed_report_ids"), "party_integration.input.completed_report_ids"), "party integration fixture は全 required report を barrier に固定してください。")
    stable_revision = mapping(party.get("stable_snapshot"), "party_integration.expected.stable_snapshot")
    require(stable_revision.get("required") is True and stable_revision.get("source") == "integrated_commit", "party integration fixture は integrated commit の stable snapshot を要求してください。")
    require(stable_revision.get("revision_id") == party_input.get("final_revision_id") and stable_revision.get("diff_hash") == party_input.get("final_diff_hash"), "party integration fixture の revision_id / diff_hash は input と一致させてください。")
    for key in ("trial_bound_to_revision", "ledger_bound_to_revision", "implementation_edits_paused_during_trial", "revision_change_invalidates_trial", "revision_change_reopens_barrier"):
        require(stable_revision.get(key) is True, f"party_integration.expected.stable_snapshot.{key} は true にしてください。")
    snapshot_layers = mapping(party.get("parallel_snapshot_layers"), "party_integration.expected.parallel_snapshot_layers")
    require(snapshot_layers.get("base_snapshot_id") == party_input.get("base_snapshot_id"), "party integration fixture は共通 base snapshot を固定してください。")
    for key in ("owned_scope_results_required", "owned_scopes_must_not_overlap", "other_owned_scope_change_does_not_stale_report", "same_owned_scope_change_stales_report", "integrated_snapshot_only_after_barrier"):
        require(snapshot_layers.get(key) is True, f"party_integration.expected.parallel_snapshot_layers.{key} は true にしてください。")
    owned_results = sequence(party_input.get("owned_scope_results"), "party_integration.input.owned_scope_results")
    require(len(owned_results) == len(required_assignment_ids), "party integration fixture は assignment ごとの owned-scope result を要求してください。")
    owned_paths: set[str] = set()
    for index, value in enumerate(owned_results):
        result = mapping(value, f"party_integration.input.owned_scope_results[{index}]")
        paths = set(sequence(result.get("scope_paths"), f"party_integration.input.owned_scope_results[{index}].scope_paths"))
        require(not owned_paths.intersection(paths), "party integration fixture の owned scope を重複させないでください。")
        owned_paths.update(str(path) for path in paths)
        require(isinstance(result.get("diff_hash"), str), "party integration fixture の owned result は diff_hash を持ってください。")
    party_forbidden = _forbidden(party.get("forbidden"), "party_integration.expected.forbidden")
    require({"integrate_incomplete_assignment", "trial_against_moving_target", "concurrent_shared_file_edit", "global_result_hash_per_parallel_worker"} <= set(party_forbidden), "party integration fixture の forbidden が不足しています。")

    guild = _base_fixture(_fixture("guild_quest_routing.yaml"), "guild_quest_routing.yaml")
    require(guild.get("rank") == "guild_quest" and guild.get("strategy_owner") == "guildmaster", "guild routing fixture は guild_quest / guildmaster にしてください。")
    routing_reasons = set(sequence(guild.get("routing_reasons"), "guild_routing.expected.routing_reasons"))
    require({"broad_impact", "multiple_parties", "safety_judgment"} <= routing_reasons, "guild routing fixture は broad impact / multiple parties / safety judgment を要求してください。")
    for key in ("command_draft_required", "party_boundaries_required", "authority_per_party_required", "trial_depth_required", "safety_gate_considered", "normalize_to_single_party_only_with_reason"):
        require(guild.get(key) is True, f"guild_routing.expected.{key} は true にしてください。")
    require(guild.get("guildmaster_implements") is False, "guild routing fixture は guildmaster の実装を禁止してください。")
    guild_forbidden = _forbidden(guild.get("forbidden"), "guild_routing.expected.forbidden")
    require({"route_directly_to_adventurer", "shared_file_multi_owner", "omit_safety_gate_decision"} <= set(guild_forbidden), "guild routing fixture の forbidden が不足しています。")

    safety = _base_fixture(_fixture("safety_gate_needs_human.yaml"), "safety_gate_needs_human.yaml")
    require(safety.get("trial_depth") == "safety_gate" and safety.get("outcome") == "needs_human", "safety fixture は safety_gate / needs_human にしてください。")
    safety_authority = _authority(safety.get("authority"), "safety.expected.authority")
    require(not any(safety_authority[key] for key in ("edit", "validate", "local_git", "external_actions")), "safety fixture は read 以外を禁止してください。")
    require({"deploy", "secret"} <= set(sequence(safety.get("human_confirmation_required"), "safety.expected.human_confirmation_required")), "safety fixture は deploy / secret の人間確認を要求してください。")
    _forbidden(safety.get("forbidden"), "safety.expected.forbidden")

    approval_doc = _fixture("safety_approval_scope_absolute_deny.yaml")
    approval_input = mapping(approval_doc.get("input"), "safety_approval.input")
    human_approval = mapping(approval_input.get("human_approval"), "safety_approval.input.human_approval")
    approval = _base_fixture(approval_doc, "safety_approval_scope_absolute_deny.yaml")
    require(approval.get("approved_scope_outcome") == "proceed_within_approved_scope" and approval.get("denied_scope_outcome") == "reject_absolute_deny", "safety approval fixture は approved scope と absolute deny を分離してください。")
    approval_scope = mapping(approval.get("approval_scope"), "safety_approval.expected.approval_scope")
    require(approval_scope.get("explicit_action_required") is True and approval_scope.get("authorized_actions") == human_approval.get("actions"), "safety approval fixture は明示 action だけを許可してください。")
    require(approval_scope.get("target") == human_approval.get("target") and approval_scope.get("revision") == human_approval.get("revision"), "safety approval fixture は target / revision を approval に固定してください。")
    for key in ("non_transferable", "one_shot", "new_quest_required_after_approval", "scope_expansion_requires_new_approval"):
        require(approval_scope.get(key) is True, f"safety_approval.expected.approval_scope.{key} は true にしてください。")
    absolute_deny = mapping(approval.get("absolute_deny"), "safety_approval.expected.absolute_deny")
    require(absolute_deny.get("applies_even_with_human_approval") is True, "absolute deny は人間承認でも解除しないでください。")
    require({"secret_access", "token_access", "credential_access", "password_access", "key_access", "auth_access", "pii_access"} <= set(sequence(absolute_deny.get("operations"), "safety_approval.expected.absolute_deny.operations")), "absolute deny operations が不足しています。")
    approval_forbidden = _forbidden(approval.get("forbidden"), "safety_approval.expected.forbidden")
    require({"production_deploy_from_staging_approval", "secret_access", "pii_access", "approval_scope_expansion"} <= set(approval_forbidden), "safety approval fixture の forbidden が不足しています。")

    trial = _base_fixture(_fixture("focused_trial_reviewer_budget.yaml"), "focused_trial_reviewer_budget.yaml")
    require(trial.get("trial_depth") == "focused_trial" and trial.get("worker_id") == "inquisitor", "focused trial fixture は inquisitor focused_trial にしてください。")
    _authority(trial.get("authority"), "focused_trial.expected.authority")
    focus_reviewers = mapping(trial.get("focus_reviewers"), "focused_trial.expected.focus_reviewers")
    require(focus_reviewers.get("reviewer_worker_id") == "focus_reviewer" and focus_reviewers.get("assignment_owner") == "inquisitor", "focused trial fixture は inquisitor が独立 focus_reviewer を割り当てる契約にしてください。")
    require(focus_reviewers.get("count_decision_required") is True, "focused trial fixture は reviewer 数判断を要求してください。")
    require(set(sequence(focus_reviewers.get("max_bound_by"), "focused_trial.expected.focus_reviewers.max_bound_by")) == {"workers.focus_reviewer.max_parallel", "autonomy_budget.subassignments"}, "focused trial fixture の reviewer 上限が不足しています。")
    require(focus_reviewers.get("cost_reason_required") is True and focus_reviewers.get("finding_disposition_required") is True, "focused trial fixture は cost reason / finding disposition を要求してください。")
    trial_handoff = mapping(trial.get("handoff_sufficiency"), "focused_trial.expected.handoff_sufficiency")
    trial_required = set(sequence(trial_handoff.get("trial_to_ledger_final_ready_requires"), "focused_trial.expected.handoff_sufficiency.trial_to_ledger_final_ready_requires"))
    require({"decision", "findings", "intent_coverage", "quest_awareness", "control_decision", "validation_evidence", "advisor_dialogue_synthesis", "reviewer_synthesis", "finding_dispositions", "risks"} <= trial_required, "focused trial fixture は trial_to_ledger_final の required evidence を要求してください。")

    revision_trial_doc = _fixture("focused_trial_revision_bound_input.yaml")
    revision_trial_input = mapping(revision_trial_doc.get("input"), "focused_trial_revision.input")
    revision_trial = _base_fixture(revision_trial_doc, "focused_trial_revision_bound_input.yaml")
    require(revision_trial.get("worker_id") == "inquisitor" and revision_trial.get("trial_depth") == "focused_trial", "revision-bound Trial fixture は inquisitor focused_trial にしてください。")
    revision_binding = mapping(revision_trial.get("revision_binding"), "focused_trial_revision.expected.revision_binding")
    require(revision_binding.get("required") is True and revision_binding.get("source_kind") == "commit_sha", "revision-bound Trial fixture は commit SHA binding を要求してください。")
    for key in ("base_ref", "head_ref", "revision_id", "diff_hash"):
        require(revision_binding.get(key) == revision_trial_input.get(key), f"revision-bound Trial fixture の {key} は input と一致させてください。")
    for key in ("subject_assignment_ids", "subject_report_ids", "changed_files"):
        require(revision_binding.get(key) == revision_trial_input.get(key), f"revision-bound Trial fixture の {key} は input と一致させてください。")
    require(revision_binding.get("stale_evidence_outcome") == "stop", "revision-bound Trial fixture は stale evidence で停止してください。")
    for key in ("clean_dirty_state_required", "assignment_ids_bound", "report_ids_bound", "changed_files_bound", "evidence_bound_to_revision", "moving_target_rejected", "revision_change_requires_rerun"):
        require(revision_binding.get(key) is True, f"focused_trial_revision.expected.revision_binding.{key} は true にしてください。")
    revision_forbidden = _forbidden(revision_trial.get("forbidden"), "focused_trial_revision.expected.forbidden")
    require({"accept_stale_diff", "unbound_finding_evidence", "accept_after_revision_change_without_rerun"} <= set(revision_forbidden), "revision-bound Trial fixture の forbidden が不足しています。")

    reviewer_doc = _fixture("focus_reviewer_bounded_contract.yaml")
    reviewer_input = mapping(reviewer_doc.get("input"), "focus_reviewer.input")
    reviewer = _base_fixture(reviewer_doc, "focus_reviewer_bounded_contract.yaml")
    require(reviewer.get("worker_id") == "focus_reviewer" and reviewer.get("assignment_owner") == "inquisitor" and reviewer.get("reviewer_role") == "bounded_trial_focus_reviewer", "focus reviewer fixture は inquisitor が割り当てる独立 focus_reviewer にしてください。")
    for key in ("autonomy_budget_subassignments", "focus_advisor_assignments", "requested_focus_reviewers", "workers_focus_reviewer_max_parallel"):
        value = reviewer_input.get(key)
        require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"focus_reviewer.input.{key} は 0 以上の整数にしてください。")
    available_shared_budget = reviewer_input["autonomy_budget_subassignments"] - reviewer_input["focus_advisor_assignments"]
    expected_reviewer_count = min(reviewer_input["requested_focus_reviewers"], reviewer_input["workers_focus_reviewer_max_parallel"], available_shared_budget)
    require(reviewer.get("reviewer_count") == expected_reviewer_count == 1, "focus reviewer fixture は shared budget 内の reviewer_count=1 にしてください。")
    require(set(sequence(reviewer.get("max_bound_by"), "focus_reviewer.expected.max_bound_by")) == {"workers.focus_reviewer.max_parallel", "autonomy_budget.subassignments"}, "focus reviewer fixture の上限が不足しています。")
    require(reviewer.get("consumes_autonomy_budget") == "subassignments" and reviewer.get("shared_budget_rule") == "focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments", "focus reviewer fixture は shared subassignment budget を要求してください。")
    for key in ("focus_split_required", "read_only_required", "owner_synthesis_required", "finding_disposition_required", "cost_reason_required_always", "skip_reason_required_when_not_used"):
        require(reviewer.get(key) is True, f"focus_reviewer.expected.{key} は true にしてください。")
    require(reviewer.get("advisor_role") is False and reviewer.get("final_decision_owner") == "inquisitor", "focus reviewer fixture は advisor と分離し、最終判断を inquisitor にしてください。")
    assignment_snapshot = mapping(reviewer_input.get("assignment_snapshot"), "focus_reviewer.input.assignment_snapshot")
    matching_snapshot = mapping(reviewer_input.get("matching_report_snapshot"), "focus_reviewer.input.matching_report_snapshot")
    mismatched_snapshot = mapping(reviewer_input.get("mismatched_report_snapshot"), "focus_reviewer.input.mismatched_report_snapshot")
    require(assignment_snapshot == matching_snapshot and assignment_snapshot != mismatched_snapshot, "focus reviewer fixture は match / mismatch snapshot を区別してください。")
    assignment_identity = mapping(reviewer.get("assignment_identity_required"), "focus_reviewer.expected.assignment_identity_required")
    require(assignment_identity == {"worker_id": "focus_reviewer", "owner_worker_id": "inquisitor"}, "focus reviewer は inquisitor caller と worker identity を開始時に検証してください。")
    require(reviewer.get("caller_enforcement") == "policy_only_with_queue_lineage", "focus reviewer caller rule はruntime ACLではなくpolicy-onlyと明記してください。")
    queue_lineage = mapping(reviewer.get("queue_lineage_required"), "focus_reviewer.expected.queue_lineage_required")
    require(queue_lineage == {"trial_ref": True, "trial_owner_worker_id": "inquisitor", "unverifiable_status": "invalid_assignment"}, "focus reviewer はqueue trial lineageを照合してください。")
    require(reviewer.get("matching_snapshot_status") == "matched" and reviewer.get("mismatched_snapshot_status") == "stale_evidence", "focus reviewer は snapshot mismatch で stale_evidence にしてください。")
    require(reviewer.get("recursive_multi_agent_disabled") is True, "focus reviewer は recursive multi-agent capability を無効にしてください。")
    reviewer_forbidden = _forbidden(reviewer.get("forbidden"), "focus_reviewer.expected.forbidden")
    require({"exceed_shared_budget", "reviewer_write_access", "reviewer_acceptance_decision", "non_inquisitor_caller", "unverified_caller_lineage", "stale_evidence_reuse", "recursive_subagent"} <= set(reviewer_forbidden), "focus reviewer fixture の forbidden が不足しています。")

    advisor = _base_fixture(_fixture("advisor_dialogue_same_focus_stop.yaml"), "advisor_dialogue_same_focus_stop.yaml")
    require(advisor.get("worker_id") == "advisor" and advisor.get("decision_authority") is False and advisor.get("terminal_worker") is True, "advisor fixture は terminal worker / decision_authority=false にしてください。")
    dialogue = mapping(advisor.get("dialogue_policy"), "advisor.expected.dialogue_policy")
    require(dialogue.get("mode") == "confidence_based" and dialogue.get("same_focus_only") is True, "advisor fixture は confidence_based / same_focus_only を要求してください。")
    require("authority_or_boundary_would_expand" in sequence(dialogue.get("stop_when"), "advisor.expected.dialogue_policy.stop_when"), "advisor fixture は authority/boundary 拡大で停止してください。")
    _forbidden(advisor.get("forbidden"), "advisor.expected.forbidden")

    advisor_synthesis_doc = _fixture("advisor_owner_synthesis.yaml")
    advisor_synthesis_input = mapping(advisor_synthesis_doc.get("input"), "advisor_synthesis.input")
    advisor_synthesis = _base_fixture(advisor_synthesis_doc, "advisor_owner_synthesis.yaml")
    require(advisor_synthesis.get("worker_id") == "advisor" and advisor_synthesis.get("decision_authority") is False and advisor_synthesis.get("terminal_worker") is True, "advisor synthesis fixture は terminal worker / decision_authority=false にしてください。")
    owner_synthesis = mapping(advisor_synthesis.get("owner_synthesis"), "advisor_synthesis.expected.owner_synthesis")
    require(owner_synthesis.get("required") is True and owner_synthesis.get("owner_worker_id") == advisor_synthesis_input.get("owner_worker_id"), "advisor synthesis fixture は assigned owner の synthesis を要求してください。")
    require(owner_synthesis.get("evidence_verification_required") is True and owner_synthesis.get("final_decision_by_owner_only") is True, "advisor synthesis fixture は evidence 確認と owner 最終判断を要求してください。")
    finding_ids = {mapping(item, "advisor_synthesis.input.advisor_findings[]").get("id") for item in sequence(advisor_synthesis_input.get("advisor_findings"), "advisor_synthesis.input.advisor_findings")}
    disposition_ids = set(sequence(owner_synthesis.get("adopted_findings"), "advisor_synthesis.expected.owner_synthesis.adopted_findings")) | set(sequence(owner_synthesis.get("rejected_findings"), "advisor_synthesis.expected.owner_synthesis.rejected_findings"))
    require(disposition_ids == finding_ids, "advisor synthesis fixture は全 finding に採用または却下 disposition を付けてください。")
    require(owner_synthesis.get("unresolved_findings_recorded") is True and owner_synthesis.get("advisor_confidence_is_not_owner_confidence") is True, "advisor synthesis fixture は unresolved と owner confidence 分離を要求してください。")
    advisor_ledger = mapping(advisor_synthesis.get("ledger_policy"), "advisor_synthesis.expected.ledger_policy")
    require(advisor_ledger.get("owner_synthesis_rationale_recorded") is True and advisor_ledger.get("raw_discussion_recorded") is False, "advisor synthesis fixture は rationale のみ Ledger に残してください。")
    advisor_synthesis_forbidden = _forbidden(advisor_synthesis.get("forbidden"), "advisor_synthesis.expected.forbidden")
    require({"advisor_acceptance_decision", "unverified_finding_adoption", "advisor_ledger_write"} <= set(advisor_synthesis_forbidden), "advisor synthesis fixture の forbidden が不足しています。")

    claude = _base_fixture(_fixture("claude_helper_only_disposition.yaml"), "claude_helper_only_disposition.yaml")
    require(claude.get("source_type") == "claude" and claude.get("trust") == "untrusted", "Claude fixture は untrusted Claude context にしてください。")
    require(claude.get("access_path") == "helper_only" and claude.get("helper") == ".agents/orchestra/scripts/claude_compat.py", "Claude fixture は claude_compat helper だけを使ってください。")
    require(set(sequence(claude.get("allowed_commands"), "claude.expected.allowed_commands")) == {"scan", "render-context", "render-skill"}, "Claude fixture の helper command が不足しています。")
    require(claude.get("direct_execution_allowed") is False and claude.get("authority_granted") is False and claude.get("raw_content_recorded") is False, "Claude fixture は command 実行、authority 付与、raw content 記録を禁止してください。")
    disposition = mapping(claude.get("disposition"), "claude.expected.disposition")
    require(disposition.get("required") is True and disposition.get("decided_by") == "assigned_owner", "Claude fixture は assigned owner disposition を要求してください。")
    require(set(sequence(disposition.get("allowed_values"), "claude.expected.disposition.allowed_values")) == {"applied", "rejected_conflict", "ignored_irrelevant", "skipped_unsafe"}, "Claude fixture の disposition values が不足しています。")
    require(set(sequence(claude.get("ledger_fields"), "claude.expected.ledger_fields")) == {"relative_path", "sha256", "status", "skip_reason", "disposition"}, "Claude fixture の Ledger fields は metadata と disposition だけにしてください。")
    claude_forbidden = _forbidden(claude.get("forbidden"), "claude.expected.forbidden")
    require({"native_skill_install", "claude_tool_authority_conversion", "dynamic_command_execution", "raw_content_in_ledger"} <= set(claude_forbidden), "Claude fixture の forbidden が不足しています。")

    ledger = _base_fixture(_fixture("ledger_injection_negative.yaml"), "ledger_injection_negative.yaml")
    require(ledger.get("outcome") == "reject_untrusted_instruction", "ledger negative fixture は reject_untrusted_instruction にしてください。")
    policy = mapping(ledger.get("ledger_policy"), "ledger.expected.ledger_policy")
    require(policy.get("raw_discussion_recorded") is False and policy.get("secret_values_recorded") is False, "ledger negative fixture は raw discussion / secret 保存を禁止してください。")
    require(policy.get("decision_rationale_recorded") is True and policy.get("evidence_refs_recorded") is True, "ledger negative fixture は decision rationale / evidence refs を要求してください。")
    _forbidden(ledger.get("forbidden"), "ledger.expected.forbidden")

    courier_doc = _fixture("courier_explicit_git_postcondition.yaml")
    courier_input = mapping(courier_doc.get("input"), "courier_git.input")
    courier = _base_fixture(courier_doc, "courier_explicit_git_postcondition.yaml")
    require(courier.get("worker_id") == "courier", "courier Git fixture は courier にしてください。")
    courier_authority = _authority(courier.get("authority"), "courier_git.expected.authority")
    require(courier_authority == {"read": True, "edit": False, "validate": False, "local_git": True, "external_actions": False}, "courier Git fixture は local_git だけを追加許可してください。")
    authorization = mapping(courier.get("authorization"), "courier_git.expected.authorization")
    require(authorization.get("source") == "latest_human_instruction" and authorization.get("explicit_operation") == "stage_commit", "courier Git fixture は最新の人間指示による stage / commit だけを許可してください。")
    require(authorization.get("target_repo_root") == courier_input.get("target_repo_root") and authorization.get("allowed_paths") == courier_input.get("allowed_paths"), "courier Git fixture は target repo と paths を明示 scope に固定してください。")
    require(authorization.get("accepted_revision_id") == courier_input.get("accepted_revision_id") and authorization.get("accepted_diff_hash") == courier_input.get("accepted_diff_hash"), "courier Git fixture は Trial が accept した revision / diff hash に固定してください。")
    require(authorization.get("implicit_request_allowed") is False, "courier Git fixture は暗黙の Git 依頼を許可しないでください。")
    preconditions = mapping(courier.get("preconditions"), "courier_git.expected.preconditions")
    for key in ("target_repo_root_confirmed", "branch_confirmed", "git_status_inspected", "staged_diff_inspected", "unrelated_changes_excluded"):
        require(preconditions.get(key) is True, f"courier_git.expected.preconditions.{key} は true にしてください。")
    postconditions = mapping(courier.get("postconditions"), "courier_git.expected.postconditions")
    for key in ("git_status_checked", "commit_hash_recorded", "committed_paths_match_scope", "remaining_changes_reported", "branch_recorded", "upstream_validation_result_recorded", "ledger_event_disposition_recorded", "committed_diff_matches_accepted_hash", "external_state_unchanged"):
        require(postconditions.get(key) is True, f"courier_git.expected.postconditions.{key} は true にしてください。")
    courier_forbidden = _forbidden(courier.get("forbidden"), "courier_git.expected.forbidden")
    require({"push", "pull_request", "destructive_git", "unrelated_stage"} <= set(courier_forbidden), "courier Git fixture の forbidden が不足しています。")

    sentinel_doc = _fixture("quest_sentinel_calibration.yaml")
    sentinel_input = mapping(sentinel_doc.get("input"), "quest_sentinel_calibration.input")
    sentinel = _base_fixture(sentinel_doc, "quest_sentinel_calibration.yaml")
    require(sentinel.get("worker_id") == "quest_sentinel" and sentinel.get("decision_authority") is False and sentinel.get("terminal_worker") is True, "quest_sentinel calibration fixture は terminal worker / decision_authority=false にしてください。")
    require(sentinel_input.get("confidence_percent") == 92 and sentinel.get("confidence_threshold_applied") == "confidence>=75", "quest_sentinel calibration fixture は confidence 92 を below-75 と誤分類しないでください。")
    require(sentinel.get("control_decision") == "invoke_security_review", "quest_sentinel calibration fixture は security review を推薦してください。")
    triggers_present = set(sequence(sentinel.get("triggers_present"), "quest_sentinel_calibration.expected.triggers_present"))
    triggers_absent = set(sequence(sentinel.get("triggers_absent"), "quest_sentinel_calibration.expected.triggers_absent"))
    require({"scope_expands", "security_sensitive"} <= triggers_present, "quest_sentinel calibration fixture は scope / security trigger を要求してください。")
    require({"confidence_below_75", "tests_fail_repeatedly"} <= triggers_absent and not (triggers_present & triggers_absent), "quest_sentinel calibration fixture は誤った confidence / test trigger を除外してください。")
    sentinel_output = mapping(sentinel.get("output_contract"), "quest_sentinel_calibration.expected.output_contract")
    require(sentinel_output.get("quest_awareness_only") is True and sentinel_output.get("control_decision_only") is True, "quest_sentinel calibration fixture は quest_awareness / control_decision だけを返してください。")
    sentinel_forbidden = _forbidden(sentinel.get("forbidden"), "quest_sentinel_calibration.expected.forbidden")
    require({"implementation", "acceptance_decision", "fabricated_confidence_trigger"} <= set(sentinel_forbidden), "quest_sentinel calibration fixture の forbidden が不足しています。")

    confidence75 = _base_fixture(_fixture("quest_awareness_confidence_below_75.yaml"), "quest_awareness_confidence_below_75.yaml")
    require(confidence75.get("control_decision") == "gather_more_evidence", "confidence<75 fixture は gather_more_evidence にしてください。")
    require(confidence75.get("finalize_allowed") is False, "confidence<75 fixture は finalize を禁止してください。")
    require(confidence75.get("quest_sentinel_considered") is True, "confidence<75 fixture は quest_sentinel 検討を要求してください。")
    require(_required_next_action(confidence75.get("required_next_action"), "confidence<75.expected.required_next_action") == "inspect_diff_or_run_additional_verification", "confidence<75 fixture は追加 evidence / 検証を next action にしてください。")
    confidence75_forbidden = _forbidden(confidence75.get("forbidden"), "confidence<75.expected.forbidden")
    require({"finalize_without_more_evidence", "raise_confidence_without_evidence"} <= set(confidence75_forbidden), "confidence<75 fixture の forbidden が不足しています。")
    require("controller_" "considered" not in confidence75, "confidence<75 fixture は旧 controller_" "considered key を使わないでください。")

    confidence50 = _base_fixture(_fixture("quest_awareness_confidence_below_50_stop.yaml"), "quest_awareness_confidence_below_50_stop.yaml")
    require(confidence50.get("control_decision") == "revise_plan", "confidence<50 fixture は revise_plan にしてください。")
    require(confidence50.get("speculative_editing_allowed") is False, "confidence<50 fixture は speculative editing を禁止してください。")
    require(_required_next_action(confidence50.get("required_next_action"), "confidence<50.expected.required_next_action") == "reconstruct_task_contract", "confidence<50 fixture は task contract 再構成を next action にしてください。")
    confidence50_forbidden = _forbidden(confidence50.get("forbidden"), "confidence<50.expected.forbidden")
    require({"speculative_fix_stacking", "final_report_as_complete"} <= set(confidence50_forbidden), "confidence<50 fixture の forbidden が不足しています。")

    failed = _base_fixture(_fixture("quest_awareness_failed_check_first_failure.yaml"), "quest_awareness_failed_check_first_failure.yaml")
    require(failed.get("control_decision") == "run_tests", "failed check fixture は run_tests にしてください。")
    require(failed.get("first_failure_required") is True and failed.get("rerun_same_check_required") is True, "failed check fixture は first failure と same check rerun を要求してください。")
    failed_forbidden = _forbidden(failed.get("forbidden"), "failed_check.expected.forbidden")
    require({"multiple_speculative_fixes", "skip_failure_explanation"} <= set(failed_forbidden), "failed check fixture の forbidden が不足しています。")

    scope = _base_fixture(_fixture("quest_awareness_scope_drift.yaml"), "quest_awareness_scope_drift.yaml")
    require(scope.get("control_decision") == "revise_plan" and scope.get("pause_required") is True, "scope drift fixture は pause と revise_plan を要求してください。")
    require(_required_next_action(scope.get("required_next_action"), "scope_drift.expected.required_next_action") == "restate_scope_and_check_goal_relevance", "scope drift fixture は scope 再確認を next action にしてください。")
    scope_forbidden = _forbidden(scope.get("forbidden"), "scope_drift.expected.forbidden")
    require({"unrelated_refactor", "silent_scope_expansion"} <= set(scope_forbidden), "scope drift fixture の forbidden が不足しています。")

    security = _base_fixture(_fixture("quest_awareness_security_sensitive.yaml"), "quest_awareness_security_sensitive.yaml")
    require(security.get("risk_level") == "high" and security.get("control_decision") == "invoke_security_review", "security-sensitive fixture は high risk と security review を要求してください。")
    require(security.get("security_review_route") == "existing_authority_security_focused_trial", "security-sensitive fixture は既存 authority 内の security-focused Trial route を要求してください。")
    require(security.get("security_review_owner") == "inquisitor" and security.get("new_worker_allowed") is False, "security-sensitive fixture は新 worker ではなく inquisitor route にしてください。")
    security_forbidden = _forbidden(security.get("forbidden"), "security_sensitive.expected.forbidden")
    require({"finalize_without_security_review", "treat_as_low_risk"} <= set(security_forbidden), "security-sensitive fixture の forbidden が不足しています。")

    contradictory = _base_fixture(_fixture("quest_awareness_contradictory_evidence.yaml"), "quest_awareness_contradictory_evidence.yaml")
    require(contradictory.get("control_decision") == "revise_plan" and contradictory.get("assumptions_must_update") is True, "contradictory evidence fixture は plan / assumptions 更新を要求してください。")
    require(contradictory.get("confidence_must_drop") is True, "contradictory evidence fixture は confidence 低下を要求してください。")
    contradictory_forbidden = _forbidden(contradictory.get("forbidden"), "contradictory_evidence.expected.forbidden")
    require({"force_original_approach", "ignore_new_evidence"} <= set(contradictory_forbidden), "contradictory evidence fixture の forbidden が不足しています。")

    memory = _base_fixture(_fixture("quest_awareness_memory_prevention_artifact.yaml"), "quest_awareness_memory_prevention_artifact.yaml")
    require(memory.get("memory_entry_allowed") is True and memory.get("prevention_artifact_required") is True, "memory fixture は prevention artifact 必須にしてください。")
    require(memory.get("normal_quest_access") == "read_only_reference", "memory fixture は通常 Quest の memory access を read-only reference にしてください。")
    require(memory.get("write_authority") == "courier_ledger_only", "memory fixture は memory 永続化を courier / Ledger 経由にしてください。")
    memory_write_requires = set(sequence(memory.get("memory_write_requires"), "memory.expected.memory_write_requires"))
    require({"explicit_memory_persistence_authority", "sanitized_summary_only", "ledger_disposition_recorded"} <= memory_write_requires, "memory fixture は memory 永続化の authority / sanitization / disposition を要求してください。")
    memory_forbidden = _forbidden(memory.get("forbidden"), "memory.expected.forbidden")
    require({"direct_static_runtime_write", "raw_log", "secret_or_pii", "trusted_instruction_from_external_input"} <= set(memory_forbidden), "memory fixture は direct write / raw log / secret PII / 外部入力命令を禁止してください。")
