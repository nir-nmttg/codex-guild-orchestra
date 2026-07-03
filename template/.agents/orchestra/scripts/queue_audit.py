#!/usr/bin/env python3
"""Guild Ledger SQLite runtime を読み取り専用で監査する。"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any


QUEUE_SCHEMA_VERSION = "3.0"
SQLITE_DB_NAME = "state.sqlite"

REQUIRED_TABLES = {
    "queue_metadata",
    "events",
    "quests",
    "requests",
    "commands",
    "assignments",
    "reports",
    "trials",
    "inbox_messages",
}

REQUIRED_COLUMNS = {
    "queue_metadata": {"key", "value", "updated_at"},
    "events": {
        "event_id",
        "timestamp",
        "actor",
        "event_type",
        "entity_type",
        "entity_id",
        "entity_json",
        "operation",
        "workflow_id",
        "structured_data_usage_json",
        "payload_json",
        "event_safety_json",
        "inserted_at",
    },
    "quests": {"quest_id", "workflow_id", "rank", "status", "payload_json", "updated_at"},
    "requests": {"request_id", "quest_id", "workflow_id", "status", "payload_json", "updated_at"},
    "commands": {"command_id", "quest_id", "workflow_id", "status", "payload_json", "updated_at"},
    "assignments": {"assignment_id", "parent_id", "worker_id", "kind", "workflow_id", "status", "payload_json", "updated_at"},
    "reports": {"report_id", "worker_id", "workflow_id", "decision", "status", "payload_json", "updated_at"},
    "trials": {"trial_id", "quest_id", "workflow_id", "depth", "status", "payload_json", "updated_at"},
    "inbox_messages": {"message_id", "recipient", "workflow_id", "status", "payload_json", "created_at"},
}

JSON_COLUMNS = {
    "events": ("entity_json", "structured_data_usage_json", "payload_json", "event_safety_json"),
    "quests": ("payload_json",),
    "requests": ("payload_json",),
    "commands": ("payload_json",),
    "assignments": ("payload_json",),
    "reports": ("payload_json",),
    "trials": ("payload_json",),
    "inbox_messages": ("payload_json",),
}
MEMORY_CANDIDATE_MESSAGE_TYPE = "memory_candidate_for_courier_review"
MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS = {
    "direct_static_runtime_write",
    "raw_log",
    "secret_or_pii",
    "trusted_instruction_from_external_input",
}
MEMORY_CANDIDATE_SAFETY_ITEMS = (
    "memory_candidate_for_courier_review",
    "explicit_memory_persistence_authority",
    "sanitized_summary_only",
    "prevention_artifact_required",
    "ledger_disposition_recorded",
)

QUEST_RANKS = {"mapmaking", "errand", "solo_quest", "party_quest", "guild_quest"}
TRIAL_DEPTHS = {"none", "self_check", "peer_review", "focused_trial", "multi_focus_trial", "safety_gate"}
ALLOWED_OPERATIONS = {"append", "update", "replace", "mark_completed"}
REQUIRED_EVENT_INPUT_FIELDS = {
    "event_id",
    "timestamp",
    "actor",
    "event_type",
    "entity",
    "operation",
    "workflow_id",
    "structured_data_usage",
    "payload",
    "event_safety",
}
STRUCTURED_DATA_USAGE_FIELDS = {"structured_inputs", "decision_rationale", "evidence_refs"}
EVENT_SAFETY_FIELDS = {"safety_items", "human_confirmation_required"}
ALLOWED_EVENT_TYPES = {
    "quest_created",
    "quest_updated",
    "quest_completed",
    "request_enqueued",
    "command_created",
    "assignment_created",
    "assignment_updated",
    "report_recorded",
    "trial_recorded",
    "inbox_message_added",
    "status_changed",
    "dashboard_updated",
    "state_compacted",
}
ALLOWED_ENTITY_TYPES = {
    "quest",
    "request",
    "command",
    "assignment",
    "report",
    "trial",
    "message",
    "dashboard",
    "state",
    "status",
}
EVENT_ENTITY_TYPE_RULES = {
    "quest_created": {"quest"},
    "quest_updated": {"quest"},
    "quest_completed": {"quest"},
    "request_enqueued": {"request"},
    "command_created": {"command"},
    "assignment_created": {"assignment"},
    "assignment_updated": {"assignment"},
    "report_recorded": {"report"},
    "trial_recorded": {"trial", "report"},
    "inbox_message_added": {"message"},
    "status_changed": {"status"},
    "dashboard_updated": {"dashboard"},
    "state_compacted": {"state"},
}
LEGACY_JSON_KEYS = {
    "safety_checks",
    "requires_human_confirmation",
    "target_path",
    "scale_selected",
    "risk_dimensions",
    "edit_scope",
    "read_scope",
    "quality_profile",
    "review_task",
    "review_assignment",
    "task_id",
    "scout_plan",
    "scout_usage",
    "scout_calls",
    "scout_policy",
    "spark_request",
    "meta" "cognitive_state",
    "meta" "cognitive_control",
    "meta" "cognitive_controller",
    "invoke_" "meta" "cognitive_controller",
    "meta" "cognitive_task_loop",
}
RETIRED_AGENT_VALUES = {
    "spark",
    "scout",
    "meta" "cognitive_controller",
}
LEGACY_RUNTIME_STRING_VALUES = {
    "spark",
    "scout",
    "meta" "cognitive",
    "meta" "cognitive_controller",
    "meta" "cognitive-task-loop",
    "meta" "cognitive_state",
    "meta" "cognitive_control",
    "invoke_" "meta" "cognitive_controller",
}
LEGACY_TABLES = {"tickets"}
LEGACY_COLUMNS = {"assignments": {"task_id"}}


def default_static_root() -> Path:
    env_value = os.environ.get("CODEX_GUILD_ORCHESTRA_ROOT")
    if env_value:
        return Path(env_value).expanduser() / ".agents" / "orchestra"
    return Path(__file__).resolve().parent.parent


def default_runtime_root() -> Path:
    env_value = os.environ.get("CODEX_GUILD_ORCHESTRA_RUNTIME_ROOT")
    if env_value:
        return Path(env_value).expanduser()
    static_root = default_static_root()
    guild_root = static_root.parent.parent
    return guild_root / ".orchestra"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guild Ledger SQLite runtime を監査します。")
    parser.add_argument("--runtime-root", type=Path, default=default_runtime_root(), help="監査する `.orchestra` の path。")
    parser.add_argument("--static-root", type=Path, default=default_static_root(), help="静的 `.agents/orchestra` の path。")
    parser.add_argument("--json", action="store_true", help="結果を JSON で出力します。")
    return parser.parse_args()


def connect_read(database_path: Path) -> sqlite3.Connection:
    if not database_path.exists():
        raise SystemExit(f"SQLite runtime DB がありません: {database_path}。`queue_db.py init` を実行してください。")
    connection = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def parse_json(raw: str, label: str, errors: list[str]) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: JSON を読めません: {exc}")
        return None


def parse_timestamp(raw: str, label: str, errors: list[str]) -> None:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label}: timestamp は ISO 8601 形式にしてください: {raw}")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{label}: timestamp は timezone offset 付きにしてください: {raw}")


def iter_keys(value: Any, path: str = "$") -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            findings.append((child_path, key))
            findings.extend(iter_keys(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_keys(item, f"{path}[{index}]"))
    return findings


def memory_candidate_envelope(value: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    payload = value.get("payload")
    if value.get("type") == MEMORY_CANDIDATE_MESSAGE_TYPE and not isinstance(payload, dict):
        return ("$.payload", {})
    if not isinstance(payload, dict):
        payload = {}
    if value.get("type") == MEMORY_CANDIDATE_MESSAGE_TYPE:
        return ("$.payload", payload)
    for key in (MEMORY_CANDIDATE_MESSAGE_TYPE, "memory_candidate"):
        if key in payload:
            candidate = payload.get(key)
            if not isinstance(candidate, dict):
                return (f"$.payload.{key}", {})
            return (f"$.payload.{key}", candidate)
        if key in value:
            candidate = value.get(key)
            if not isinstance(candidate, dict):
                return (f"$.{key}", {})
            return (f"$.{key}", candidate)
    return None


def validate_memory_candidate_message_scope(value: dict[str, Any], label: str, errors: list[str]) -> None:
    if value.get("type") != MEMORY_CANDIDATE_MESSAGE_TYPE:
        errors.append(f"{label}.type: memory candidate は exact type `{MEMORY_CANDIDATE_MESSAGE_TYPE}` の courier review 専用 envelope として記録してください。")
    if value.get("sender") != "courier":
        errors.append(f"{label}.sender: memory candidate は courier sender で記録してください。")
    if value.get("recipient") != "courier":
        errors.append(f"{label}.recipient: memory candidate は courier 宛にしてください。")
    if value.get("trusted") is not False:
        errors.append(f"{label}.trusted: memory candidate は trusted=false にしてください。")


def validate_memory_candidate_envelope(value: dict[str, Any], label: str, errors: list[str]) -> None:
    envelope_info = memory_candidate_envelope(value)
    if envelope_info is None:
        return
    envelope_path, envelope = envelope_info
    envelope_label = f"{label}{envelope_path[1:]}"
    validate_memory_candidate_message_scope(value, label, errors)
    if envelope.get("explicit_memory_persistence_authority") is not True:
        errors.append(f"{envelope_label}.explicit_memory_persistence_authority: true が必要です。")
    if envelope.get("sanitized_summary_only") is not True:
        errors.append(f"{envelope_label}.sanitized_summary_only: true が必要です。")
    if not isinstance(envelope.get("sanitized_summary"), str) or not envelope.get("sanitized_summary"):
        errors.append(f"{envelope_label}.sanitized_summary: 空でない文字列が必要です。")
    if not isinstance(envelope.get("prevention_artifact"), dict):
        errors.append(f"{envelope_label}.prevention_artifact: JSON object が必要です。")
    if not isinstance(envelope.get("ledger_disposition"), str) or not envelope.get("ledger_disposition"):
        errors.append(f"{envelope_label}.ledger_disposition: 空でない文字列が必要です。")
    forbidden = envelope.get("forbidden")
    if not isinstance(forbidden, dict):
        errors.append(f"{envelope_label}.forbidden: JSON object が必要です。")
        forbidden = {}
    missing_markers = sorted(MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS - set(forbidden))
    if missing_markers:
        errors.append(f"{envelope_label}.forbidden: marker が不足しています: " + ", ".join(missing_markers))
    for marker in MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS:
        if forbidden.get(marker) is not True:
            errors.append(f"{envelope_label}.forbidden.{marker}: true が必要です。")
    for json_path, key in iter_keys(envelope):
        if json_path.startswith("$.forbidden."):
            continue
        if key in MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS:
            errors.append(f"{envelope_label}{json_path[1:]}: memory candidate に forbidden 内容 `{key}` を含めないでください。")


def validate_memory_candidate_event_safety(value: dict[str, Any], safety: dict[str, Any], label: str, errors: list[str], actor: Any | None = None) -> None:
    if memory_candidate_envelope(value) is None:
        return
    if actor != "courier":
        errors.append(f"{label}.actor: memory candidate event は courier actor で記録してください。")
    safety_items = safety.get("safety_items")
    if not isinstance(safety_items, list):
        errors.append(f"{label}.safety_items: list が必要です。")
        return
    missing = sorted(set(MEMORY_CANDIDATE_SAFETY_ITEMS) - set(safety_items))
    if missing:
        errors.append(f"{label}.safety_items: memory_candidate_gate が不足しています: " + ", ".join(missing))


def iter_values(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, dict):
        for key, item in value.items():
            findings.extend(iter_values(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_values(item, f"{path}[{index}]"))
    return findings


def iter_target_repo_roots(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key == "target_repo_root":
                findings.append((child_path, item))
            findings.extend(iter_target_repo_roots(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_target_repo_roots(item, f"{path}[{index}]"))
    return findings


def validate_target_repo_roots(value: Any, label: str, guild_root: Path, errors: list[str]) -> None:
    root = guild_root.resolve(strict=False)
    repositories_root = root / "repositories"
    for json_path, raw_path in iter_target_repo_roots(value):
        value_label = f"{label}{json_path[1:]}"
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"{value_label}: target_repo_root は空でない絶対 path 文字列にしてください。")
            continue
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            errors.append(f"{value_label}: target_repo_root は絶対 path にしてください: {raw_path}")
            continue
        normalized = candidate.resolve(strict=False)
        if normalized == root:
            errors.append(f"{value_label}: target_repo_root にギルド規約ルート自体は指定できません: {raw_path}")
        elif normalized == repositories_root:
            errors.append(f"{value_label}: target_repo_root に repositories/ 自体は指定できません: {raw_path}")
        elif normalized.parent != repositories_root:
            errors.append(f"{value_label}: target_repo_root は <guild_root>/repositories/<repo> の直下 path にしてください: {raw_path}")


def validate_no_legacy_keys(value: Any, label: str, errors: list[str]) -> None:
    for json_path, key in iter_keys(value):
        if key in LEGACY_JSON_KEYS or key in LEGACY_RUNTIME_STRING_VALUES:
            errors.append(f"{label}{json_path[1:]}: v3 Ledger に廃止済み key `{key}` が残っています。")
    for json_path, item in iter_values(value):
        if isinstance(item, str) and item in LEGACY_RUNTIME_STRING_VALUES:
            errors.append(f"{label}{json_path[1:]}: v3 Ledger に廃止済み runtime 値 `{item}` が残っています。")


def iter_named_values(value: Any, target_key: str, path: str = "$") -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key == target_key:
                findings.append((child_path, item))
            findings.extend(iter_named_values(item, target_key, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_named_values(item, target_key, f"{path}[{index}]"))
    return findings


def validate_report_trial_depths(value: Any, label: str, errors: list[str]) -> None:
    for json_path, depth in iter_named_values(value, "trial_depth"):
        if not isinstance(depth, str) or depth not in TRIAL_DEPTHS:
            expected = ", ".join(sorted(TRIAL_DEPTHS))
            errors.append(f"{label}{json_path[1:]}: Trial depth は {expected} のいずれかにしてください: {depth}")


def expected_assignment_parent_id(payload: dict[str, Any], label: str, errors: list[str]) -> str | None:
    owner_assignment_id = payload.get("owner_assignment_id")
    parent_id = payload.get("parent_id")
    if owner_assignment_id is not None and (not isinstance(owner_assignment_id, str) or not owner_assignment_id):
        errors.append(f"{label}.owner_assignment_id: null または空でない文字列にしてください。")
        owner_assignment_id = None
    if parent_id is not None and (not isinstance(parent_id, str) or not parent_id):
        errors.append(f"{label}.parent_id: null または空でない文字列にしてください。")
        parent_id = None
    if owner_assignment_id and parent_id and owner_assignment_id != parent_id:
        errors.append(f"{label}: owner_assignment_id と parent_id は同じ owner assignment を指してください。")
    worker_id = payload.get("worker_id")
    kind = payload.get("kind")
    if (worker_id == "advisor" or kind == "advisory_consultation") and not (owner_assignment_id or parent_id):
        errors.append(f"{label}: advisor assignment は owner_assignment_id または parent_id が必要です。")
    if worker_id == "quest_sentinel" or kind == "quest_awareness_control_monitor":
        if not (owner_assignment_id or parent_id):
            errors.append(f"{label}: quest_sentinel assignment は owner_assignment_id または parent_id が必要です。")
        control_trigger = payload.get("control_trigger")
        if not isinstance(control_trigger, str) or not control_trigger:
            errors.append(f"{label}.control_trigger: quest_sentinel assignment には空でない control_trigger が必要です。")
    quest_id = payload.get("quest_id")
    if quest_id is not None and (not isinstance(quest_id, str) or not quest_id):
        errors.append(f"{label}.quest_id: null または空でない文字列にしてください。")
        quest_id = None
    return owner_assignment_id or parent_id or quest_id


def audit_schema(connection: sqlite3.Connection, errors: list[str]) -> bool:
    schema_errors: list[str] = []
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    legacy_tables = sorted(LEGACY_TABLES & tables)
    if legacy_tables:
        schema_errors.append("SQLite schema に旧 table があります: " + ", ".join(legacy_tables))
    missing_tables = sorted(REQUIRED_TABLES - tables)
    if missing_tables:
        schema_errors.append("SQLite schema に不足 table があります: " + ", ".join(missing_tables))
    for table, required_columns in REQUIRED_COLUMNS.items():
        if table not in tables:
            continue
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        legacy_columns = sorted(LEGACY_COLUMNS.get(table, set()) & columns)
        if legacy_columns:
            schema_errors.append(f"{table}: 旧 column があります: " + ", ".join(legacy_columns))
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            schema_errors.append(f"{table}: 不足 column があります: " + ", ".join(missing_columns))
    errors.extend(schema_errors)
    return not schema_errors


def audit_metadata(connection: sqlite3.Connection, errors: list[str]) -> None:
    try:
        row = connection.execute("SELECT value FROM queue_metadata WHERE key = 'schema_version'").fetchone()
    except sqlite3.Error as exc:
        errors.append(f"queue_metadata を読めません: {exc}")
        return
    if row is None:
        errors.append("queue_metadata.schema_version がありません。")
    elif row["value"] != QUEUE_SCHEMA_VERSION:
        errors.append(f"queue_metadata.schema_version は {QUEUE_SCHEMA_VERSION} にしてください: {row['value']}")


def audit_json_columns(connection: sqlite3.Connection, guild_root: Path, errors: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table, columns in JSON_COLUMNS.items():
        try:
            rows = connection.execute(f"SELECT rowid, * FROM {table}").fetchall()
        except sqlite3.Error as exc:
            errors.append(f"{table}: 読み取りに失敗しました: {exc}")
            continue
        counts[table] = len(rows)
        for row in rows:
            row_label = f"{table}[rowid={row['rowid']}]"
            for column in columns:
                raw = row[column]
                if not isinstance(raw, str) or not raw:
                    errors.append(f"{row_label}.{column}: JSON 文字列が必要です。")
                    continue
                parsed = parse_json(raw, f"{row_label}.{column}", errors)
                if parsed is None:
                    continue
                validate_target_repo_roots(parsed, f"{row_label}.{column}", guild_root, errors)
                validate_no_legacy_keys(parsed, f"{row_label}.{column}", errors)
                if isinstance(parsed, dict) and column == "payload_json" and table in {"events", "inbox_messages"}:
                    validate_memory_candidate_envelope(parsed, f"{row_label}.{column}", errors)
                if table in {"events", "reports"} and column == "payload_json":
                    validate_report_trial_depths(parsed, f"{row_label}.{column}", errors)
    return counts


def audit_events(connection: sqlite3.Connection, errors: list[str]) -> None:
    try:
        rows = connection.execute("SELECT * FROM events").fetchall()
    except sqlite3.Error as exc:
        errors.append(f"events: 読み取りに失敗しました: {exc}")
        return
    required_strings = ("event_id", "timestamp", "actor", "event_type", "entity_type", "entity_id", "operation")
    for row in rows:
        label = f"events[{row['event_id'] or 'unknown'}]"
        for column in required_strings:
            if not isinstance(row[column], str) or not row[column]:
                errors.append(f"{label}.{column}: 空でない文字列にしてください。")
        event_type = row["event_type"]
        entity_type = row["entity_type"]
        if isinstance(event_type, str) and event_type and event_type not in ALLOWED_EVENT_TYPES:
            errors.append(f"{label}.event_type: 未定義の event type です: {event_type}")
        if isinstance(entity_type, str) and entity_type and entity_type not in ALLOWED_ENTITY_TYPES:
            errors.append(f"{label}.entity_type: 未定義の entity type です: {entity_type}")
        operation = row["operation"]
        if isinstance(operation, str) and operation and operation not in ALLOWED_OPERATIONS:
            errors.append(f"{label}.operation: 未定義の operation です: {operation}")
        expected_entity_types = EVENT_ENTITY_TYPE_RULES.get(event_type)
        if expected_entity_types is not None and entity_type not in expected_entity_types:
            expected = ", ".join(sorted(expected_entity_types))
            errors.append(f"{label}.entity_type: {event_type} では {expected} にしてください: {entity_type}")
        if isinstance(row["timestamp"], str) and row["timestamp"]:
            parse_timestamp(row["timestamp"], f"{label}.timestamp", errors)

        usage = parse_json(row["structured_data_usage_json"], f"{label}.structured_data_usage_json", errors)
        if isinstance(usage, dict):
            for key in STRUCTURED_DATA_USAGE_FIELDS:
                if key not in usage:
                    errors.append(f"{label}.structured_data_usage_json.{key}: 必須 field です。")
            for key in ("structured_inputs", "evidence_refs"):
                if not isinstance(usage.get(key), list):
                    errors.append(f"{label}.structured_data_usage_json.{key}: list にしてください。")
            if usage.get("decision_rationale") is not None and not isinstance(usage.get("decision_rationale"), str):
                errors.append(f"{label}.structured_data_usage_json.decision_rationale: null または文字列にしてください。")

        safety = parse_json(row["event_safety_json"], f"{label}.event_safety_json", errors)
        if isinstance(safety, dict):
            for key in EVENT_SAFETY_FIELDS:
                if key not in safety:
                    errors.append(f"{label}.event_safety_json.{key}: 必須 field です。")
            for key in EVENT_SAFETY_FIELDS:
                if not isinstance(safety.get(key), list):
                    errors.append(f"{label}.event_safety_json.{key}: list にしてください。")
            payload = parse_json(row["payload_json"], f"{label}.payload_json", errors)
            if isinstance(payload, dict):
                if memory_candidate_envelope(payload) is not None and entity_type != "message":
                    errors.append(f"{label}.entity_type: memory candidate event は message entity で記録してください。")
                validate_memory_candidate_event_safety(payload, safety, f"{label}.event_safety_json", errors, row["actor"])


def audit_rank_and_trial_values(connection: sqlite3.Connection, errors: list[str]) -> None:
    for table, id_column in (("quests", "quest_id"),):
        try:
            rows = connection.execute(f"SELECT {id_column}, rank FROM {table} WHERE rank IS NOT NULL").fetchall()
        except sqlite3.Error as exc:
            errors.append(f"{table}: rank 読み取りに失敗しました: {exc}")
            continue
        for row in rows:
            if row["rank"] not in QUEST_RANKS:
                errors.append(f"{table}[{row[id_column]}].rank: 未定義の Quest Rank です: {row['rank']}")

    try:
        rows = connection.execute("SELECT trial_id, depth FROM trials WHERE depth IS NOT NULL").fetchall()
    except sqlite3.Error as exc:
        errors.append(f"trials: depth 読み取りに失敗しました: {exc}")
        return
    for row in rows:
        if row["depth"] not in TRIAL_DEPTHS:
            errors.append(f"trials[{row['trial_id']}].depth: 未定義の Trial depth です: {row['depth']}")


def audit_retired_agent_columns(connection: sqlite3.Connection, errors: list[str]) -> None:
    checks = (
        ("events", "event_id", "actor"),
        ("assignments", "assignment_id", "worker_id"),
        ("reports", "report_id", "worker_id"),
        ("inbox_messages", "message_id", "recipient"),
    )
    for table, id_column, value_column in checks:
        try:
            rows = connection.execute(f"SELECT {id_column}, {value_column} FROM {table}").fetchall()
        except sqlite3.Error as exc:
            errors.append(f"{table}: {value_column} 読み取りに失敗しました: {exc}")
            continue
        for row in rows:
            value = row[value_column]
            if isinstance(value, str) and value in RETIRED_AGENT_VALUES:
                errors.append(f"{table}[{row[id_column]}].{value_column}: 廃止済み agent 値 `{value}` が残っています。")


def audit_assignment_parent_contract(connection: sqlite3.Connection, errors: list[str]) -> None:
    try:
        rows = connection.execute("SELECT assignment_id, parent_id, payload_json FROM assignments").fetchall()
    except sqlite3.Error as exc:
        errors.append(f"assignments: parent_id 読み取りに失敗しました: {exc}")
        return
    for row in rows:
        label = f"assignments[{row['assignment_id']}].payload_json"
        payload = parse_json(row["payload_json"], label, errors)
        if not isinstance(payload, dict):
            continue
        expected_parent_id = expected_assignment_parent_id(payload, label, errors)
        if row["parent_id"] != expected_parent_id:
            errors.append(
                f"assignments[{row['assignment_id']}].parent_id: payload の owner/parent relation と一致しません: "
                f"{row['parent_id']} != {expected_parent_id}"
            )


def main() -> int:
    args = parse_args()
    database_path = args.runtime_root / "queue" / SQLITE_DB_NAME
    static_root = args.static_root.resolve(strict=False)
    guild_root = static_root.parent.parent
    errors: list[str] = []

    with connect_read(database_path) as connection:
        schema_ok = audit_schema(connection, errors)
        counts: dict[str, int] = {}
        if schema_ok:
            audit_metadata(connection, errors)
            counts = audit_json_columns(connection, guild_root, errors)
            audit_events(connection, errors)
            audit_rank_and_trial_values(connection, errors)
            audit_retired_agent_columns(connection, errors)
            audit_assignment_parent_contract(connection, errors)

    result = {"ok": not errors, "database": str(database_path), "counts": counts, "errors": errors}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("ledger audit: ok")
        print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
