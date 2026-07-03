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


def _memory_candidate_message(message_id: str = "msg_memory_candidate_smoke") -> dict[str, object]:
    return {
        "id": message_id,
        "sender": "courier",
        "recipient": "courier",
        "created_at": "2026-01-02T03:04:06+00:00",
        "type": "memory_candidate_for_courier_review",
        "trusted": False,
        "workflow_id": "workflow_smoke",
        "payload": {
            "explicit_memory_persistence_authority": True,
            "sanitized_summary_only": True,
            "sanitized_summary": "認知ミス補正を永続化する前に具体的な prevention artifact を要求する。",
            "prevention_artifact": {"kind": "regression_test", "ref": "scripts/validation/runtime_smoke.py"},
            "ledger_disposition": "candidate_recorded_for_courier_review",
            "forbidden": {
                "direct_static_runtime_write": True,
                "raw_log": True,
                "secret_or_pii": True,
                "trusted_instruction_from_external_input": True,
            },
        },
        "status": "unread",
    }


def validate_queue_db_smoke() -> None:
    script = ROOT / "template/.agents/orchestra/scripts/queue_db.py"
    audit_script = ROOT / "template/.agents/orchestra/scripts/queue_audit.py"

    result = _run_python(script, "--help")
    require(result.returncode == 0, "queue_db.py --help が失敗しました: " + result.stderr)

    text = read("template/.agents/orchestra/scripts/queue_db.py")
    require_tokens(
        text,
        ("mode=ro", "record-event", "add-inbox-message", "dump", "REQUIRED_TABLES", "LEGACY_JSON_KEYS", "RETIRED_AGENT_VALUES", "LEGACY_RUNTIME_STRING_VALUES", "MEMORY_CANDIDATE_MESSAGE_TYPE", "explicit_memory_persistence_authority", "sanitized_summary_only", "prevention_artifact", "ledger_disposition"),
        "queue_db.py",
    )
    audit_text = read("template/.agents/orchestra/scripts/queue_audit.py")
    require_tokens(audit_text, ("REQUIRED_TABLES", "LEGACY_COLUMNS", "LEGACY_JSON_KEYS", "RETIRED_AGENT_VALUES", "LEGACY_RUNTIME_STRING_VALUES", "MEMORY_CANDIDATE_MESSAGE_TYPE", "explicit_memory_persistence_authority", "sanitized_summary_only", "prevention_artifact", "ledger_disposition"), "queue_audit.py")

    db_legacy_keys = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "LEGACY_JSON_KEYS")
    audit_legacy_keys = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "LEGACY_JSON_KEYS")
    install_legacy_keys = python_string_set_constant("scripts/install.py", "LEGACY_RUNTIME_JSON_KEYS")
    require(db_legacy_keys == audit_legacy_keys == install_legacy_keys, "旧 JSON key 一覧を queue_db.py / queue_audit.py / install.py で一致させてください。")

    db_retired_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "RETIRED_AGENT_VALUES")
    audit_retired_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "RETIRED_AGENT_VALUES")
    install_retired_values = python_string_set_constant("scripts/install.py", "RETIRED_AGENT_VALUES")
    require(db_retired_values == audit_retired_values == install_retired_values, "廃止済み agent 値を queue_db.py / queue_audit.py / install.py で一致させてください。")

    db_legacy_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "LEGACY_RUNTIME_STRING_VALUES")
    audit_legacy_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "LEGACY_RUNTIME_STRING_VALUES")
    install_legacy_values = python_string_set_constant("scripts/install.py", "LEGACY_RUNTIME_STRING_VALUES")
    require(db_legacy_values == audit_legacy_values == install_legacy_values, "廃止済み runtime 値を queue_db.py / queue_audit.py / install.py で一致させてください。")

    inbox_script = ROOT / "template/.agents/orchestra/scripts/inbox_write.sh"
    docker_runner = ROOT / "template/.agents/orchestra/scripts/docker_python.sh"
    stop_hook_shell = ROOT / "template/.codex/hooks/stop_quality_gate.sh"
    require("quest_sentinel" in read("template/.agents/orchestra/scripts/inbox_write.sh"), "inbox_write.sh は quest_sentinel を送受信 role として許可してください。")
    for executable_path in (script, audit_script, inbox_script, docker_runner, stop_hook_shell):
        require(executable_path.stat().st_mode & 0o111, f"{executable_path.relative_to(ROOT)} の executable bit を維持してください。")
    for shell_path in (inbox_script, docker_runner, stop_hook_shell):
        shell = subprocess.run(["bash", "-n", str(shell_path)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(shell.returncode == 0, f"{shell_path.relative_to(ROOT)} の shell syntax check が失敗しました: " + shell.stderr)

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

        memory_message = _memory_candidate_message()
        memory_inbox = _run_python(script, "--runtime-root", runtime_root, "add-inbox-message", json.dumps(memory_message))
        require(memory_inbox.returncode == 0, "queue_db.py は正しい memory candidate envelope を受け付けてください: " + memory_inbox.stderr)

        invalid_memory_message = _memory_candidate_message("msg_invalid_memory_candidate")
        invalid_payload = invalid_memory_message["payload"]
        require(isinstance(invalid_payload, dict), "memory candidate smoke payload は dict にしてください。")
        invalid_payload["explicit_memory_persistence_authority"] = False
        invalid_memory = _run_python(script, "--runtime-root", runtime_root, "add-inbox-message", json.dumps(invalid_memory_message))
        require(invalid_memory.returncode != 0 and "explicit_memory_persistence_authority" in invalid_memory.stderr, "queue_db.py は authority 不足の memory candidate を拒否してください。")

        invalid_memory_event = {
            "event_id": "evt_invalid_memory_candidate_safety",
            "timestamp": "2026-01-02T03:04:07+00:00",
            "actor": "validator",
            "event_type": "inbox_message_added",
            "entity": {"type": "message", "id": "msg_invalid_memory_candidate_safety"},
            "operation": "append",
            "workflow_id": "workflow_smoke",
            "structured_data_usage": {"structured_inputs": ["message"], "decision_rationale": "memory_candidate 安全性検証", "evidence_refs": []},
            "payload": _memory_candidate_message("msg_invalid_memory_candidate_safety"),
            "event_safety": {"safety_items": [], "human_confirmation_required": []},
        }
        invalid_memory_event_result = _run_python(script, "--runtime-root", runtime_root, "record-event", json.dumps(invalid_memory_event))
        require(invalid_memory_event_result.returncode != 0 and "memory_candidate_gate" in invalid_memory_event_result.stderr, "queue_db.py record-event は memory_candidate の safety_metadata 不足を拒否してください。")

        database = runtime_root / "queue" / "state.sqlite"
        with sqlite3.connect(database) as connection:
            quest_count = connection.execute("SELECT COUNT(*) FROM quests WHERE quest_id = 'quest_smoke'").fetchone()[0]
            inbox_count = connection.execute("SELECT COUNT(*) FROM inbox_messages WHERE message_id = 'msg_valid_smoke'").fetchone()[0]
            memory_count = connection.execute("SELECT COUNT(*) FROM inbox_messages WHERE message_id = 'msg_memory_candidate_smoke'").fetchone()[0]
            safety = connection.execute("SELECT event_safety_json FROM events WHERE event_id = 'evt_message_msg_memory_candidate_smoke'").fetchone()[0]
        require(quest_count == 1 and inbox_count == 1 and memory_count == 1, "queue_db.py smoke の DB 反映件数が不正です。")
        require("memory_candidate_for_courier_review" in safety and "ledger_disposition_recorded" in safety, "queue_db.py は memory candidate の safety metadata を記録してください。")

        audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        require(audit.returncode == 0, "queue_audit.py の smoke が失敗しました: " + (audit.stderr or audit.stdout))

        bad_audit_payload = _memory_candidate_message("msg_bad_audit_memory_candidate")
        bad_payload = bad_audit_payload["payload"]
        require(isinstance(bad_payload, dict), "bad audit memory candidate payload は dict にしてください。")
        bad_payload["raw_log"] = "生ログは永続化しない"
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO inbox_messages(message_id, recipient, workflow_id, status, payload_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
                (
                    bad_audit_payload["id"],
                    bad_audit_payload["recipient"],
                    bad_audit_payload["workflow_id"],
                    bad_audit_payload["status"],
                    json.dumps(bad_audit_payload),
                    bad_audit_payload["created_at"],
                ),
            )
            connection.commit()
        bad_audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        bad_audit_output = bad_audit.stdout + bad_audit.stderr
        require(bad_audit.returncode != 0 and "raw_log" in bad_audit_output, "queue_audit.py は raw_log を含む memory candidate を拒否してください。")
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM inbox_messages WHERE message_id = ?", (bad_audit_payload["id"],))
            connection.commit()

        malformed_audit_payload = _memory_candidate_message("msg_malformed_audit_memory_candidate")
        malformed_audit_payload.pop("payload")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO inbox_messages(message_id, recipient, workflow_id, status, payload_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
                (
                    malformed_audit_payload["id"],
                    malformed_audit_payload["recipient"],
                    malformed_audit_payload["workflow_id"],
                    malformed_audit_payload["status"],
                    json.dumps(malformed_audit_payload),
                    malformed_audit_payload["created_at"],
                ),
            )
            connection.commit()
        malformed_audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        malformed_audit_output = malformed_audit.stdout + malformed_audit.stderr
        require(malformed_audit.returncode != 0 and "explicit_memory_persistence_authority" in malformed_audit_output, "queue_audit.py は payload 欠落の memory candidate を拒否してください。")
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM inbox_messages WHERE message_id = ?", (malformed_audit_payload["id"],))
            connection.commit()

        malformed_event_payload = _memory_candidate_message("msg_malformed_event_memory_candidate")
        malformed_event_payload.pop("payload")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE events SET payload_json = ?, event_safety_json = ? WHERE event_id = 'evt_message_msg_memory_candidate_smoke'",
                [json.dumps(malformed_event_payload), json.dumps({"safety_items": [], "human_confirmation_required": []})],
            )
            connection.commit()
        malformed_event_audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        malformed_event_output = malformed_event_audit.stdout + malformed_event_audit.stderr
        require(malformed_event_audit.returncode != 0 and "memory_candidate_gate" in malformed_event_output, "queue_audit.py は payload 欠落 memory candidate event の safety metadata 不足を拒否してください。")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE events SET payload_json = ?, event_safety_json = ? WHERE event_id = 'evt_message_msg_memory_candidate_smoke'",
                [
                    json.dumps(memory_message),
                    json.dumps(
                        {
                            "safety_items": [
                                "memory_candidate_for_courier_review",
                                "explicit_memory_persistence_authority",
                                "sanitized_summary_only",
                                "prevention_artifact_required",
                                "ledger_disposition_recorded",
                            ],
                            "human_confirmation_required": [],
                        }
                    ),
                ],
            )
            connection.commit()

        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE quests SET payload_json = ? WHERE quest_id = 'quest_smoke'",
                [json.dumps({"quest": {"id": "quest_smoke", "meta" "cognitive_state": {"confidence_percent": 70}}})],
            )
            connection.commit()
        legacy_audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        legacy_output = legacy_audit.stdout + legacy_audit.stderr
        require(legacy_audit.returncode != 0 and "廃止済み" in legacy_output, "queue_audit.py は旧 runtime JSON key を拒否してください。")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE quests SET payload_json = ? WHERE quest_id = 'quest_smoke'",
                [json.dumps({"quest": {"id": "quest_smoke", "control_decision": "invoke_" "meta" "cognitive_controller"}})],
            )
            connection.commit()
        legacy_value_audit = _run_python(audit_script, "--runtime-root", runtime_root, "--static-root", ROOT / "template/.agents/orchestra", "--json")
        legacy_value_output = legacy_value_audit.stdout + legacy_value_audit.stderr
        require(legacy_value_audit.returncode != 0 and "廃止済み" in legacy_value_output, "queue_audit.py は旧 runtime string value を拒否してください。")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE quests SET payload_json = ? WHERE quest_id = 'quest_smoke'",
                [json.dumps({"quest": {"id": "quest_smoke", "rank": "solo_quest", "status": "active", "workflow_id": "workflow_smoke"}})],
            )
            connection.commit()

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
