"""再利用する schema 検証 helper。"""

from __future__ import annotations

from .core import mapping, require, sequence
from .rules import (
    ARTIFACT_REQUIRED_FIELDS,
    AUTHORITY_KEYS,
    AUTONOMY_KEYS,
    CONTROL_DECISION_KEYS,
    CONTROL_DECISIONS,
    QUEST_AWARENESS_KEYS,
    STRUCTURED_DATA_USAGE_FIELDS,
)

def validate_template_metadata(document: dict[str, object], rel: str) -> None:
    for key in ARTIFACT_REQUIRED_FIELDS:
        require(key in document, f"{rel} に {key} が必要です。")
    require(document["schema_version"] == "3.0", f"{rel}.schema_version は 3.0 にしてください。")
    usage = mapping(document.get("structured_data_usage"), f"{rel}.structured_data_usage")
    for key in STRUCTURED_DATA_USAGE_FIELDS:
        require(key in usage, f"{rel}.structured_data_usage.{key} が必要です。")


def validate_authority(value: object, label: str) -> None:
    authority = mapping(value, label)
    require(set(authority) == AUTHORITY_KEYS, f"{label} は authority key と一致させてください。")
    for key in AUTHORITY_KEYS:
        require(isinstance(authority[key], bool), f"{label}.{key} は bool にしてください。")


def validate_boundaries(value: object, label: str) -> None:
    boundaries = mapping(value, label)
    for key in ("target_repo_root", "read_deny", "edit_deny", "safety_items"):
        require(key in boundaries, f"{label}.{key} が必要です。")
    for key in ("read_deny", "edit_deny", "safety_items"):
        sequence(boundaries[key], f"{label}.{key}")


def validate_autonomy_budget(value: object, label: str) -> None:
    budget = mapping(value, label)
    require(set(budget) == AUTONOMY_KEYS, f"{label} は autonomy_budget key と一致させてください。")
    for key in AUTONOMY_KEYS - {"timebox_minutes"}:
        require(isinstance(budget[key], int) and not isinstance(budget[key], bool) and budget[key] >= 0, f"{label}.{key} は 0 以上の整数にしてください。")
    require(budget["timebox_minutes"] is None or isinstance(budget["timebox_minutes"], int), f"{label}.timebox_minutes は null または整数にしてください。")


def validate_quest_awareness(value: object, label: str) -> None:
    state = mapping(value, label)
    require(set(state) == QUEST_AWARENESS_KEYS, f"{label} は quest_awareness key と一致させてください。")
    for key in ("known_facts", "unknowns", "assumptions", "evidence"):
        sequence(state[key], f"{label}.{key}")
    require(state.get("risk_level") in {"low", "medium", "high", None}, f"{label}.risk_level は low / medium / high / null にしてください。")
    require(state.get("verification_status") in {"not_checked", "partially_checked", "verified", "failed", None}, f"{label}.verification_status が不正です。")
    confidence = state.get("confidence_percent")
    require(confidence is None or (isinstance(confidence, int) and not isinstance(confidence, bool) and 0 <= confidence <= 100), f"{label}.confidence_percent は null または 0..100 の整数にしてください。")


def validate_control_decision(value: object, label: str) -> None:
    decision = mapping(value, label)
    require(set(decision) == CONTROL_DECISION_KEYS, f"{label} は control_decision key と一致させてください。")
    require(decision.get("decision") in CONTROL_DECISIONS | {None}, f"{label}.decision が不正です。")
    sequence(decision.get("triggers"), f"{label}.triggers")
    require(isinstance(decision.get("escalation_required"), bool), f"{label}.escalation_required は bool にしてください。")


def validate_percent(value: object, label: str) -> None:
    require(isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 100, f"{label} は 1 から 100 の整数にしてください。")


def validate_dialogue_policy(value: object, label: str) -> None:
    dialogue = mapping(value, label)
    require(dialogue.get("mode") == "confidence_based", f"{label}.mode は confidence_based にしてください。")
    require(dialogue.get("same_focus_only") is True, f"{label}.same_focus_only は true にしてください。")
    require(dialogue.get("owner_controls_confidence") is True, f"{label}.owner_controls_confidence は true にしてください。")
    require(dialogue.get("raw_discussion_ledger_policy") == "do_not_record", f"{label}.raw_discussion_ledger_policy は do_not_record にしてください。")
    continue_when = set(sequence(dialogue.get("continue_when"), f"{label}.continue_when"))
    require({"owner_confidence_below_target", "new_evidence_added", "confidence_delta_meets_minimum", "blocking_unknowns_decreased"} <= continue_when, f"{label}.continue_when が不足しています。")
    stop_when = set(sequence(dialogue.get("stop_when"), f"{label}.stop_when"))
    require(
        {
            "confidence_target_met",
            "no_new_evidence_added",
            "confidence_delta_below_minimum",
            "blocking_unknowns_unchanged",
            "same_unknown_repeated",
            "advisor_cannot_add_verifiable_evidence",
            "owner_cannot_verify_advisor_basis",
            "authority_or_boundary_would_expand",
            "human_confirmation_required",
            "advisor_focus_would_drift",
        }
        <= stop_when,
        f"{label}.stop_when が不足しています。",
    )


def validate_compat_context(value: object, label: str) -> None:
    entries = sequence(value, label)
    require(entries, f"{label} は Claude 互換 context disposition の雛形を含めてください。")
    for index, value_entry in enumerate(entries):
        entry_label = f"{label}[{index}]"
        entry = mapping(value_entry, entry_label)
        for key in ("source_type", "path", "sha256", "trust", "applies_to", "status", "disposition", "skip_reason"):
            require(key in entry, f"{entry_label}.{key} が必要です。")
        for key in ("content", "rendered_context", "settings", "raw_content"):
            require(key not in entry, f"{entry_label} に raw payload key `{key}` を含めないでください。")
        require(entry.get("source_type") == "claude", f"{entry_label}.source_type は claude にしてください。")
        require(entry.get("trust") == "untrusted", f"{entry_label}.trust は untrusted にしてください。")
