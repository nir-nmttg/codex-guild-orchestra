#!/usr/bin/env python3
"""Guild-native runtime 向け SQLite Ledger 補助。"""

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
DEFAULT_DB_NAME = "state.sqlite"
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
ALLOWED_OPERATIONS = {"append", "update", "replace", "mark_completed"}
QUEST_RANKS = {"mapmaking", "errand", "solo_quest", "party_quest", "guild_quest"}
TRIAL_DEPTHS = {"none", "self_check", "peer_review", "focused_trial", "multi_focus_trial", "safety_gate"}
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
REQUIRED_INBOX_MESSAGE_FIELDS = {"id", "sender", "recipient", "created_at", "type", "trusted", "payload", "status"}
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
LEGACY_TABLES = {"tickets"}
LEGACY_COLUMNS = {"assignments": {"task_id"}}
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


def static_root() -> Path:
    return Path(__file__).resolve().parent.parent


def guild_root() -> Path:
    return static_root().parent.parent


def default_runtime_root() -> Path:
    env_value = os.environ.get("CODEX_GUILD_ORCHESTRA_RUNTIME_ROOT")
    if env_value:
        return Path(env_value).expanduser()
    return guild_root() / ".orchestra"


def db_path(runtime_root: Path) -> Path:
    return runtime_root / "queue" / DEFAULT_DB_NAME


def schema_path() -> Path:
    return Path(__file__).resolve().with_name("queue_schema.sql")


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_loads(value: str) -> Any:
    return json.loads(value)


def connect_write(runtime_root: Path) -> sqlite3.Connection:
    path = db_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def connect_read(runtime_root: Path) -> sqlite3.Connection:
    path = db_path(runtime_root)
    if not path.exists():
        raise SystemExit(f"SQLite runtime DB がありません: {path}。`queue_db.py init` を実行してください。")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def schema_mismatch_message(schema_errors: list[str]) -> str:
    return (
        "SQLite runtime DB の物理 schema が v3 と一致しません。"
        + "自動 migration は行いません。`--backup --reset-runtime` または `--clean-install` を使ってください: "
        + "; ".join(schema_errors)
    )


def existing_tables(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def init_db(connection: sqlite3.Connection) -> None:
    if existing_tables(connection):
        schema_errors = collect_schema_errors(connection)
        if schema_errors:
            raise SystemExit(schema_mismatch_message(schema_errors))
    connection.executescript(schema_path().read_text(encoding="utf-8"))
    schema_errors = collect_schema_errors(connection)
    if schema_errors:
        raise SystemExit(schema_mismatch_message(schema_errors))
    connection.execute(
        """
        INSERT INTO queue_metadata(key, value)
        VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
        """,
        (QUEUE_SCHEMA_VERSION,),
    )
    connection.commit()


def collect_schema_errors(connection: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    tables = existing_tables(connection)
    legacy_tables = sorted(LEGACY_TABLES & tables)
    if legacy_tables:
        errors.append("旧 table が残っています: " + ", ".join(legacy_tables))
    missing_tables = sorted(REQUIRED_TABLES - tables)
    if missing_tables:
        errors.append("不足 table: " + ", ".join(missing_tables))
    for table, required_columns in REQUIRED_COLUMNS.items():
        if table not in tables:
            continue
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            errors.append(f"{table} の不足 column: " + ", ".join(missing_columns))
        legacy_columns = sorted(LEGACY_COLUMNS.get(table, set()) & columns)
        if legacy_columns:
            errors.append(f"{table} の旧 column: " + ", ".join(legacy_columns))
    return errors


def read_json_arg(raw: str) -> Any:
    if raw == "-":
        raw = sys.stdin.read()
    elif not raw.lstrip().startswith(("{", "[")):
        path = Path(raw).expanduser()
        if path.exists() and path.is_file():
            raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON を読めません: {exc}") from exc


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"{label} は JSON object にしてください。")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SystemExit(f"{label} は空でない文字列にしてください。")
    return value


def require_string_or_null(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return require_string(value, label)


def parse_timestamp(value: Any, label: str) -> None:
    raw = require_string(value, label)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"{label} は ISO 8601 形式にしてください: {raw}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SystemExit(f"{label} は timezone offset 付きにしてください: {raw}")


def payload_body(event: dict[str, Any]) -> dict[str, Any]:
    return require_mapping(event.get("payload"), "event.payload")


def event_entity(event: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    entity = require_mapping(event.get("entity"), "event.entity")
    entity_type = require_string(entity.get("type") or entity.get("kind"), "event.entity.type")
    entity_id = require_string(entity.get("id"), "event.entity.id")
    return entity_type, entity_id, entity


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


def iter_values(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, dict):
        for key, item in value.items():
            findings.extend(iter_values(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_values(item, f"{path}[{index}]"))
    return findings


def memory_candidate_envelope(payload: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    if payload.get("type") == MEMORY_CANDIDATE_MESSAGE_TYPE:
        body = require_mapping(payload.get("payload"), "message.payload")
        return ("message.payload", body)
    body = payload.get("payload")
    if not isinstance(body, dict):
        body = {}
    for key in (MEMORY_CANDIDATE_MESSAGE_TYPE, "memory_candidate"):
        if key in body:
            raise SystemExit(
                "memory candidate は message.type を "
                f"{MEMORY_CANDIDATE_MESSAGE_TYPE} にした courier review 専用 envelope として記録してください: message.payload.{key}"
            )
        if key in payload:
            raise SystemExit(
                "memory candidate は message.type を "
                f"{MEMORY_CANDIDATE_MESSAGE_TYPE} にした courier review 専用 envelope として記録してください: message.{key}"
            )
    return None


def validate_memory_candidate_message_scope(payload: dict[str, Any], actor: Any | None = None) -> None:
    if payload.get("sender") != "courier":
        raise SystemExit("memory candidate の message.sender は courier にしてください。")
    if payload.get("recipient") != "courier":
        raise SystemExit("memory candidate の message.recipient は courier にしてください。")
    if payload.get("trusted") is not False:
        raise SystemExit("memory candidate の message.trusted は false にしてください。")
    if actor is not None and actor != "courier":
        raise SystemExit("memory candidate の event.actor は courier にしてください。")


def validate_memory_candidate_envelope(envelope: dict[str, Any], label: str) -> None:
    if envelope.get("explicit_memory_persistence_authority") is not True:
        raise SystemExit(f"{label}.explicit_memory_persistence_authority は true にしてください。")
    if envelope.get("sanitized_summary_only") is not True:
        raise SystemExit(f"{label}.sanitized_summary_only は true にしてください。")
    require_string(envelope.get("sanitized_summary"), f"{label}.sanitized_summary")
    require_mapping(envelope.get("prevention_artifact"), f"{label}.prevention_artifact")
    require_string(envelope.get("ledger_disposition"), f"{label}.ledger_disposition")
    forbidden = require_mapping(envelope.get("forbidden"), f"{label}.forbidden")
    missing_markers = sorted(MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS - set(forbidden))
    if missing_markers:
        raise SystemExit(f"{label}.forbidden に必要な marker がありません: " + ", ".join(missing_markers))
    for marker in MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS:
        if forbidden.get(marker) is not True:
            raise SystemExit(f"{label}.forbidden.{marker} は true にしてください。")
    for json_path, key in iter_keys(envelope):
        if json_path.startswith("$.forbidden."):
            continue
        if key in MEMORY_CANDIDATE_REQUIRED_FORBIDDEN_MARKERS:
            raise SystemExit(f"{label}{json_path[1:]}: memory candidate に forbidden 内容 `{key}` を含めないでください。")


def validate_memory_candidate_event_safety(payload: dict[str, Any], event_safety: Any, actor: Any | None = None) -> None:
    if memory_candidate_envelope(payload) is None:
        return
    validate_memory_candidate_message_scope(payload, actor)
    safety = require_mapping(event_safety, "event.event_safety")
    safety_items = safety.get("safety_items")
    if not isinstance(safety_items, list):
        raise SystemExit("event.event_safety.safety_items は list にしてください。")
    missing = sorted(set(MEMORY_CANDIDATE_SAFETY_ITEMS) - set(safety_items))
    if missing:
        raise SystemExit("event.event_safety.safety_items に memory_candidate_gate が不足しています: " + ", ".join(missing))


def validate_no_legacy_runtime_shape(value: Any, label: str) -> None:
    for json_path, key in iter_keys(value):
        if key in LEGACY_JSON_KEYS or key in LEGACY_RUNTIME_STRING_VALUES:
            raise SystemExit(f"{label}{json_path[1:]}: 廃止済み key `{key}` が残っています。")
    for json_path, item in iter_values(value):
        if isinstance(item, str) and item in LEGACY_RUNTIME_STRING_VALUES:
            raise SystemExit(f"{label}{json_path[1:]}: 廃止済み runtime 値 `{item}` が残っています。")


def validate_target_repo_roots(value: Any, label: str) -> None:
    root = guild_root().resolve(strict=False)
    repositories_root = root / "repositories"
    for json_path, raw_path in iter_target_repo_roots(value):
        value_label = f"{label}{json_path[1:]}"
        if not isinstance(raw_path, str) or not raw_path:
            raise SystemExit(f"{value_label}: target_repo_root は空でない絶対 path 文字列にしてください。")
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            raise SystemExit(f"{value_label}: target_repo_root は絶対 path にしてください: {raw_path}")
        normalized = candidate.resolve(strict=False)
        if normalized == root:
            raise SystemExit(f"{value_label}: target_repo_root にギルド規約ルート自体は指定できません: {raw_path}")
        if normalized == repositories_root:
            raise SystemExit(f"{value_label}: target_repo_root に repositories/ 自体は指定できません: {raw_path}")
        if normalized.parent != repositories_root:
            raise SystemExit(f"{value_label}: target_repo_root は <guild_root>/repositories/<repo> の直下 path にしてください: {raw_path}")


def validate_structured_data_usage(value: Any) -> None:
    usage = require_mapping(value, "event.structured_data_usage")
    for key in STRUCTURED_DATA_USAGE_FIELDS:
        if key not in usage:
            raise SystemExit(f"event.structured_data_usage.{key} がありません。")
    for key in ("structured_inputs", "evidence_refs"):
        if not isinstance(usage.get(key), list):
            raise SystemExit(f"event.structured_data_usage.{key} は list にしてください。")
    if usage.get("decision_rationale") is not None and not isinstance(usage.get("decision_rationale"), str):
        raise SystemExit("event.structured_data_usage.decision_rationale は null または文字列にしてください。")


def validate_event_safety(value: Any) -> None:
    safety = require_mapping(value, "event.event_safety")
    for key in EVENT_SAFETY_FIELDS:
        if key not in safety:
            raise SystemExit(f"event.event_safety.{key} がありません。")
    for key in EVENT_SAFETY_FIELDS:
        if not isinstance(safety.get(key), list):
            raise SystemExit(f"event.event_safety.{key} は list にしてください。")


def validate_event_input(event: dict[str, Any]) -> None:
    for field in REQUIRED_EVENT_INPUT_FIELDS:
        if field not in event:
            raise SystemExit(f"event.{field} がありません。")
    require_string(event["event_id"], "event.event_id")
    require_string(event["actor"], "event.actor")
    event_type = require_string(event["event_type"], "event.event_type")
    operation = require_string(event["operation"], "event.operation")
    require_string_or_null(event.get("workflow_id"), "event.workflow_id")
    parse_timestamp(event["timestamp"], "event.timestamp")
    validate_structured_data_usage(event["structured_data_usage"])
    validate_event_safety(event["event_safety"])
    entity_type, _entity_id, _entity = event_entity(event)
    if event_type not in ALLOWED_EVENT_TYPES:
        raise SystemExit(f"event.event_type は許可値にしてください: {event_type}")
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise SystemExit(f"event.entity.type は許可値にしてください: {entity_type}")
    if operation not in ALLOWED_OPERATIONS:
        expected = ", ".join(sorted(ALLOWED_OPERATIONS))
        raise SystemExit(f"event.operation は {expected} のいずれかにしてください: {operation}")
    expected_entity_types = EVENT_ENTITY_TYPE_RULES.get(event_type)
    if expected_entity_types is not None and entity_type not in expected_entity_types:
        expected = ", ".join(sorted(expected_entity_types))
        raise SystemExit(f"event.entity.type は {event_type} では {expected} にしてください: {entity_type}")
    payload = payload_body(event)
    if memory_candidate_envelope(payload) is not None:
        if entity_type != "message":
            raise SystemExit("memory candidate event の event.entity.type は message にしてください。")
        validate_memory_candidate_event_safety(payload, event["event_safety"], event.get("actor"))
    validate_target_repo_roots(event, "event")
    validate_no_legacy_runtime_shape(event, "event")


def insert_event(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    event_id = require_string(event.get("event_id"), "event.event_id")
    entity_type, entity_id, entity = event_entity(event)
    payload = payload_body(event)
    row_values = (
        event_id,
        require_string(event.get("timestamp"), "event.timestamp"),
        require_string(event.get("actor"), "event.actor"),
        require_string(event.get("event_type"), "event.event_type"),
        entity_type,
        entity_id,
        json_dumps(entity),
        require_string(event.get("operation"), "event.operation"),
        event.get("workflow_id"),
        json_dumps(event.get("structured_data_usage") or {}),
        json_dumps(payload),
        json_dumps(event.get("event_safety") or {}),
    )
    existing = connection.execute("SELECT event_id FROM events WHERE event_id = ?", (event_id,)).fetchone()
    if existing is not None:
        raise SystemExit(f"event_id が重複しています: {event_id}")
    connection.execute(
        """
        INSERT INTO events(
          event_id, timestamp, actor, event_type, entity_type, entity_id, entity_json,
          operation, workflow_id, structured_data_usage_json, payload_json, event_safety_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        row_values,
    )


def nested_payload(payload: dict[str, Any], *names: str) -> dict[str, Any]:
    for name in names:
        value = payload.get(name)
        if isinstance(value, dict):
            return value
    return payload


def assignment_parent_id(payload: dict[str, Any]) -> str | None:
    owner_assignment_id = require_string_or_null(payload.get("owner_assignment_id"), "assignment.owner_assignment_id")
    parent_id = require_string_or_null(payload.get("parent_id"), "assignment.parent_id")
    if owner_assignment_id and parent_id and owner_assignment_id != parent_id:
        raise SystemExit("assignment.owner_assignment_id と assignment.parent_id は同じ owner assignment を指してください。")
    worker_id = payload.get("worker_id")
    kind = payload.get("kind")
    if (worker_id == "advisor" or kind == "advisory_consultation") and not (owner_assignment_id or parent_id):
        raise SystemExit("advisor assignment は owner_assignment_id または parent_id が必要です。")
    if worker_id == "quest_sentinel" or kind == "quest_awareness_control_monitor":
        if not (owner_assignment_id or parent_id):
            raise SystemExit("quest_sentinel assignment は owner_assignment_id または parent_id が必要です。")
        require_string(payload.get("control_trigger"), "assignment.control_trigger")
    return owner_assignment_id or parent_id or require_string_or_null(payload.get("quest_id"), "assignment.quest_id")


def upsert_quest(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = nested_payload(payload_body(event), "quest")
    quest_id = require_string(payload.get("id") or payload.get("quest_id"), "quest.id")
    rank = payload.get("rank")
    if rank is not None and (not isinstance(rank, str) or rank not in QUEST_RANKS):
        expected = ", ".join(sorted(QUEST_RANKS))
        raise SystemExit(f"quest.rank は {expected} のいずれかにしてください: {rank}")
    connection.execute(
        """
        INSERT INTO quests(quest_id, workflow_id, rank, status, payload_json)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(quest_id) DO UPDATE SET
          workflow_id = excluded.workflow_id,
          rank = excluded.rank,
          status = excluded.status,
          payload_json = excluded.payload_json,
          updated_at = datetime('now')
        """,
        (quest_id, payload.get("workflow_id") or event.get("workflow_id"), rank, payload.get("status") or "drafted", json_dumps(payload)),
    )


def upsert_request(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = nested_payload(payload_body(event), "request", "quest")
    request_id = require_string(payload.get("id") or payload.get("request_id") or payload.get("quest_id"), "request.id")
    connection.execute(
        """
        INSERT INTO requests(request_id, quest_id, workflow_id, status, payload_json)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(request_id) DO UPDATE SET
          quest_id = excluded.quest_id,
          workflow_id = excluded.workflow_id,
          status = excluded.status,
          payload_json = excluded.payload_json,
          updated_at = datetime('now')
        """,
        (request_id, payload.get("quest_id"), payload.get("workflow_id") or event.get("workflow_id"), payload.get("status") or "drafted", json_dumps(payload)),
    )


def upsert_command(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = nested_payload(payload_body(event), "command")
    command_id = require_string(payload.get("id") or payload.get("command_id"), "command.id")
    connection.execute(
        """
        INSERT INTO commands(command_id, quest_id, workflow_id, status, payload_json)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(command_id) DO UPDATE SET
          quest_id = excluded.quest_id,
          workflow_id = excluded.workflow_id,
          status = excluded.status,
          payload_json = excluded.payload_json,
          updated_at = datetime('now')
        """,
        (command_id, payload.get("quest_id"), payload.get("workflow_id") or event.get("workflow_id"), payload.get("status") or "drafted", json_dumps(payload)),
    )


def upsert_assignment(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = nested_payload(payload_body(event), "assignment")
    assignment_id = require_string(payload.get("id") or payload.get("assignment_id"), "assignment.id")
    connection.execute(
        """
        INSERT INTO assignments(assignment_id, parent_id, worker_id, kind, workflow_id, status, payload_json)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(assignment_id) DO UPDATE SET
          parent_id = excluded.parent_id,
          worker_id = excluded.worker_id,
          kind = excluded.kind,
          workflow_id = excluded.workflow_id,
          status = excluded.status,
          payload_json = excluded.payload_json,
          updated_at = datetime('now')
        """,
        (
            assignment_id,
            assignment_parent_id(payload),
            payload.get("worker_id") or payload.get("role") or "unassigned",
            payload.get("kind") or payload.get("role") or event.get("entity", {}).get("type") or "assignment",
            payload.get("workflow_id") or event.get("workflow_id"),
            payload.get("status") or "idle",
            json_dumps(payload),
        ),
    )


def upsert_report(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = nested_payload(payload_body(event), "report")
    report_id = require_string(payload.get("id") or payload.get("report_id") or event_entity(event)[1], "report.id")
    if "trial_depth" in payload:
        depth = payload["trial_depth"]
        if not isinstance(depth, str) or depth not in TRIAL_DEPTHS:
            expected = ", ".join(sorted(TRIAL_DEPTHS))
            raise SystemExit(f"report.trial_depth は {expected} のいずれかにしてください: {depth}")
    connection.execute(
        """
        INSERT INTO reports(report_id, worker_id, workflow_id, decision, status, payload_json)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_id) DO UPDATE SET
          worker_id = excluded.worker_id,
          workflow_id = excluded.workflow_id,
          decision = excluded.decision,
          status = excluded.status,
          payload_json = excluded.payload_json,
          updated_at = datetime('now')
        """,
        (
            report_id,
            payload.get("worker_id") or "unknown",
            payload.get("workflow_id") or event.get("workflow_id"),
            payload.get("decision"),
            payload.get("status"),
            json_dumps(payload),
        ),
    )


def upsert_trial(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = nested_payload(payload_body(event), "trial", "report")
    trial_id = require_string(payload.get("id") or payload.get("trial_id") or event_entity(event)[1], "trial.id")
    depth = None
    if "depth" in payload:
        depth = payload["depth"]
    elif "trial_depth" in payload:
        depth = payload["trial_depth"]
    if depth is not None and (not isinstance(depth, str) or depth not in TRIAL_DEPTHS):
        expected = ", ".join(sorted(TRIAL_DEPTHS))
        raise SystemExit(f"trial.depth は {expected} のいずれかにしてください: {depth}")
    connection.execute(
        """
        INSERT INTO trials(trial_id, quest_id, workflow_id, depth, status, payload_json)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(trial_id) DO UPDATE SET
          quest_id = excluded.quest_id,
          workflow_id = excluded.workflow_id,
          depth = excluded.depth,
          status = excluded.status,
          payload_json = excluded.payload_json,
          updated_at = datetime('now')
        """,
        (trial_id, payload.get("quest_id"), payload.get("workflow_id") or event.get("workflow_id"), depth, payload.get("status") or "draft", json_dumps(payload)),
    )


def validate_inbox_message_payload(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_INBOX_MESSAGE_FIELDS - set(payload))
    if missing:
        raise SystemExit("message に必要な field がありません: " + ", ".join(missing))
    require_string(payload.get("id"), "message.id")
    require_string(payload.get("sender"), "message.sender")
    require_string(payload.get("recipient"), "message.recipient")
    parse_timestamp(payload.get("created_at"), "message.created_at")
    require_string(payload.get("type"), "message.type")
    if not isinstance(payload.get("trusted"), bool):
        raise SystemExit("message.trusted は bool にしてください。")
    require_mapping(payload.get("payload"), "message.payload")
    require_string(payload.get("status"), "message.status")
    envelope = memory_candidate_envelope(payload)
    if envelope is not None:
        validate_memory_candidate_message_scope(payload)
        validate_memory_candidate_envelope(envelope[1], envelope[0])


def inbox_event_safety(payload: dict[str, Any]) -> dict[str, list[str]]:
    envelope = memory_candidate_envelope(payload)
    if envelope is None:
        return {"safety_items": [], "human_confirmation_required": []}
    return {
        "safety_items": list(MEMORY_CANDIDATE_SAFETY_ITEMS),
        "human_confirmation_required": [],
    }


def upsert_message(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = payload_body(event)
    validate_inbox_message_payload(payload)
    message_id = require_string(payload.get("id"), "message.id")
    connection.execute(
        """
        INSERT INTO inbox_messages(message_id, recipient, workflow_id, status, payload_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(message_id) DO UPDATE SET
          recipient = excluded.recipient,
          workflow_id = excluded.workflow_id,
          status = excluded.status,
          payload_json = excluded.payload_json,
          created_at = excluded.created_at
        """,
        (
            message_id,
            require_string(payload.get("recipient"), "message.recipient"),
            payload.get("workflow_id") or event.get("workflow_id"),
            require_string(payload.get("status"), "message.status"),
            json_dumps(payload),
            require_string(payload.get("created_at"), "message.created_at"),
        ),
    )


def record_event(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    validate_event_input(event)
    insert_event(connection, event)
    entity_type = event_entity(event)[0]
    if entity_type == "quest":
        upsert_quest(connection, event)
    elif entity_type == "request":
        upsert_request(connection, event)
    elif entity_type == "command":
        upsert_command(connection, event)
    elif entity_type == "assignment":
        upsert_assignment(connection, event)
    elif entity_type == "report":
        upsert_report(connection, event)
    elif entity_type == "trial":
        upsert_trial(connection, event)
    elif entity_type == "message":
        upsert_message(connection, event)


def cmd_init(args: argparse.Namespace) -> None:
    with connect_write(args.runtime_root) as connection:
        init_db(connection)
    print(db_path(args.runtime_root))


def cmd_record_event(args: argparse.Namespace) -> None:
    event = require_mapping(read_json_arg(args.event), "event")
    with connect_write(args.runtime_root) as connection:
        record_event(connection, event)
        connection.commit()
    print(event["event_id"])


def cmd_add_inbox_message(args: argparse.Namespace) -> None:
    payload = require_mapping(read_json_arg(args.message), "message")
    validate_inbox_message_payload(payload)
    event = {
        "event_id": f"evt_message_{payload['id']}",
        "timestamp": payload["created_at"],
        "actor": payload["sender"],
        "event_type": "inbox_message_added",
        "entity": {"type": "message", "id": payload["id"]},
        "operation": "append",
        "workflow_id": payload.get("workflow_id"),
        "structured_data_usage": {"structured_inputs": ["message"], "decision_rationale": "inbox message append", "evidence_refs": []},
        "payload": payload,
        "event_safety": inbox_event_safety(payload),
    }
    with connect_write(args.runtime_root) as connection:
        record_event(connection, event)
        connection.commit()
    print(event["event_id"])


def cmd_dump(args: argparse.Namespace) -> None:
    allowed = {"queue_metadata", "events", "quests", "requests", "commands", "assignments", "reports", "trials", "inbox_messages"}
    if args.table not in allowed:
        raise SystemExit("dump table は次のいずれかにしてください: " + ", ".join(sorted(allowed)))
    with connect_read(args.runtime_root) as connection:
        rows = [dict(row) for row in connection.execute(f"SELECT * FROM {args.table} ORDER BY rowid")]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    with connect_read(args.runtime_root) as connection:
        result = {}
        for table in ("quests", "requests", "commands", "assignments", "reports", "trials", "inbox_messages", "events"):
            result[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guild runtime Ledger helper")
    parser.add_argument("--runtime-root", type=Path, default=default_runtime_root())
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    record = sub.add_parser("record-event")
    record.add_argument("event")
    record.set_defaults(func=cmd_record_event)

    inbox = sub.add_parser("add-inbox-message")
    inbox.add_argument("message")
    inbox.set_defaults(func=cmd_add_inbox_message)

    dump = sub.add_parser("dump")
    dump.add_argument("table")
    dump.set_defaults(func=cmd_dump)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
