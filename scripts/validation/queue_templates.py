"""compact queue artifact契約を検証する。

templateはモデルへtask evidenceだけを要求し、オーケストレーション上の儀式を要求しない。
identity、authority、lineage、terminal status、snapshotはhelperとvalidatorが厳密に管理する。
"""

from __future__ import annotations

from .core import load_yaml, mapping, read, require, sequence
from .rules import CORE_TRIAL_CHECKS, QUEUE_TEMPLATE_PATHS, VOCABULARY_DRIFT_TERMS
from .schema_helpers import (
    validate_authority,
    validate_boundaries,
    validate_evidence_state,
    validate_subject_snapshot,
    validate_template_metadata,
)


TEMPLATE_ROOT_KEYS = {"artifact_type", "schema_version", "workflow_id", "structured_data_usage"}
RETIRED_CEREMONY = (
    "quest_awareness",
    "control_decision",
    "confidence_percent",
    "confidence_delta",
    "confidence_threshold",
    "skip_reason_required_when_not_used",
    "cost_reason",
    "extra_file_reads",
    "validation_iterations",
    "advisor_consultation",
    "consideration_required",
)


def _doc(rel: str, body_key: str) -> tuple[dict[str, object], dict[str, object]]:
    document = mapping(load_yaml(rel), rel)
    validate_template_metadata(document, rel)
    require(set(document) == TEMPLATE_ROOT_KEYS | {body_key}, f"{rel} の top-level key が compact contract と一致しません。")
    return document, mapping(document.get(body_key), f"{rel}.{body_key}")


def _keys(value: dict[str, object], expected: set[str], label: str) -> None:
    require(set(value) == expected, f"{label} の key が compact contract と一致しません。")


def _read_only(authority: object, label: str, *, validate: bool = False) -> None:
    validate_authority(authority, label)
    require(
        mapping(authority, label)
        == {"read": True, "edit": False, "validate": validate, "local_git": False, "external_actions": False},
        f"{label} は限定 read-only authority にしてください。",
    )


def _bounded_snapshot_authority(body: dict[str, object], label: str) -> None:
    validate_subject_snapshot(body.get("subject_snapshot"), f"{label}.subject_snapshot")
    validate_authority(body.get("authority"), f"{label}.authority")
    validate_boundaries(body.get("boundaries"), f"{label}.boundaries")


def validate_queue_templates() -> None:
    for rel in QUEUE_TEMPLATE_PATHS:
        text = read(rel)
        for token in RETIRED_CEREMONY:
            require(token not in text, f"{rel} に廃止した model-facing ceremony `{token}` が残っています。")
        for token in VOCABULARY_DRIFT_TERMS:
            require(token not in text, f"{rel} に表記揺れ `{token}` が残っています。")

    request_text = read("template/.agents/orchestra/queue/templates/request.yaml")
    require("evidence_state:" in request_text and "subject_snapshot:" in request_text, "request example は compact evidence_state と helper snapshot を参照してください。")
    command_text = read("template/.agents/orchestra/queue/templates/command.yaml")
    require("subject_snapshot:" in command_text and "cgo-snapshot-v1" in command_text, "command example は canonical subject snapshot を参照してください。")
    require(all(token in command_text for token in ("integration_contract:", "integration_owner:", "mutation_barrier_required:", "required_assignment_ids:", "required_report_refs:", "integration_scope:")), "command example はintegration前にrequired集合とintegration scopeを固定してください。")

    _, assignment = _doc("template/.agents/orchestra/queue/templates/adventurer_assignment.yaml", "assignment")
    _keys(
        assignment,
        {
            "id", "quest_id", "worker_id", "role", "terminal_worker", "objective", "success_criteria",
            "owned_scope", "integration_barrier", "authority", "boundaries", "subject_snapshot", "evidence_state",
            "validation_expectations", "risks", "evidence_refs", "status", "timestamp",
        },
        "adventurer_assignment.assignment",
    )
    require(assignment.get("worker_id") in {"adventurer", "integration_owner"}, "implementation assignment の worker_id が不正です。")
    require(assignment.get("role") in {"bounded_implementation_owner", "cross_scope_integration_owner"}, "implementation role はworker contractと一致させてください。")
    require(assignment.get("terminal_worker") is True, "adventurer は recursive delegation しない terminal worker にしてください。")
    _bounded_snapshot_authority(assignment, "adventurer_assignment.assignment")
    validate_evidence_state(assignment.get("evidence_state"), "adventurer_assignment.assignment.evidence_state")
    owned_scope = mapping(assignment.get("owned_scope"), "adventurer_assignment.assignment.owned_scope")
    _keys(owned_scope, {"read", "edit", "validate"}, "adventurer_assignment.assignment.owned_scope")
    for key in owned_scope:
        sequence(owned_scope[key], f"adventurer_assignment.assignment.owned_scope.{key}")

    _, adventurer_report = _doc("template/.agents/orchestra/queue/templates/adventurer_report.yaml", "report")
    _keys(
        adventurer_report,
        {
            "id", "quest_id", "assignment_id", "worker_id", "target_repo_root", "status", "summary",
            "changed_files", "decisions_made", "evidence_state", "validation_evidence", "base_snapshot",
            "result_snapshot", "risks", "evidence_refs", "timestamp",
        },
        "adventurer_report.report",
    )
    require(adventurer_report.get("worker_id") in {"adventurer", "integration_owner"}, "implementation report worker_id が不正です。")
    validate_evidence_state(adventurer_report.get("evidence_state"), "adventurer_report.report.evidence_state")
    validate_subject_snapshot(adventurer_report.get("base_snapshot"), "adventurer_report.report.base_snapshot")
    validate_subject_snapshot(adventurer_report.get("result_snapshot"), "adventurer_report.report.result_snapshot")

    _, cart_assignment = _doc("template/.agents/orchestra/queue/templates/cartographer_assignment.yaml", "assignment")
    _keys(
        cart_assignment,
        {
            "id", "quest_id", "worker_id", "role", "kind", "terminal_worker", "objective", "success_criteria",
            "focus", "authority", "boundaries", "subject_snapshot", "evidence_state", "evidence_required",
            "risks", "status", "timestamp",
        },
        "cartographer_assignment.assignment",
    )
    require(cart_assignment.get("worker_id") == "cartographer" and cart_assignment.get("kind") == "mapmaking", "cartographer identity が不正です。")
    require(cart_assignment.get("terminal_worker") is True, "cartographer は terminal worker にしてください。")
    _bounded_snapshot_authority(cart_assignment, "cartographer_assignment.assignment")
    _read_only(cart_assignment.get("authority"), "cartographer_assignment.assignment.authority")
    validate_evidence_state(cart_assignment.get("evidence_state"), "cartographer_assignment.assignment.evidence_state")

    _, cart_report = _doc("template/.agents/orchestra/queue/templates/cartographer_report.yaml", "report")
    _keys(
        cart_report,
        {
            "id", "quest_id", "assignment_id", "worker_id", "target_repo_root", "status", "objective", "summary",
            "terrain_map", "recommendation", "recommended_owner_role", "recommended_trial_depth", "evidence_state",
            "subject_snapshot", "risks", "evidence_refs", "timestamp",
        },
        "cartographer_report.report",
    )
    validate_evidence_state(cart_report.get("evidence_state"), "cartographer_report.report.evidence_state")
    validate_subject_snapshot(cart_report.get("subject_snapshot"), "cartographer_report.report.subject_snapshot")

    _, advisor = _doc("template/.agents/orchestra/queue/templates/advisor_assignment.yaml", "assignment")
    _keys(
        advisor,
        {
            "id", "quest_id", "parent_id", "worker_id", "role", "kind", "owner_worker_id",
            "owner_assignment_id", "terminal_worker", "decision_authority", "objective", "focus",
            "evidence_required", "stop_conditions", "subject_snapshot", "authority", "boundaries", "risks",
            "status", "timestamp",
        },
        "advisor_assignment.assignment",
    )
    require(advisor.get("worker_id") == "advisor" and advisor.get("kind") == "advisory_consultation", "advisor identity が不正です。")
    require(advisor.get("role") == "independent_focus_advisor", "advisor role はworker contractと一致させてください。")
    require(advisor.get("terminal_worker") is True and advisor.get("decision_authority") is False, "advisor は terminal / non-decision worker にしてください。")
    _bounded_snapshot_authority(advisor, "advisor_assignment.assignment")
    _read_only(advisor.get("authority"), "advisor_assignment.assignment.authority")
    require(
        {"focus_resolved", "no_new_verifiable_evidence", "authority_or_boundary_would_expand", "human_confirmation_required"}
        <= set(sequence(advisor.get("stop_conditions"), "advisor_assignment.assignment.stop_conditions")),
        "advisor stop conditions は evidence/focus/authority で停止できる必要があります。",
    )

    _, advisor_report = _doc("template/.agents/orchestra/queue/templates/advisor_report.yaml", "report")
    _keys(
        advisor_report,
        {
            "id", "quest_id", "assignment_id", "worker_id", "owner_worker_id", "target_repo_root", "status",
            "terminal_worker", "decision_authority", "focus", "summary", "findings", "evidence_refs",
            "important_unknowns", "risks", "recommended_next_action", "subject_snapshot", "timestamp",
        },
        "advisor_report.report",
    )
    require(advisor_report.get("terminal_worker") is True and advisor_report.get("decision_authority") is False, "advisor report は non-decision terminal contract を維持してください。")
    validate_subject_snapshot(advisor_report.get("subject_snapshot"), "advisor_report.report.subject_snapshot")

    _, focus = _doc("template/.agents/orchestra/queue/templates/focus_reviewer_assignment.yaml", "assignment")
    _keys(
        focus,
        {
            "id", "quest_id", "trial_id", "worker_id", "owner_worker_id", "role", "terminal_worker",
            "decision_authority", "severity_authority", "objective", "caller_lineage", "risk_trigger", "focus", "subject_snapshot",
            "authority", "boundaries", "evidence_required", "forbidden", "status", "timestamp",
        },
        "focus_reviewer_assignment.assignment",
    )
    require(focus.get("worker_id") == "focus_reviewer" and focus.get("owner_worker_id") == "inquisitor", "focus reviewer lineage identity が不正です。")
    require(focus.get("terminal_worker") is True and focus.get("decision_authority") is False and focus.get("severity_authority") is False, "focus reviewer authority flags が不正です。")
    lineage = mapping(focus.get("caller_lineage"), "focus_reviewer_assignment.assignment.caller_lineage")
    _keys(lineage, {"required_parent_role", "trial_owner_worker_id", "trial_ref", "verification"}, "focus_reviewer_assignment.assignment.caller_lineage")
    require(lineage.get("required_parent_role") == "inquisitor" and lineage.get("trial_owner_worker_id") == "inquisitor", "focus reviewer は inquisitor lineage に限定してください。")
    _bounded_snapshot_authority(focus, "focus_reviewer_assignment.assignment")
    _read_only(focus.get("authority"), "focus_reviewer_assignment.assignment.authority", validate=True)

    _, focus_report = _doc("template/.agents/orchestra/queue/templates/focus_reviewer_report.yaml", "report")
    _keys(
        focus_report,
        {
            "id", "quest_id", "trial_id", "assignment_id", "worker_id", "owner_worker_id", "terminal_worker",
            "decision_authority", "severity_authority", "caller_lineage_check", "risk_trigger", "focus",
            "subject_snapshot", "snapshot_check", "summary", "finding_candidates", "evidence_refs",
            "important_unknowns", "residual_risks", "status", "timestamp",
        },
        "focus_reviewer_report.report",
    )
    require(focus_report.get("terminal_worker") is True and focus_report.get("decision_authority") is False and focus_report.get("severity_authority") is False, "focus reviewer report authority flags が不正です。")
    caller_check = mapping(focus_report.get("caller_lineage_check"), "focus_reviewer_report.report.caller_lineage_check")
    _keys(caller_check, {"required_parent_role", "trial_owner_worker_id", "trial_ref", "verified", "status"}, "focus_reviewer_report.report.caller_lineage_check")
    require(caller_check.get("status") in {None, "verified", "invalid_assignment", "unverifiable"}, "focus reviewer lineage status が不正です。")
    validate_subject_snapshot(focus_report.get("subject_snapshot"), "focus_reviewer_report.report.subject_snapshot")
    snapshot_check = mapping(focus_report.get("snapshot_check"), "focus_reviewer_report.report.snapshot_check")
    _keys(snapshot_check, {"start_match", "report_match", "status"}, "focus_reviewer_report.report.snapshot_check")
    require(snapshot_check.get("status") in {None, "matched", "stale_evidence", "invalid_assignment"}, "focus reviewer snapshot status が不正です。")

    _, trial = _doc("template/.agents/orchestra/queue/templates/inquisitor_trial.yaml", "trial")
    _keys(
        trial,
        {
            "id", "quest_id", "worker_id", "role", "depth", "objective", "success_criteria",
            "subject_assignment_ids", "subject_report_ids", "changed_files", "subject_snapshot", "authority",
            "boundaries", "evidence_state", "core_checks", "risk_triggered_checks", "advisor_assignments",
            "reviewer_assignments", "decision_options", "evidence_required", "status", "timestamp",
        },
        "inquisitor_trial.trial",
    )
    require(trial.get("worker_id") == "inquisitor" and trial.get("role") == "trial_lead", "Trial worker/role は inquisitor/trial_lead にしてください。")
    _bounded_snapshot_authority(trial, "inquisitor_trial.trial")
    _read_only(trial.get("authority"), "inquisitor_trial.trial.authority", validate=True)
    validate_evidence_state(trial.get("evidence_state"), "inquisitor_trial.trial.evidence_state")
    require(set(sequence(trial.get("core_checks"), "inquisitor_trial.trial.core_checks")) == CORE_TRIAL_CHECKS, "Trial core checks は常時必要な6観点だけにしてください。")

    _, trial_report = _doc("template/.agents/orchestra/queue/templates/inquisitor_report.yaml", "report")
    _keys(
        trial_report,
        {
            "id", "quest_id", "trial_id", "worker_id", "target_repo_root", "status", "decision", "summary",
            "trial_depth", "subject_snapshot", "evidence_state", "findings", "validation_evidence", "advisor_reports",
            "reviewer_reports", "finding_dispositions", "risks", "requested_changes", "evidence_refs", "timestamp",
        },
        "inquisitor_report.report",
    )
    validate_subject_snapshot(trial_report.get("subject_snapshot"), "inquisitor_report.report.subject_snapshot")
    validate_evidence_state(trial_report.get("evidence_state"), "inquisitor_report.report.evidence_state")

    _, sentinel = _doc("template/.agents/orchestra/queue/templates/quest_sentinel_assignment.yaml", "assignment")
    _keys(
        sentinel,
        {
            "id", "quest_id", "parent_id", "owner_assignment_id", "owner_worker_id", "worker_id", "role", "kind",
            "terminal_worker", "decision_authority", "control_trigger", "objective", "evidence_state", "output_contract",
            "subject_snapshot", "authority", "boundaries", "evidence_required", "risks", "status", "timestamp",
        },
        "quest_sentinel_assignment.assignment",
    )
    require(sentinel.get("worker_id") == "quest_sentinel" and sentinel.get("kind") == "evidence_state_monitor", "quest_sentinel は exceptional evidence-state monitor にしてください。")
    require(sentinel.get("role") == "exceptional_control_diagnostician", "quest_sentinel role はworker contractと一致させてください。")
    require(sentinel.get("terminal_worker") is True and sentinel.get("decision_authority") is False, "quest_sentinel は non-decision terminal worker にしてください。")
    _bounded_snapshot_authority(sentinel, "quest_sentinel_assignment.assignment")
    _read_only(sentinel.get("authority"), "quest_sentinel_assignment.assignment.authority")
    validate_evidence_state(sentinel.get("evidence_state"), "quest_sentinel_assignment.assignment.evidence_state")
    require(mapping(sentinel.get("output_contract"), "quest_sentinel_assignment.assignment.output_contract") == {"evidence_state_only": True, "hidden_reasoning_allowed": False}, "quest_sentinel output contract が不正です。")

    for rel in (
        "template/.agents/orchestra/queue/templates/adventurer_inbox.yaml",
        "template/.agents/orchestra/queue/templates/role_inbox.yaml",
    ):
        document = mapping(load_yaml(rel), rel)
        validate_template_metadata(document, rel)
        require(set(document) == TEMPLATE_ROOT_KEYS | {"messages"}, f"{rel} の top-level key が compact contract と一致しません。")
        sequence(document.get("messages"), f"{rel}.messages")
