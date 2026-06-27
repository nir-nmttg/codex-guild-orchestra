"""runtime Ledger と queue DB の smoke 検証。"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import ROOT, python_string_set_constant, read, require, require_tokens
from .rules import LEDGER_TABLES


def validate_sqlite_schema() -> None:
    schema = read("template/.agents/orchestra/scripts/queue_schema.sql")
    require("assignment_id TEXT NOT NULL PRIMARY KEY" in schema, "assignments table は assignment_id を primary key にしてください。")
    require("task_id" not in schema, "SQLite schema に旧 column `task_id` を戻さないでください。")
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(schema)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    missing = sorted(LEDGER_TABLES - tables)
    require(not missing, "SQLite schema に不足 table があります: " + ", ".join(missing))


def _run_python(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _valid_event() -> dict[str, object]:
    return {
        "event_id": "evt_smoke_quest_created",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "validator",
        "event_type": "quest_created",
        "entity": {"type": "quest", "id": "quest_smoke"},
        "operation": "append",
        "workflow_id": "workflow_smoke",
        "structured_data_usage": {"structured_inputs": ["validator_smoke"], "decision_rationale": "positive smoke", "evidence_refs": ["scripts/validate.py"]},
        "payload": {"quest": {"id": "quest_smoke", "rank": "solo_quest", "status": "active", "workflow_id": "workflow_smoke"}},
        "event_safety": {"safety_items": [], "human_confirmation_required": []},
    }


def validate_queue_db_smoke() -> None:
    script = ROOT / "template/.agents/orchestra/scripts/queue_db.py"
    audit_script = ROOT / "template/.agents/orchestra/scripts/queue_audit.py"

    result = _run_python(script, "--help")
    require(result.returncode == 0, "queue_db.py --help が失敗しました: " + result.stderr)

    text = read("template/.agents/orchestra/scripts/queue_db.py")
    require_tokens(
        text,
        ("mode=ro", "record-event", "add-inbox-message", "dump", "REQUIRED_TABLES", "LEGACY_JSON_KEYS", "RETIRED_AGENT_VALUES"),
        "queue_db.py",
    )
    audit_text = read("template/.agents/orchestra/scripts/queue_audit.py")
    require_tokens(audit_text, ("REQUIRED_TABLES", "LEGACY_COLUMNS", "LEGACY_JSON_KEYS", "RETIRED_AGENT_VALUES"), "queue_audit.py")

    db_legacy_keys = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "LEGACY_JSON_KEYS")
    audit_legacy_keys = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "LEGACY_JSON_KEYS")
    install_legacy_keys = python_string_set_constant("scripts/install.py", "LEGACY_RUNTIME_JSON_KEYS")
    require(db_legacy_keys == audit_legacy_keys == install_legacy_keys, "旧 JSON key 一覧を queue_db.py / queue_audit.py / install.py で一致させてください。")

    db_retired_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "RETIRED_AGENT_VALUES")
    audit_retired_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "RETIRED_AGENT_VALUES")
    install_retired_values = python_string_set_constant("scripts/install.py", "RETIRED_AGENT_VALUES")
    require(db_retired_values == audit_retired_values == install_retired_values, "廃止済み agent 値を queue_db.py / queue_audit.py / install.py で一致させてください。")

    inbox_script = ROOT / "template/.agents/orchestra/scripts/inbox_write.sh"
    for executable_path in (script, audit_script, inbox_script):
        require(executable_path.stat().st_mode & 0o111, f"{executable_path.relative_to(ROOT)} の executable bit を維持してください。")
    shell = subprocess.run(["bash", "-n", str(inbox_script)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(shell.returncode == 0, "inbox_write.sh の shell syntax check が失敗しました: " + shell.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        runtime_root = Path(tmp) / ".orchestra"

        init = _run_python(script, "--runtime-root", runtime_root, "init")
        require(init.returncode == 0, "queue_db.py init が失敗しました: " + init.stderr)

        recorded = _run_python(script, "--runtime-root", runtime_root, "record-event", json.dumps(_valid_event()))
        require(recorded.returncode == 0, "queue_db.py record-event の smoke が失敗しました: " + recorded.stderr)

        message = {
            "id": "msg_valid_smoke",
            "sender": "validator",
            "recipient": "adventurer",
            "created_at": "2026-01-02T03:04:05+00:00",
            "type": "message",
            "trusted": False,
            "workflow_id": "workflow_smoke",
            "payload": {"summary": "positive smoke"},
            "status": "unread",
        }
        inbox = _run_python(script, "--runtime-root", runtime_root, "add-inbox-message", json.dumps(message))
        require(inbox.returncode == 0, "queue_db.py add-inbox-message の smoke が失敗しました: " + inbox.stderr)

        database = runtime_root / "queue" / "state.sqlite"
        with sqlite3.connect(database) as connection:
            quest_count = connection.execute("SELECT COUNT(*) FROM quests WHERE quest_id = 'quest_smoke'").fetchone()[0]
            inbox_count = connection.execute("SELECT COUNT(*) FROM inbox_messages WHERE message_id = 'msg_valid_smoke'").fetchone()[0]
        require(quest_count == 1 and inbox_count == 1, "queue_db.py smoke の DB 反映件数が不正です。")

        audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        require(audit.returncode == 0, "queue_audit.py の smoke が失敗しました: " + (audit.stderr or audit.stdout))

        invalid_event = _valid_event()
        invalid_event["event_id"] = "evt_invalid_operation"
        invalid_event["operation"] = "merge"
        invalid = _run_python(script, "--runtime-root", runtime_root, "record-event", json.dumps(invalid_event))
        require(invalid.returncode != 0 and "operation" in invalid.stderr, "queue_db.py は invalid operation を拒否してください。")

    with tempfile.TemporaryDirectory() as tmp:
        runtime_root = Path(tmp) / ".orchestra"
        database = runtime_root / "queue" / "state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE tickets(ticket_id TEXT PRIMARY KEY)")
            connection.execute("CREATE TABLE assignments(task_id TEXT PRIMARY KEY, status TEXT)")
            connection.commit()

        legacy_init = _run_python(script, "--runtime-root", runtime_root, "init")
        output = legacy_init.stdout + legacy_init.stderr
        require(legacy_init.returncode != 0 and ("tickets" in output or "task_id" in output), "queue_db.py init は旧物理 schema を拒否してください。")
