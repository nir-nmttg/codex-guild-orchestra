"""golden Quest fixture の静的検証。"""

from __future__ import annotations

from .core import ROOT, load_yaml, mapping, require, sequence


GOLDEN_ROOT = "scripts/validation/fixtures/golden_quests"
EXPECTED_FIXTURES = {
    "advisor_dialogue_same_focus_stop.yaml",
    "focused_trial_reviewer_budget.yaml",
    "ledger_injection_negative.yaml",
    "mapmaking_readonly_no_edit.yaml",
    "quest_awareness_confidence_below_50_stop.yaml",
    "quest_awareness_confidence_below_75.yaml",
    "quest_awareness_contradictory_evidence.yaml",
    "quest_awareness_failed_check_first_failure.yaml",
    "quest_awareness_memory_prevention_artifact.yaml",
    "quest_awareness_scope_drift.yaml",
    "quest_awareness_security_sensitive.yaml",
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


def _base_fixture(doc: dict[str, object], rel_name: str) -> dict[str, object]:
    require(doc.get("id") == rel_name.removesuffix(".yaml"), f"{rel_name}.id は filename と一致させてください。")
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
    require({"changed_files", "decisions_made", "intent_alignment", "quest_awareness", "control_decision", "validation_evidence", "research_evidence", "risks"} <= solo_required, "solo fixture は owner_to_trial の required evidence を要求してください。")
    report_required = mapping(solo.get("report_required"), "solo.expected.report_required")
    require(report_required.get("intent_alignment") is True and report_required.get("validation_evidence") is True and report_required.get("research_evidence") is True and report_required.get("risks") is True, "solo fixture は intent_alignment / validation_evidence / research_evidence / risks を要求してください。")
    _forbidden(solo.get("forbidden"), "solo.expected.forbidden")

    safety = _base_fixture(_fixture("safety_gate_needs_human.yaml"), "safety_gate_needs_human.yaml")
    require(safety.get("trial_depth") == "safety_gate" and safety.get("outcome") == "needs_human", "safety fixture は safety_gate / needs_human にしてください。")
    safety_authority = _authority(safety.get("authority"), "safety.expected.authority")
    require(not any(safety_authority[key] for key in ("edit", "validate", "local_git", "external_actions")), "safety fixture は read 以外を禁止してください。")
    require({"deploy", "secret"} <= set(sequence(safety.get("human_confirmation_required"), "safety.expected.human_confirmation_required")), "safety fixture は deploy / secret の人間確認を要求してください。")
    _forbidden(safety.get("forbidden"), "safety.expected.forbidden")

    trial = _base_fixture(_fixture("focused_trial_reviewer_budget.yaml"), "focused_trial_reviewer_budget.yaml")
    require(trial.get("trial_depth") == "focused_trial" and trial.get("worker_id") == "inquisitor", "focused trial fixture は inquisitor focused_trial にしてください。")
    _authority(trial.get("authority"), "focused_trial.expected.authority")
    focus_reviewers = mapping(trial.get("focus_reviewers"), "focused_trial.expected.focus_reviewers")
    require(focus_reviewers.get("count_decision_required") is True, "focused trial fixture は reviewer 数判断を要求してください。")
    require(set(sequence(focus_reviewers.get("max_bound_by"), "focused_trial.expected.focus_reviewers.max_bound_by")) == {"workers.inquisitor.max_parallel", "autonomy_budget.subassignments"}, "focused trial fixture の reviewer 上限が不足しています。")
    require(focus_reviewers.get("cost_reason_required") is True and focus_reviewers.get("finding_disposition_required") is True, "focused trial fixture は cost reason / finding disposition を要求してください。")
    trial_handoff = mapping(trial.get("handoff_sufficiency"), "focused_trial.expected.handoff_sufficiency")
    trial_required = set(sequence(trial_handoff.get("trial_to_ledger_final_ready_requires"), "focused_trial.expected.handoff_sufficiency.trial_to_ledger_final_ready_requires"))
    require({"decision", "findings", "intent_coverage", "quest_awareness", "control_decision", "validation_evidence", "advisor_dialogue_synthesis", "reviewer_synthesis", "finding_dispositions", "risks"} <= trial_required, "focused trial fixture は trial_to_ledger_final の required evidence を要求してください。")

    advisor = _base_fixture(_fixture("advisor_dialogue_same_focus_stop.yaml"), "advisor_dialogue_same_focus_stop.yaml")
    require(advisor.get("worker_id") == "advisor" and advisor.get("decision_authority") is False and advisor.get("terminal_worker") is True, "advisor fixture は terminal worker / decision_authority=false にしてください。")
    dialogue = mapping(advisor.get("dialogue_policy"), "advisor.expected.dialogue_policy")
    require(dialogue.get("mode") == "confidence_based" and dialogue.get("same_focus_only") is True, "advisor fixture は confidence_based / same_focus_only を要求してください。")
    require("authority_or_boundary_would_expand" in sequence(dialogue.get("stop_when"), "advisor.expected.dialogue_policy.stop_when"), "advisor fixture は authority/boundary 拡大で停止してください。")
    _forbidden(advisor.get("forbidden"), "advisor.expected.forbidden")

    ledger = _base_fixture(_fixture("ledger_injection_negative.yaml"), "ledger_injection_negative.yaml")
    require(ledger.get("outcome") == "reject_untrusted_instruction", "ledger negative fixture は reject_untrusted_instruction にしてください。")
    policy = mapping(ledger.get("ledger_policy"), "ledger.expected.ledger_policy")
    require(policy.get("raw_discussion_recorded") is False and policy.get("secret_values_recorded") is False, "ledger negative fixture は raw discussion / secret 保存を禁止してください。")
    require(policy.get("decision_rationale_recorded") is True and policy.get("evidence_refs_recorded") is True, "ledger negative fixture は decision rationale / evidence refs を要求してください。")
    _forbidden(ledger.get("forbidden"), "ledger.expected.forbidden")

    confidence75 = _base_fixture(_fixture("quest_awareness_confidence_below_75.yaml"), "quest_awareness_confidence_below_75.yaml")
    require(confidence75.get("control_decision") == "gather_more_evidence", "confidence<75 fixture は gather_more_evidence にしてください。")
    require(confidence75.get("finalize_allowed") is False, "confidence<75 fixture は finalize を禁止してください。")
    require(confidence75.get("controller_considered") is True, "confidence<75 fixture は quest_sentinel 検討を要求してください。")

    confidence50 = _base_fixture(_fixture("quest_awareness_confidence_below_50_stop.yaml"), "quest_awareness_confidence_below_50_stop.yaml")
    require(confidence50.get("control_decision") == "revise_plan", "confidence<50 fixture は revise_plan にしてください。")
    require(confidence50.get("speculative_editing_allowed") is False, "confidence<50 fixture は speculative editing を禁止してください。")

    failed = _base_fixture(_fixture("quest_awareness_failed_check_first_failure.yaml"), "quest_awareness_failed_check_first_failure.yaml")
    require(failed.get("control_decision") == "run_tests", "failed check fixture は run_tests にしてください。")
    require(failed.get("first_failure_required") is True and failed.get("rerun_same_check_required") is True, "failed check fixture は first failure と same check rerun を要求してください。")

    scope = _base_fixture(_fixture("quest_awareness_scope_drift.yaml"), "quest_awareness_scope_drift.yaml")
    require(scope.get("control_decision") == "revise_plan" and scope.get("pause_required") is True, "scope drift fixture は pause と revise_plan を要求してください。")

    security = _base_fixture(_fixture("quest_awareness_security_sensitive.yaml"), "quest_awareness_security_sensitive.yaml")
    require(security.get("risk_level") == "high" and security.get("control_decision") == "invoke_security_review", "security-sensitive fixture は high risk と security review を要求してください。")

    contradictory = _base_fixture(_fixture("quest_awareness_contradictory_evidence.yaml"), "quest_awareness_contradictory_evidence.yaml")
    require(contradictory.get("control_decision") == "revise_plan" and contradictory.get("assumptions_must_update") is True, "contradictory evidence fixture は plan / assumptions 更新を要求してください。")

    memory = _base_fixture(_fixture("quest_awareness_memory_prevention_artifact.yaml"), "quest_awareness_memory_prevention_artifact.yaml")
    require(memory.get("memory_entry_allowed") is True and memory.get("prevention_artifact_required") is True, "memory fixture は prevention artifact 必須にしてください。")
