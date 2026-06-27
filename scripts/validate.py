#!/usr/bin/env python3
"""Guild-native runtime contract validator."""

from __future__ import annotations

import json
import ast
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]

try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "Makefile",
    "README.md",
    "VERSION",
    "requirements.txt",
    "docs/orchestration-runtime.md",
    "docs/agent-deployment.md",
    "docs/guild-quest-lifecycle.md",
    "docs/customization.md",
    "docs/deployment-patterns.md",
    "docs/claude-compatibility.md",
    "docs/prompt-recipes.md",
    "docs/localization-management.md",
    "template/AGENTS.md",
    "template/.codex/config.toml",
    "template/.codex/hooks.json",
    "template/.codex/hooks/stop_quality_gate.py",
    "template/.codex/agents/adventurer.toml",
    "template/.codex/agents/advisor.toml",
    "template/.codex/agents/cartographer.toml",
    "template/.codex/agents/courier.toml",
    "template/.codex/agents/guildmaster.toml",
    "template/.codex/agents/inquisitor.toml",
    "template/.codex/agents/party_leader.toml",
    "template/.agents/orchestra/config/settings.yaml",
    "template/.agents/orchestra/README.md",
    "template/.agents/orchestra/instructions/common.md",
    "template/.agents/orchestra/instructions/advisor.md",
    "template/.agents/orchestra/instructions/receptionist.md",
    "template/.agents/orchestra/instructions/cartographer.md",
    "template/.agents/orchestra/instructions/guildmaster.md",
    "template/.agents/orchestra/instructions/party_leader.md",
    "template/.agents/orchestra/instructions/adventurer.md",
    "template/.agents/orchestra/instructions/inquisitor.md",
    "template/.agents/orchestra/instructions/session_recovery.md",
    "template/.agents/orchestra/logs/daily/README.md",
    "template/.agents/orchestra/queue/README.md",
    "template/.agents/orchestra/queue/templates/advisor_assignment.yaml",
    "template/.agents/orchestra/queue/templates/advisor_report.yaml",
    "template/.agents/orchestra/queue/templates/adventurer_assignment.yaml",
    "template/.agents/orchestra/queue/templates/adventurer_report.yaml",
    "template/.agents/orchestra/queue/templates/adventurer_inbox.yaml",
    "template/.agents/orchestra/queue/templates/cartographer_assignment.yaml",
    "template/.agents/orchestra/queue/templates/cartographer_report.yaml",
    "template/.agents/orchestra/queue/templates/inquisitor_trial.yaml",
    "template/.agents/orchestra/queue/templates/inquisitor_report.yaml",
    "template/.agents/orchestra/queue/templates/role_inbox.yaml",
    "template/.agents/orchestra/queue/templates/request.yaml",
    "template/.agents/orchestra/queue/templates/command.yaml",
    "template/.agents/skills/repository-design-mapmaking/SKILL.md",
    "template/.agents/skills/use-guild-workflow/SKILL.md",
    "template/.agents/orchestra/scripts/inbox_write.sh",
    "template/.agents/orchestra/scripts/claude_compat.py",
    "template/.agents/orchestra/scripts/queue_db.py",
    "template/.agents/orchestra/scripts/queue_audit.py",
    "template/.agents/orchestra/scripts/queue_schema.sql",
    "scripts/install.py",
    "scripts/clean_install.sh",
    "scripts/install.sh",
    "scripts/sync.sh",
]

QUEST_RANKS = {"mapmaking", "errand", "solo_quest", "party_quest", "guild_quest"}
TRIAL_DEPTHS = {"none", "self_check", "peer_review", "focused_trial", "multi_focus_trial", "safety_gate"}
TRIAL_REQUIRED_CHECKS = {
    "intent_coverage",
    "success_criteria",
    "guild_law",
    "authority_boundary",
    "scope_boundary",
    "safety_items",
    "architecture_consistency",
    "responsibility_split",
    "readability",
    "maintainability",
    "validation_evidence",
    "regression_risk",
}
TRIAL_CONDITIONAL_CHECKS = {
    "edge_cases",
    "error_handling",
    "security",
    "performance",
    "accessibility",
    "compatibility",
}
TRIAL_DEPTH_GUARDRAILS = {"multi_focus_trial", "safety_gate"}
OPERATIONS = {"append", "update", "replace", "mark_completed"}
ARTIFACT_REQUIRED_FIELDS = ["artifact_type", "schema_version", "workflow_id", "structured_data_usage"]
STRUCTURED_DATA_USAGE_FIELDS = ["structured_inputs", "decision_rationale", "evidence_refs"]
EVENT_INPUT_REQUIRED_FIELDS = [
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
]
EVENT_SAFETY_FIELDS = ["safety_items", "human_confirmation_required"]
AUTHORITY_KEYS = {"read", "edit", "validate", "local_git", "external_actions"}
AUTONOMY_KEYS = {"subassignments", "extra_file_reads", "validation_iterations", "timebox_minutes"}
LEDGER_TABLES = {
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
EVENT_TYPES = {
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
ENTITY_TYPES = {
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
SAFETY_TOKENS = (
    "target_repo_root",
    "<guild_root>/repositories/<repo>",
    "secret",
    "token",
    "credential",
    "PII",
    "破壊的操作",
    "公開 API",
    "未信頼",
    "人間確認",
)
GUILD_TERMS = (
    "Guild Law",
    "Quest Charter",
    "Party Tactics",
    "Trial",
    "Ledger",
)
DEFAULT_INTAKE_TOKENS = (
    "Default Guild Intake",
    "always_guild_intake",
    "use-guild-workflow",
    "target_repo_root",
    "full Quest",
)
DEFAULT_INTAKE_CONFIRMATION_TOKENS = (
    "guild_law.human_confirmation_required_for",
    "破壊的操作",
    "依存追加",
    "migration",
    "deploy",
    "本番データ",
    "課金",
    "認可",
    "公開API互換性変更",
    "仕様判断",
    "MCP server",
    "外部 network access",
    "秘密情報",
    "認証情報",
    "PII",
)
GUILD_SKILL_PRIORITY_TOKENS = (
    "類似 Skill",
    "owner: codex-guild-orchestra",
    "ギルド側 Skill",
    "非ギルド Skill",
    "plugin",
    "connector",
    "Quest Charter",
    "authority",
    "boundaries",
)
LEGACY_PRIMARY_TERMS = (
    "root_session_to_adventurer_with_inquisitor_review",
    "root_session_to_courier_no_queue_no_subagents",
    "scale_risk_model",
    "inquisitor_count_by_scale",
    "small.review_task_fields",
    "planning/tiny/small/medium/large",
)
LEGACY_ROUTE_COMMENT_TERMS = (
    "小規模",
    "大規模",
    "planning/tiny/small/medium/large",
)
VOCABULARY_DRIFT_TERMS = (
    "task_id",
    "quest_queue",
    "adventurer_task.yaml",
    "inquisitor_task.yaml",
    "docs/agent-expansion-by-scale.md",
)
ACTIVE_PROSE_PATHS = (
    "README.md",
    "docs/agent-deployment.md",
    "docs/customization.md",
    "docs/deployment-patterns.md",
    "docs/claude-compatibility.md",
    "docs/guild-quest-lifecycle.md",
    "docs/localization-management.md",
    "docs/orchestration-runtime.md",
    "docs/prompt-recipes.md",
    "scripts/install.py",
    "template/AGENTS.md",
    "template/.codex/config.toml",
    "template/.codex/agents/adventurer.toml",
    "template/.codex/agents/advisor.toml",
    "template/.codex/agents/cartographer.toml",
    "template/.codex/agents/courier.toml",
    "template/.codex/agents/guildmaster.toml",
    "template/.codex/agents/inquisitor.toml",
    "template/.codex/agents/party_leader.toml",
    "template/.agents/orchestra/README.md",
    "template/.agents/orchestra/config/settings.yaml",
    "template/.agents/orchestra/dashboard.md",
    "template/.agents/orchestra/queue/README.md",
    "template/.agents/orchestra/instructions/adventurer.md",
    "template/.agents/orchestra/instructions/advisor.md",
    "template/.agents/orchestra/instructions/cartographer.md",
    "template/.agents/orchestra/instructions/common.md",
    "template/.agents/orchestra/instructions/guildmaster.md",
    "template/.agents/orchestra/instructions/inquisitor.md",
    "template/.agents/orchestra/instructions/party_leader.md",
    "template/.agents/orchestra/instructions/receptionist.md",
    "template/.agents/orchestra/instructions/session_recovery.md",
    "template/.agents/orchestra/logs/daily/README.md",
)
ACTIVE_PROSE_DRIFT_TERMS = (
    "固定 route",
    "規模別 route",
    "軽量 assignment",
    "agent の自律性",
    "専用 agent",
    "`courier` agent",
    "runtime contract/state",
    "runtime state として",
    "動的 state",
    "role instruction",
    "golden task",
)
AMBIGUOUS_INQUISITOR_TERMS = (
    "lead inquisitor",
    "lead Inquisitor",
    "lead `inquisitor`",
)


class ValidationError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def read(rel_path: str) -> str:
    try:
        return (ROOT / rel_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"{rel_path} を読めません: {exc}") from exc


def load_yaml(rel_path: str) -> object:
    require(yaml is not None, "YAML 検証には PyYAML が必要です。")
    try:
        return yaml.safe_load((ROOT / rel_path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # type: ignore[union-attr]
        raise ValidationError(f"{rel_path} の YAML parse に失敗しました: {exc}") from exc


def mapping(value: object, label: str) -> dict[str, object]:
    require(isinstance(value, dict), f"{label} は mapping にしてください。")
    return value  # type: ignore[return-value]


def sequence(value: object, label: str) -> list[object]:
    require(isinstance(value, list), f"{label} は list にしてください。")
    return value  # type: ignore[return-value]


def require_keys(value: dict[str, object], keys: set[str] | tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in value]
    require(not missing, f"{label} に必要な field がありません: " + ", ".join(missing))


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    missing = [token for token in tokens if token not in text]
    require(not missing, f"{label} に必要な語がありません: " + ", ".join(missing))


def validate_active_prose_vocabulary() -> None:
    paths = list(ACTIVE_PROSE_PATHS)
    skills_root = ROOT / "template/.agents/skills"
    if skills_root.exists():
        paths.extend(str(path.relative_to(ROOT)) for path in sorted(skills_root.glob("*/SKILL.md")))

    for rel in paths:
        text = read(rel)
        for token in ACTIVE_PROSE_DRIFT_TERMS:
            require(token not in text, f"{rel} に Guild 命名から外れる表現 `{token}` が残っています。")


def python_string_set_constant(rel_path: str, constant_name: str) -> set[str]:
    tree = ast.parse(read(rel_path), filename=rel_path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == constant_name for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        require(isinstance(value, set) and all(isinstance(item, str) for item in value), f"{rel_path}.{constant_name} は str set にしてください。")
        return set(value)
    raise ValidationError(f"{rel_path}.{constant_name} が見つかりません。")


def validate_dependencies() -> None:
    missing = []
    if yaml is None:
        missing.append("PyYAML")
    if tomllib is None:
        missing.append("tomllib/tomli")
    require(not missing, "検証に必要な依存がありません: " + ", ".join(missing))


def validate_required_paths() -> None:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    require(not missing, "不足している必須ファイルがあります: " + ", ".join(missing))


def validate_version() -> None:
    version = read("VERSION").strip()
    parts = version.split(".")
    require(len(parts) == 3 and all(part.isdecimal() for part in parts), "VERSION は MAJOR.MINOR.PATCH 形式にしてください。")


def validate_settings() -> None:
    settings = mapping(load_yaml("template/.agents/orchestra/config/settings.yaml"), "settings.yaml")
    require(settings.get("version") == "3.0", "settings.yaml.version は 3.0 にしてください。")
    for section in ("guild_runtime", "default_intake_policy", "skill_selection_policy", "paths", "guild_law", "claude_compat", "quest_charter", "workers", "advisory_consultation", "root_session", "party_tactics", "trial", "ledger", "reporting"):
        require(section in settings, f"settings.yaml に {section} が必要です。")

    text = read("template/.agents/orchestra/config/settings.yaml")
    require_tokens(text, GUILD_TERMS + SAFETY_TOKENS, "settings.yaml")
    for token in LEGACY_PRIMARY_TERMS:
        require(token not in text, f"settings.yaml に旧固定 contract `{token}` が残っています。")
    for token in AMBIGUOUS_INQUISITOR_TERMS:
        require(token not in text, f"settings.yaml に曖昧な inquisitor 表記 `{token}` が残っています。")
    require("Trial 統合担当の `inquisitor`" in text, "settings.yaml は Trial 統合担当の `inquisitor` 表記を使ってください。")

    runtime = mapping(settings["guild_runtime"], "settings.guild_runtime")
    ranks = mapping(runtime.get("quest_ranks"), "settings.guild_runtime.quest_ranks")
    require(set(ranks) == QUEST_RANKS, "quest_ranks は mapmaking / errand / solo_quest / party_quest / guild_quest にしてください。")

    default_intake = mapping(settings["default_intake_policy"], "settings.default_intake_policy")
    require(default_intake.get("mode") == "always_guild_intake", "default_intake_policy.mode は always_guild_intake にしてください。")
    require(default_intake.get("target_repo_required_for_target_repo_work") is True, "target repo 作業は target_repo_root 固定を必須にしてください。")
    default_intake_text = json.dumps(default_intake, ensure_ascii=False)
    require_tokens(
        default_intake_text,
        ("Guild intake", "use-guild-workflow", "target_repo_root", "repositories/<repo>", "orchestra-*", "full Quest", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS,
        "settings.default_intake_policy",
    )

    skill_selection = mapping(settings["skill_selection_policy"], "settings.skill_selection_policy")
    require(skill_selection.get("similar_skill_priority") == "prefer_guild_owned", "skill_selection_policy.similar_skill_priority は prefer_guild_owned にしてください。")
    require(skill_selection.get("guild_skill_owner") == "codex-guild-orchestra", "skill_selection_policy.guild_skill_owner は codex-guild-orchestra にしてください。")
    require_tokens(
        json.dumps(skill_selection, ensure_ascii=False),
        GUILD_SKILL_PRIORITY_TOKENS + ("Guild Law", "人間の最新指示", "必須 Skill", "未信頼"),
        "settings.skill_selection_policy",
    )

    guild_law = mapping(settings["guild_law"], "settings.guild_law")
    immutable = sequence(guild_law.get("immutable"), "settings.guild_law.immutable")
    require(immutable, "settings.guild_law.immutable は空にできません。")
    require("human_confirmation_required_for" in guild_law, "settings.guild_law.human_confirmation_required_for が必要です。")

    claude_compat = mapping(settings["claude_compat"], "settings.claude_compat")
    claude_rule = str(claude_compat.get("rule") or "")
    require_tokens(
        claude_rule,
        ("target_repo_root", "Claude artifacts", "未信頼", "AGENTS", "Guild Law", "Quest Charter", "authority", "boundaries", "disposition"),
        "settings.claude_compat.rule",
    )
    helper = mapping(claude_compat.get("helper"), "settings.claude_compat.helper")
    require(helper.get("path") == ".agents/orchestra/scripts/claude_compat.py", "claude_compat.helper.path は claude_compat.py にしてください。")
    require({"scan", "render-context", "render-skill"} <= set(sequence(helper.get("commands"), "settings.claude_compat.helper.commands")), "claude_compat helper command が不足しています。")
    settings_allowlist = set(sequence(claude_compat.get("settings_allowlist"), "settings.claude_compat.settings_allowlist"))
    require({"claudeMdExcludes", "skillOverrides", "strictPluginOnlyCustomization", "disableSkillShellExecution"} <= settings_allowlist, "claude_compat.settings_allowlist が不足しています。")
    unsupported = set(sequence(claude_compat.get("unsupported_execution_surfaces"), "settings.claude_compat.unsupported_execution_surfaces"))
    require({"allowed-tools", "disallowed-tools", "hooks", "MCP", "plugin", "env", "!command", "context: fork", "model_override", "effort_override", "shell"} <= unsupported, "claude_compat.unsupported_execution_surfaces が不足しています。")
    claude_safety = mapping(claude_compat.get("safety"), "settings.claude_compat.safety")
    for key in ("target_repo_only", "reject_symlink_escape", "reject_nested_git_repo", "reject_secret_like_paths"):
        require(claude_safety.get(key) is True, f"claude_compat.safety.{key} は true にしてください。")
    for key in ("execute_dynamic_commands", "install_as_codex_skill", "copy_to_agents_skills", "grant_tools_from_allowed_tools"):
        require(claude_safety.get(key) is False, f"claude_compat.safety.{key} は false にしてください。")
    require(claude_safety.get("raw_content_ledger_policy") == "do_not_record", "claude_compat raw content は Ledger に残さないでください。")
    dispositions = set(sequence(claude_compat.get("dispositions"), "settings.claude_compat.dispositions"))
    require(dispositions == {"applied", "rejected_conflict", "ignored_irrelevant", "skipped_unsafe"}, "claude_compat.dispositions が期待値と一致しません。")

    charter = mapping(settings["quest_charter"], "settings.quest_charter")
    required_fields = set(sequence(charter.get("required_fields"), "settings.quest_charter.required_fields"))
    for key in ("id", "rank", "objective", "success_criteria", "authority", "boundaries", "autonomy_budget", "party_tactics", "trial_plan", "escalation_triggers", "evidence_required", "status"):
        require(key in required_fields, f"Quest Charter required_fields に {key} が必要です。")
    authority_levels = mapping(charter.get("authority_levels"), "settings.quest_charter.authority_levels")
    require(set(authority_levels) == AUTHORITY_KEYS, "authority_levels は read/edit/validate/local_git/external_actions にしてください。")
    autonomy_fields = set(sequence(charter.get("autonomy_budget_fields"), "settings.quest_charter.autonomy_budget_fields"))
    require(autonomy_fields == AUTONOMY_KEYS, "autonomy_budget_fields が期待値と一致しません。")

    party_tactics = mapping(settings["party_tactics"], "settings.party_tactics")
    require("scout_policy" not in party_tactics, "settings.party_tactics.scout_policy を戻さないでください。")
    research_policy = mapping(party_tactics.get("research_policy"), "settings.party_tactics.research_policy")
    require("担当" in str(research_policy.get("rule") or "") and "evidence" in str(research_policy.get("rule") or ""), "research_policy.rule は担当自身の根拠確認を明記してください。")

    trial = mapping(settings["trial"], "settings.trial")
    depths = set(mapping(trial.get("depths"), "settings.trial.depths"))
    require(depths == TRIAL_DEPTHS, "Trial depth が期待値と一致しません。")
    required_checks = set(sequence(trial.get("required_checks"), "settings.trial.required_checks"))
    require(required_checks == TRIAL_REQUIRED_CHECKS, "settings.trial.required_checks が期待値と一致しません。")
    conditional_checks = set(mapping(trial.get("conditional_checks"), "settings.trial.conditional_checks"))
    require(conditional_checks == TRIAL_CONDITIONAL_CHECKS, "settings.trial.conditional_checks が期待値と一致しません。")
    depth_guardrails = set(mapping(trial.get("depth_guardrails"), "settings.trial.depth_guardrails"))
    require(depth_guardrails == TRIAL_DEPTH_GUARDRAILS, "settings.trial.depth_guardrails が期待値と一致しません。")

    workers = mapping(settings["workers"], "settings.workers")
    for role in ("adventurer", "party_leader", "inquisitor", "advisor"):
        role_data = mapping(workers.get(role), f"settings.workers.{role}")
        require(isinstance(role_data.get("max_parallel"), int), f"settings.workers.{role}.max_parallel が必要です。")
    advisor_worker = mapping(workers.get("advisor"), "settings.workers.advisor")
    require(advisor_worker.get("terminal_worker") is True, "settings.workers.advisor.terminal_worker は true にしてください。")
    require("spark" not in workers, "settings.workers.spark を戻さないでください。")

    advisory = mapping(settings["advisory_consultation"], "settings.advisory_consultation")
    allowed_callers = set(sequence(advisory.get("allowed_callers"), "settings.advisory_consultation.allowed_callers"))
    require(allowed_callers == {"cartographer", "guildmaster", "party_leader", "inquisitor"}, "advisory_consultation.allowed_callers が期待値と一致しません。")
    advisory_rule = str(advisory.get("rule") or "")
    require("既定で検討" in advisory_rule and "使わない場合" in advisory_rule, "advisory_consultation.rule は advisor 利用を既定で検討し、使わない理由を残すことを明記してください。")
    default_policy = mapping(advisory.get("default_policy"), "settings.advisory_consultation.default_policy")
    require(default_policy.get("consider_when_subassignments_available") is True, "advisor は subassignments がある時に既定で検討してください。")
    require(default_policy.get("skip_reason_required") is True, "advisor を使わない理由を必須にしてください。")
    high_value_focus = set(sequence(default_policy.get("use_for_high_value_focus"), "settings.advisory_consultation.default_policy.use_for_high_value_focus"))
    require({"mapmaking", "party_quest", "guild_quest", "focused_trial", "multi_focus_trial", "architecture", "safety", "security", "regression", "validation"} <= high_value_focus, "advisor の重点 focus が不足しています。")
    require(advisory.get("terminal_worker") is True, "advisory_consultation.terminal_worker は true にしてください。")
    require(advisory.get("recursive_subagents") is False, "advisory_consultation.recursive_subagents は false にしてください。")
    require(advisory.get("decision_authority") is False, "advisory_consultation.decision_authority は false にしてください。")
    require(advisory.get("owner_synthesis_required") is True, "advisory_consultation.owner_synthesis_required は true にしてください。")
    require(advisory.get("authority_must_not_exceed_owner") is True, "advisory_consultation.authority_must_not_exceed_owner は true にしてください。")
    require(advisory.get("consumes_autonomy_budget") == "subassignments", "advisor は autonomy_budget.subassignments を消費してください。")
    require("実装分業者ではなく" in advisory_rule and "confidence" in advisory_rule, "advisory_consultation.rule は advisor が実装分業者ではなく confidence を高める助言担当であることを明記してください。")
    dialogue = mapping(advisory.get("dialogue"), "settings.advisory_consultation.dialogue")
    require(dialogue.get("enabled") is True, "advisory_consultation.dialogue.enabled は true にしてください。")
    validate_dialogue_policy(dialogue, "settings.advisory_consultation.dialogue")
    validate_percent(dialogue.get("confidence_target_percent_default"), "settings.advisory_consultation.dialogue.confidence_target_percent_default")
    validate_percent(dialogue.get("confidence_delta_min_percent_default"), "settings.advisory_consultation.dialogue.confidence_delta_min_percent_default")
    basis_required = set(sequence(dialogue.get("confidence_basis_required"), "settings.advisory_consultation.dialogue.confidence_basis_required"))
    require({"verified_findings", "validation_evidence", "unresolved_risks", "blocking_unknowns"} <= basis_required, "confidence basis が不足しています。")

    root_session = mapping(settings["root_session"], "settings.root_session")
    root_owns = "\n".join(str(item) for item in sequence(root_session.get("owns"), "settings.root_session.owns"))
    root_avoids = "\n".join(str(item) for item in sequence(root_session.get("avoids"), "settings.root_session.avoids"))
    root_rule = str(root_session.get("rule") or "")
    require("target_repo_root" in root_owns, "root_session.owns は target_repo_root 固定を明記してください。")
    require("Guild Law" in root_owns and "boundaries" in root_owns, "root_session.owns は Guild Law / boundaries 検証を明記してください。")
    require("実装" in root_avoids and "Trial" in root_avoids and "品質採否" in root_avoids, "root_session.avoids は実装・Trial・品質採否を持たないことを明記してください。")
    require("Ledger" in root_avoids and "直接反映" in root_avoids, "root_session.avoids は Ledger 直接反映禁止を明記してください。")
    require("Root" in root_rule and "実装" in root_rule and "Trial" in root_rule and "courier" in root_rule, "root_session.rule は Root / 実装 / Trial / courier の責務境界を明記してください。")

    ledger = mapping(settings["ledger"], "settings.ledger")
    require(ledger.get("source_of_truth") == ".orchestra/queue/state.sqlite", "Ledger source_of_truth は .orchestra/queue/state.sqlite にしてください。")
    ledger_sqlite = mapping(ledger.get("sqlite"), "settings.ledger.sqlite")
    primary_tables = set(sequence(ledger_sqlite.get("primary_tables"), "settings.ledger.sqlite.primary_tables"))
    require(primary_tables == LEDGER_TABLES - {"queue_metadata"}, "settings.ledger.sqlite.primary_tables が SQLite schema と一致しません。")
    artifact_metadata = mapping(ledger.get("artifact_metadata"), "settings.ledger.artifact_metadata")
    for key in ("required_fields", "structured_data_usage_fields", "event_input_required_fields", "event_safety_fields", "allowed_event_types", "allowed_entity_types", "event_entity_type_rules", "operation_allowed_values"):
        require(key in artifact_metadata, f"settings.ledger.artifact_metadata.{key} が必要です。")
    require(sequence(artifact_metadata.get("required_fields"), "settings.ledger.artifact_metadata.required_fields") == ARTIFACT_REQUIRED_FIELDS, "artifact_metadata.required_fields が期待値と一致しません。")
    require(sequence(artifact_metadata.get("structured_data_usage_fields"), "settings.ledger.artifact_metadata.structured_data_usage_fields") == STRUCTURED_DATA_USAGE_FIELDS, "structured_data_usage_fields が期待値と一致しません。")
    require(sequence(artifact_metadata.get("event_input_required_fields"), "settings.ledger.artifact_metadata.event_input_required_fields") == EVENT_INPUT_REQUIRED_FIELDS, "event_input_required_fields が期待値と一致しません。")
    require(sequence(artifact_metadata.get("event_safety_fields"), "settings.ledger.artifact_metadata.event_safety_fields") == EVENT_SAFETY_FIELDS, "event_safety_fields が期待値と一致しません。")
    allowed_event_types = set(sequence(artifact_metadata.get("allowed_event_types"), "settings.ledger.artifact_metadata.allowed_event_types"))
    require(allowed_event_types == EVENT_TYPES, "allowed_event_types が期待値と一致しません。")
    allowed_entity_types = set(sequence(artifact_metadata.get("allowed_entity_types"), "settings.ledger.artifact_metadata.allowed_entity_types"))
    require(allowed_entity_types == ENTITY_TYPES, "allowed_entity_types が期待値と一致しません。")
    require("task" not in allowed_entity_types, "allowed_entity_types に旧 entity `task` を戻さないでください。")
    entity_type_rules = mapping(artifact_metadata.get("event_entity_type_rules"), "settings.ledger.artifact_metadata.event_entity_type_rules")
    require(set(entity_type_rules) == set(EVENT_ENTITY_TYPE_RULES), "event_entity_type_rules の event type が期待値と一致しません。")
    for event_type, entity_types in entity_type_rules.items():
        values = set(sequence(entity_types, f"settings.ledger.artifact_metadata.event_entity_type_rules.{event_type}"))
        require(values == EVENT_ENTITY_TYPE_RULES[event_type], f"{event_type} の entity type が期待値と一致しません。")
        require("task" not in values, f"{event_type} に旧 entity `task` を戻さないでください。")
    operations = set(sequence(artifact_metadata.get("operation_allowed_values"), "settings.ledger.artifact_metadata.operation_allowed_values"))
    require(operations == OPERATIONS, "operation_allowed_values が期待値と一致しません。")


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


def validate_queue_templates() -> None:
    paths = [
        "template/.agents/orchestra/queue/templates/advisor_assignment.yaml",
        "template/.agents/orchestra/queue/templates/advisor_report.yaml",
        "template/.agents/orchestra/queue/templates/adventurer_assignment.yaml",
        "template/.agents/orchestra/queue/templates/cartographer_assignment.yaml",
        "template/.agents/orchestra/queue/templates/cartographer_report.yaml",
        "template/.agents/orchestra/queue/templates/inquisitor_trial.yaml",
        "template/.agents/orchestra/queue/templates/adventurer_report.yaml",
        "template/.agents/orchestra/queue/templates/inquisitor_report.yaml",
        "template/.agents/orchestra/queue/templates/request.yaml",
        "template/.agents/orchestra/queue/templates/command.yaml",
        "template/.agents/orchestra/queue/templates/adventurer_inbox.yaml",
        "template/.agents/orchestra/queue/templates/role_inbox.yaml",
    ]
    for rel in paths:
        doc = mapping(load_yaml(rel), rel)
        validate_template_metadata(doc, rel)
        text = read(rel)
        for token in ("scale:", "risk_dimensions:", "quality_profile:", "spark_request:", "scout_plan:", "scout_usage:", "scout_calls:"):
            require(token not in text, f"{rel} に旧固定 contract `{token}` が残っています。")
        for token in ("enabled: true", "enabled: false", "advisors: [advisor]", "used: false"):
            require(token not in text, f"{rel} に旧 advisor field `{token}` が残っています。")
        for token in VOCABULARY_DRIFT_TERMS:
            require(token not in text, f"{rel} に表記揺れ `{token}` が残っています。")

    assignment = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/adventurer_assignment.yaml"), "adventurer_assignment").get("assignment"), "adventurer_assignment.assignment")
    for key in ("id", "quest_id", "rank", "objective", "success_criteria", "authority", "boundaries", "autonomy_budget", "research_plan", "validation_expectations", "trial_expectations", "escalation_triggers", "evidence_required", "status"):
        require(key in assignment, f"adventurer_assignment.assignment.{key} が必要です。")
    validate_authority(assignment["authority"], "adventurer_assignment.assignment.authority")
    validate_boundaries(assignment["boundaries"], "adventurer_assignment.assignment.boundaries")
    validate_autonomy_budget(assignment["autonomy_budget"], "adventurer_assignment.assignment.autonomy_budget")
    assignment_known_context = mapping(assignment.get("known_context"), "adventurer_assignment.assignment.known_context")
    validate_compat_context(assignment_known_context.get("compat_context"), "adventurer_assignment.assignment.known_context.compat_context")

    cartographer_assignment = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/cartographer_assignment.yaml"), "cartographer_assignment").get("assignment"), "cartographer_assignment.assignment")
    for key in ("id", "quest_id", "worker_id", "role", "kind", "rank", "objective", "success_criteria", "non_goals", "focus", "authority", "boundaries", "known_context", "autonomy_budget", "research_plan", "advisor_consultation", "output_requirements", "escalation_triggers", "evidence_required", "status"):
        require(key in cartographer_assignment, f"cartographer_assignment.assignment.{key} が必要です。")
    require(cartographer_assignment["worker_id"] == "cartographer", "cartographer_assignment.assignment.worker_id は cartographer にしてください。")
    require(cartographer_assignment["kind"] == "mapmaking", "cartographer_assignment.assignment.kind は mapmaking にしてください。")
    require(cartographer_assignment["rank"] == "mapmaking", "cartographer_assignment.assignment.rank は mapmaking にしてください。")
    validate_authority(cartographer_assignment["authority"], "cartographer_assignment.assignment.authority")
    cartographer_authority = mapping(cartographer_assignment["authority"], "cartographer_assignment.assignment.authority")
    require(
        cartographer_authority.get("read") is True
        and cartographer_authority.get("edit") is False
        and cartographer_authority.get("validate") is False
        and cartographer_authority.get("local_git") is False
        and cartographer_authority.get("external_actions") is False,
        "cartographer assignment は read-only にしてください。",
    )
    validate_boundaries(cartographer_assignment["boundaries"], "cartographer_assignment.assignment.boundaries")
    validate_autonomy_budget(cartographer_assignment["autonomy_budget"], "cartographer_assignment.assignment.autonomy_budget")
    cartographer_known_context = mapping(cartographer_assignment.get("known_context"), "cartographer_assignment.assignment.known_context")
    validate_compat_context(cartographer_known_context.get("compat_context"), "cartographer_assignment.assignment.known_context.compat_context")
    cartographer_advisor = mapping(cartographer_assignment.get("advisor_consultation"), "cartographer_assignment.assignment.advisor_consultation")
    require(set(cartographer_advisor) == {"consideration_required", "assignments", "owner_synthesis_required", "terminal_worker_required", "skip_reason_required_when_not_used", "skip_reason"}, "cartographer advisor_consultation は検討必須と skip reason 契約だけにしてください。")
    require(cartographer_advisor.get("consideration_required") is True, "cartographer は advisor を既定で検討対象にしてください。")
    require(cartographer_advisor.get("owner_synthesis_required") is True, "cartographer advisor は owner synthesis を必須にしてください。")
    require(cartographer_advisor.get("terminal_worker_required") is True, "cartographer advisor は terminal worker を必須にしてください。")
    require(cartographer_advisor.get("skip_reason_required_when_not_used") is True, "cartographer advisor を使わない時は理由を必須にしてください。")

    advisor_assignment = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/advisor_assignment.yaml"), "advisor_assignment").get("assignment"), "advisor_assignment.assignment")
    for key in ("id", "quest_id", "parent_id", "worker_id", "role", "kind", "owner_worker_id", "owner_assignment_id", "objective", "focus", "dialogue_policy", "decision_authority", "terminal_worker", "owner_synthesis_required", "authority", "boundaries", "autonomy_budget", "research_plan", "escalation_triggers", "evidence_required", "status"):
        require(key in advisor_assignment, f"advisor_assignment.assignment.{key} が必要です。")
    require(advisor_assignment["worker_id"] == "advisor", "advisor_assignment.assignment.worker_id は advisor にしてください。")
    require(advisor_assignment["decision_authority"] is False, "advisor_assignment.assignment.decision_authority は false にしてください。")
    require(advisor_assignment["terminal_worker"] is True, "advisor_assignment.assignment.terminal_worker は true にしてください。")
    require(advisor_assignment["owner_synthesis_required"] is True, "advisor_assignment.assignment.owner_synthesis_required は true にしてください。")
    dialogue_policy = mapping(advisor_assignment["dialogue_policy"], "advisor_assignment.assignment.dialogue_policy")
    validate_dialogue_policy(dialogue_policy, "advisor_assignment.assignment.dialogue_policy")
    for key in ("confidence_target_percent", "confidence_delta_min_percent"):
        validate_percent(dialogue_policy.get(key), f"advisor_assignment.assignment.dialogue_policy.{key}")
    validate_authority(advisor_assignment["authority"], "advisor_assignment.assignment.authority")
    advisor_authority = mapping(advisor_assignment["authority"], "advisor_assignment.assignment.authority")
    require(advisor_authority.get("read") is True and advisor_authority.get("edit") is False and advisor_authority.get("local_git") is False and advisor_authority.get("external_actions") is False, "advisor は read-only にしてください。")
    validate_boundaries(advisor_assignment["boundaries"], "advisor_assignment.assignment.boundaries")
    validate_autonomy_budget(advisor_assignment["autonomy_budget"], "advisor_assignment.assignment.autonomy_budget")
    advisor_known_context = mapping(advisor_assignment.get("known_context"), "advisor_assignment.assignment.known_context")
    validate_compat_context(advisor_known_context.get("compat_context"), "advisor_assignment.assignment.known_context.compat_context")

    trial = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/inquisitor_trial.yaml"), "inquisitor_trial").get("trial"), "inquisitor_trial.trial")
    for key in ("id", "quest_id", "depth", "focus", "authority", "boundaries", "trial_checks", "depth_guardrails", "autonomy_budget", "research_plan", "decision_options", "evidence_required", "status"):
        require(key in trial, f"inquisitor_trial.trial.{key} が必要です。")
    validate_authority(trial["authority"], "inquisitor_trial.trial.authority")
    validate_boundaries(trial["boundaries"], "inquisitor_trial.trial.boundaries")
    validate_autonomy_budget(trial["autonomy_budget"], "inquisitor_trial.trial.autonomy_budget")
    trial_checks = set(sequence(trial["trial_checks"], "inquisitor_trial.trial.trial_checks"))
    expected_trial_checks = TRIAL_REQUIRED_CHECKS | TRIAL_CONDITIONAL_CHECKS
    require(trial_checks == expected_trial_checks, "inquisitor_trial.trial.trial_checks が期待値と一致しません。")
    depth_guardrails = mapping(trial["depth_guardrails"], "inquisitor_trial.trial.depth_guardrails")
    require(set(depth_guardrails) == TRIAL_DEPTH_GUARDRAILS, "inquisitor_trial.trial.depth_guardrails が期待値と一致しません。")
    multi_focus_guardrail = mapping(depth_guardrails["multi_focus_trial"], "inquisitor_trial.trial.depth_guardrails.multi_focus_trial")
    require(multi_focus_guardrail.get("requires_focus_split") is True, "multi_focus_trial は focus 分割を必須にしてください。")
    require(multi_focus_guardrail.get("allows_focus_advisors") is True, "multi_focus_trial は focus advisor を許可してください。")
    require(multi_focus_guardrail.get("requires_owner_synthesis") is True, "multi_focus_trial は owner synthesis を必須にしてください。")
    require(multi_focus_guardrail.get("if_focus_is_insufficient") == "request_changes", "multi_focus_trial の focus 不足時は request_changes にしてください。")
    focus_advisors = mapping(trial.get("focus_advisors"), "inquisitor_trial.trial.focus_advisors")
    require(set(focus_advisors) == {"consideration_required", "assignments", "owner_synthesis_required", "terminal_worker_required", "skip_reason_required_when_not_used", "skip_reason"}, "focus_advisors は検討必須と skip reason 契約だけにしてください。")
    require(focus_advisors.get("consideration_required") is True, "inquisitor_trial は focus advisor を既定で検討対象にしてください。")
    require(focus_advisors.get("owner_synthesis_required") is True, "focus advisor は owner synthesis を必須にしてください。")
    require(focus_advisors.get("terminal_worker_required") is True, "focus advisor は terminal worker を必須にしてください。")
    require(focus_advisors.get("skip_reason_required_when_not_used") is True, "focus advisor を使わない時は理由を必須にしてください。")
    require("skip_reason" in focus_advisors, "focus advisor を使わない理由欄が必要です。")
    trial_research_plan = mapping(trial.get("research_plan"), "inquisitor_trial.trial.research_plan")
    validate_compat_context(trial_research_plan.get("compat_context"), "inquisitor_trial.trial.research_plan.compat_context")
    trial_budget = mapping(trial["autonomy_budget"], "inquisitor_trial.trial.autonomy_budget")
    require(isinstance(trial_budget.get("subassignments"), int) and trial_budget.get("subassignments") >= 1, "inquisitor_trial は advisor 検討用の subassignments を 1 以上にしてください。")
    safety_gate_guardrail = mapping(depth_guardrails["safety_gate"], "inquisitor_trial.trial.depth_guardrails.safety_gate")
    require(safety_gate_guardrail.get("requires_human_or_safety_evidence") is True, "safety_gate は人間確認または安全確認 evidence を必須にしてください。")
    require(safety_gate_guardrail.get("if_evidence_is_missing") == "needs_human", "safety_gate の evidence 不足時は needs_human にしてください。")

    cartographer_report = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/cartographer_report.yaml"), "cartographer_report").get("report"), "cartographer_report.report")
    for key in ("id", "quest_id", "assignment_id", "worker_id", "target_repo_root", "status", "summary", "objective", "success_criteria", "terrain_map", "risk_zones", "recommended_quest_rank", "recommended_party_tactics", "recommended_trial", "advisor_usage", "advisor_synthesis", "unknowns", "research_evidence", "confidence", "risks", "evidence_refs"):
        require(key in cartographer_report, f"cartographer_report.report.{key} が必要です。")
    require(cartographer_report["worker_id"] == "cartographer", "cartographer_report.report.worker_id は cartographer にしてください。")
    terrain_map = mapping(cartographer_report["terrain_map"], "cartographer_report.report.terrain_map")
    require(set(terrain_map) == {"existing_structure", "relevant_paths", "dependencies", "candidate_routes"}, "cartographer_report.report.terrain_map が期待値と一致しません。")
    recommended_rank = mapping(cartographer_report["recommended_quest_rank"], "cartographer_report.report.recommended_quest_rank")
    require(recommended_rank.get("rank") == "mapmaking", "cartographer_report.report.recommended_quest_rank.rank は mapmaking にしてください。")
    cartographer_report_advisor = mapping(cartographer_report["advisor_usage"], "cartographer_report.report.advisor_usage")
    require(set(cartographer_report_advisor) == {"considered", "used", "skip_reason_required_when_not_used", "skip_reason"}, "cartographer_report.report.advisor_usage は検討結果と skip reason 契約だけにしてください。")
    require(cartographer_report_advisor.get("considered") is True, "cartographer_report.report.advisor_usage.considered は true にしてください。")
    require(cartographer_report_advisor.get("used") is None, "cartographer_report.report.advisor_usage.used は draft で採否を先取りしないでください。")
    require(cartographer_report_advisor.get("skip_reason_required_when_not_used") is True, "cartographer_report.report.advisor_usage.skip_reason_required_when_not_used は true にしてください。")
    cartographer_synthesis = mapping(cartographer_report["advisor_synthesis"], "cartographer_report.report.advisor_synthesis")
    require(cartographer_synthesis.get("raw_discussion_recorded") is False, "cartographer_report.report.advisor_synthesis.raw_discussion_recorded は false にしてください。")
    cartographer_research = mapping(cartographer_report.get("research_evidence"), "cartographer_report.report.research_evidence")
    validate_compat_context(cartographer_research.get("compat_context"), "cartographer_report.report.research_evidence.compat_context")

    for rel in ("template/.agents/orchestra/queue/templates/adventurer_report.yaml", "template/.agents/orchestra/queue/templates/inquisitor_report.yaml"):
        report = mapping(mapping(load_yaml(rel), rel).get("report"), f"{rel}.report")
        for key in ("id", "quest_id", "worker_id", "status", "summary", "validation_evidence", "research_evidence", "confidence", "risks", "evidence_refs"):
            require(key in report, f"{rel}.report.{key} が必要です。")
        report_research = mapping(report.get("research_evidence"), f"{rel}.report.research_evidence")
        validate_compat_context(report_research.get("compat_context"), f"{rel}.report.research_evidence.compat_context")
        if rel.endswith("inquisitor_report.yaml"):
            advisor_usage = mapping(report.get("advisor_usage"), f"{rel}.report.advisor_usage")
            require(set(advisor_usage) == {"considered", "used", "skip_reason_required_when_not_used", "skip_reason"}, f"{rel}.report.advisor_usage は検討結果と skip reason 契約だけにしてください。")
            for key in ("considered", "used", "skip_reason_required_when_not_used", "skip_reason"):
                require(key in advisor_usage, f"{rel}.report.advisor_usage.{key} が必要です。")
            require(advisor_usage.get("considered") is True, f"{rel}.report.advisor_usage.considered は true にしてください。")
            require(advisor_usage.get("used") is None, f"{rel}.report.advisor_usage.used は draft で採否を先取りしないでください。")
            require(advisor_usage.get("skip_reason_required_when_not_used") is True, f"{rel}.report.advisor_usage.skip_reason_required_when_not_used は true にしてください。")
            dialogue_synthesis = mapping(report.get("advisor_dialogue_synthesis"), f"{rel}.report.advisor_dialogue_synthesis")
            require(dialogue_synthesis.get("raw_discussion_recorded") is False, f"{rel}.report.advisor_dialogue_synthesis.raw_discussion_recorded は false にしてください。")
            for key in ("confidence_target_percent", "owner_confidence_percent", "previous_confidence_percent", "confidence_delta_percent", "new_evidence_refs", "blocking_unknowns_resolved", "blocking_unknowns_remaining", "continue_or_stop", "stop_reason"):
                require(key in dialogue_synthesis, f"{rel}.report.advisor_dialogue_synthesis.{key} が必要です。")
    advisor_report = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/advisor_report.yaml"), "advisor_report").get("report"), "advisor_report.report")
    for key in ("id", "quest_id", "assignment_id", "worker_id", "owner_worker_id", "status", "decision_authority", "terminal_worker", "owner_synthesis_required", "summary", "focus", "findings", "risks", "unknowns", "confidence_percent", "confidence_basis", "confidence_delta_percent", "new_evidence_refs", "blocking_unknowns_resolved", "blocking_unknowns_remaining", "recommended_next_focus", "research_evidence", "confidence", "evidence_refs"):
        require(key in advisor_report, f"advisor_report.report.{key} が必要です。")
    require(advisor_report["worker_id"] == "advisor", "advisor_report.report.worker_id は advisor にしてください。")
    require(advisor_report["decision_authority"] is False, "advisor_report.report.decision_authority は false にしてください。")
    require(advisor_report["terminal_worker"] is True, "advisor_report.report.terminal_worker は true にしてください。")
    require(advisor_report["owner_synthesis_required"] is True, "advisor_report.report.owner_synthesis_required は true にしてください。")
    confidence_basis = mapping(advisor_report["confidence_basis"], "advisor_report.report.confidence_basis")
    require(set(confidence_basis) == {"verified_findings", "validation_evidence", "unresolved_risks", "blocking_unknowns"}, "advisor_report.report.confidence_basis が期待値と一致しません。")
    advisor_research = mapping(advisor_report.get("research_evidence"), "advisor_report.report.research_evidence")
    validate_compat_context(advisor_research.get("compat_context"), "advisor_report.report.research_evidence.compat_context")


def validate_sqlite_schema() -> None:
    schema = read("template/.agents/orchestra/scripts/queue_schema.sql")
    require("assignment_id TEXT NOT NULL PRIMARY KEY" in schema, "assignments table は assignment_id を primary key にしてください。")
    require("task_id" not in schema, "SQLite schema に旧 column `task_id` を戻さないでください。")
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(schema)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    missing = sorted(LEDGER_TABLES - tables)
    require(not missing, "SQLite schema に不足 table があります: " + ", ".join(missing))


def validate_queue_db_smoke() -> None:
    script = ROOT / "template/.agents/orchestra/scripts/queue_db.py"
    audit_script = ROOT / "template/.agents/orchestra/scripts/queue_audit.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(result.returncode == 0, "queue_db.py --help が失敗しました: " + result.stderr)
    text = read("template/.agents/orchestra/scripts/queue_db.py")
    require_tokens(
        text,
        (
            "quest",
            "trial",
            "target_repo_root",
            "mode=ro",
            "record-event",
            "add-inbox-message",
            "dump",
            "ALLOWED_OPERATIONS",
            "REQUIRED_EVENT_INPUT_FIELDS",
            "STRUCTURED_DATA_USAGE_FIELDS",
            "EVENT_SAFETY_FIELDS",
            "REQUIRED_TABLES",
            "REQUIRED_COLUMNS",
            "LEGACY_JSON_KEYS",
            "RETIRED_AGENT_VALUES",
        ),
        "queue_db.py",
    )
    operation_constant = 'ALLOWED_OPERATIONS = {"append", "update", "replace", "mark_completed"}'
    require(operation_constant in text, "queue_db.py の ALLOWED_OPERATIONS が settings と一致しません。")
    require('"task_id"' in text and "LEGACY_COLUMNS" in text, "queue_db.py は旧 assignments.task_id を物理 schema mismatch として検出してください。")
    audit_text = read("template/.agents/orchestra/scripts/queue_audit.py")
    require_tokens(audit_text, ("ALLOWED_OPERATIONS", "operation", "REQUIRED_EVENT_INPUT_FIELDS", "STRUCTURED_DATA_USAGE_FIELDS", "EVENT_SAFETY_FIELDS", "REQUIRED_TABLES", "REQUIRED_COLUMNS", "LEGACY_TABLES", "LEGACY_COLUMNS", "LEGACY_JSON_KEYS", "RETIRED_AGENT_VALUES"), "queue_audit.py")
    require(operation_constant in audit_text, "queue_audit.py の ALLOWED_OPERATIONS が settings と一致しません。")
    db_legacy_keys = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "LEGACY_JSON_KEYS")
    audit_legacy_keys = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "LEGACY_JSON_KEYS")
    install_legacy_keys = python_string_set_constant("scripts/install.py", "LEGACY_RUNTIME_JSON_KEYS")
    db_retired_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_db.py", "RETIRED_AGENT_VALUES")
    audit_retired_values = python_string_set_constant("template/.agents/orchestra/scripts/queue_audit.py", "RETIRED_AGENT_VALUES")
    install_retired_values = python_string_set_constant("scripts/install.py", "RETIRED_AGENT_VALUES")
    require(db_legacy_keys == audit_legacy_keys, "queue_db.py と queue_audit.py の LEGACY_JSON_KEYS を一致させてください。")
    require(db_legacy_keys == install_legacy_keys, "queue_db.py と install.py の旧 JSON key 一覧を一致させてください。")
    require(db_retired_values == audit_retired_values, "queue_db.py と queue_audit.py の RETIRED_AGENT_VALUES を一致させてください。")
    require(db_retired_values == install_retired_values, "queue_db.py と install.py の RETIRED_AGENT_VALUES を一致させてください。")
    require({"scout_plan", "scout_usage", "scout_calls", "scout_policy", "spark_request"}.issubset(db_legacy_keys), "Scout/spark 旧 JSON key は legacy set に含めてください。")
    executable_paths = [
        ROOT / "template/.agents/orchestra/scripts/queue_db.py",
        ROOT / "template/.agents/orchestra/scripts/queue_audit.py",
        ROOT / "template/.agents/orchestra/scripts/inbox_write.sh",
    ]
    for executable_path in executable_paths:
        require(executable_path.stat().st_mode & 0o111, f"{executable_path.relative_to(ROOT)} の executable bit を維持してください。")
    inbox_script = executable_paths[2]
    inbox_text = read("template/.agents/orchestra/scripts/inbox_write.sh")
    for role in ("receptionist", "guildmaster", "cartographer", "courier", "party_leader", "inquisitor", "adventurer", "advisor"):
        require(f"'{role}'" in inbox_text or f'"{role}"' in inbox_text, f"inbox_write.sh の role allowlist に {role} が必要です。")
    shell = subprocess.run(
        ["bash", "-n", str(inbox_script)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(shell.returncode == 0, "inbox_write.sh の shell syntax check が失敗しました: " + shell.stderr)

    invalid_event = {
        "event_id": "evt_invalid_operation",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "validator",
        "event_type": "status_changed",
        "entity": {"type": "status", "id": "invalid_operation"},
        "operation": "merge",
        "workflow_id": None,
        "structured_data_usage": {"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []},
        "payload": {},
        "event_safety": {"safety_items": [], "human_confirmation_required": []},
    }
    invalid_trial_depth_event = {
        "event_id": "evt_invalid_trial_depth",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "validator",
        "event_type": "trial_recorded",
        "entity": {"type": "trial", "id": "invalid_trial_depth"},
        "operation": "append",
        "workflow_id": None,
        "structured_data_usage": {"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []},
        "payload": {"trial": {"id": "invalid_trial_depth", "depth": "", "status": "draft"}},
        "event_safety": {"safety_items": [], "human_confirmation_required": []},
    }
    invalid_report_trial_depth_event = {
        "event_id": "evt_invalid_report_trial_depth",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "validator",
        "event_type": "report_recorded",
        "entity": {"type": "report", "id": "invalid_report_trial_depth"},
        "operation": "append",
        "workflow_id": None,
        "structured_data_usage": {"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []},
        "payload": {"report": {"id": "invalid_report_trial_depth", "worker_id": "inquisitor", "trial_depth": "", "status": "draft"}},
        "event_safety": {"safety_items": [], "human_confirmation_required": []},
    }
    legacy_scout_keys = ("scout_plan", "scout_usage", "scout_calls", "scout_policy", "spark_request")
    retired_spark_assignment_event = {
        "event_id": "evt_retired_spark_assignment",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "validator",
        "event_type": "assignment_created",
        "entity": {"type": "assignment", "id": "retired_spark_assignment"},
        "operation": "append",
        "workflow_id": None,
        "structured_data_usage": {"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []},
        "payload": {"assignment": {"id": "retired_spark_assignment", "worker_id": "spark", "status": "idle"}},
        "event_safety": {"safety_items": [], "human_confirmation_required": []},
    }
    retired_spark_message = {
        "id": "msg_retired_spark",
        "sender": "validator",
        "recipient": "spark",
        "created_at": "2026-01-01T00:00:00+00:00",
        "type": "message",
        "trusted": False,
        "payload": {"summary": "negative smoke"},
        "status": "unread",
    }
    missing_inbox_field_message = {
        "id": "msg_missing_created_at",
        "sender": "validator",
        "recipient": "adventurer",
        "type": "message",
        "trusted": False,
        "payload": {"summary": "negative smoke"},
        "status": "unread",
    }
    missing_workflow_id_event = {
        "event_id": "evt_missing_workflow_id",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "validator",
        "event_type": "status_changed",
        "entity": {"type": "status", "id": "missing_workflow_id"},
        "operation": "append",
        "structured_data_usage": {"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []},
        "payload": {},
        "event_safety": {"safety_items": [], "human_confirmation_required": []},
    }

    def sqlite_tables(database: Path) -> set[str]:
        with sqlite3.connect(database) as connection:
            return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    with tempfile.TemporaryDirectory() as tmp:
        runtime_root = Path(tmp) / ".orchestra"
        database = runtime_root / "queue" / "state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute(" ".join(["CREATE", "TABLE", "tickets(ticket_id", "TEXT", "PRIMARY", "KEY)"]))
            connection.execute(" ".join(["CREATE", "TABLE", "assignments(task_id", "TEXT", "PRIMARY", "KEY,", "status", "TEXT)"]))
            connection.execute(" ".join(["INSERT", "INTO", "assignments(task_id,", "status)", "VALUES('legacy_task_smoke',", "'active')"]))
            connection.commit()
        before_tables = sqlite_tables(database)
        legacy_init = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "init"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        legacy_output = legacy_init.stdout + legacy_init.stderr
        require(legacy_init.returncode != 0, "queue_db.py init は legacy runtime DB を schema 適用前に拒否してください。")
        require(
            "--backup --reset-runtime" in legacy_output and "--clean-install" in legacy_output and ("tickets" in legacy_output or "task_id" in legacy_output),
            "queue_db.py init の旧 schema 拒否文言は reset-runtime / clean-install と不一致詳細を案内してください。",
        )
        require(sqlite_tables(database) == before_tables, "queue_db.py init は旧 DB 拒否時に途中作成 table を増やさないでください。")

        legacy_audit = subprocess.run(
            [sys.executable, str(audit_script), "--runtime-root", str(runtime_root), "--static-root", str(ROOT / "template/.agents/orchestra"), "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        legacy_audit_output = legacy_audit.stdout + legacy_audit.stderr
        require(legacy_audit.returncode != 0, "queue_audit.py は legacy runtime DB を拒否してください。")
        require("Traceback" not in legacy_audit_output and "IndexError" not in legacy_audit_output, "queue_audit.py は legacy runtime DB を traceback で失敗させないでください。")
        try:
            legacy_audit_json = json.loads(legacy_audit.stdout)
        except json.JSONDecodeError as exc:
            raise ValidationError("queue_audit.py --json は legacy runtime DB でも structured JSON を返してください。") from exc
        require(isinstance(legacy_audit_json.get("errors"), list), "queue_audit.py --json の legacy runtime DB 失敗は errors list を返してください。")
        require(
            "tickets" in legacy_audit_output and "task_id" in legacy_audit_output,
            "queue_audit.py は legacy table/column を明示して検出してください。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        runtime_root = Path(tmp) / ".orchestra"
        init = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "init"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(init.returncode == 0, "queue_db.py init が失敗しました: " + init.stderr)
        reinit = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "init"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(reinit.returncode == 0, "queue_db.py init は既存 v3 DB への再実行に成功してください: " + reinit.stderr)

        def valid_event(event_id: str, event_type: str, entity_type: str, entity_id: str, payload: dict[str, object]) -> dict[str, object]:
            return {
                "event_id": event_id,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "actor": "validator",
                "event_type": event_type,
                "entity": {"type": entity_type, "id": entity_id},
                "operation": "append",
                "workflow_id": "workflow_smoke",
                "structured_data_usage": {"structured_inputs": ["validator_smoke"], "decision_rationale": "positive smoke", "evidence_refs": ["scripts/validate.py"]},
                "payload": payload,
                "event_safety": {"safety_items": [], "human_confirmation_required": []},
            }

        positive_events = [
            valid_event(
                "evt_smoke_quest_created",
                "quest_created",
                "quest",
                "quest_smoke",
                {"quest": {"id": "quest_smoke", "rank": "solo_quest", "status": "active", "workflow_id": "workflow_smoke"}},
            ),
            valid_event(
                "evt_smoke_assignment_created",
                "assignment_created",
                "assignment",
                "assignment_smoke",
                {"assignment": {"id": "assignment_smoke", "quest_id": "quest_smoke", "worker_id": "adventurer", "kind": "implementation", "status": "active", "workflow_id": "workflow_smoke"}},
            ),
            valid_event(
                "evt_smoke_advisor_assignment_created",
                "assignment_created",
                "assignment",
                "advisor_assignment_smoke",
                {
                    "assignment": {
                        "id": "advisor_assignment_smoke",
                        "quest_id": "quest_smoke",
                        "parent_id": "assignment_smoke",
                        "owner_assignment_id": "assignment_smoke",
                        "worker_id": "advisor",
                        "role": "advisory_specialist",
                        "kind": "advisory_consultation",
                        "decision_authority": False,
                        "terminal_worker": True,
                        "status": "active",
                        "workflow_id": "workflow_smoke",
                    }
                },
            ),
            valid_event(
                "evt_smoke_advisor_report_recorded",
                "report_recorded",
                "report",
                "advisor_report_smoke",
                {
                    "report": {
                        "id": "advisor_report_smoke",
                        "quest_id": "quest_smoke",
                        "worker_id": "advisor",
                        "decision_authority": False,
                        "terminal_worker": True,
                        "status": "recorded",
                        "workflow_id": "workflow_smoke",
                    }
                },
            ),
            valid_event(
                "evt_smoke_trial_recorded",
                "trial_recorded",
                "trial",
                "trial_smoke",
                {"trial": {"id": "trial_smoke", "quest_id": "quest_smoke", "depth": "peer_review", "status": "recorded", "workflow_id": "workflow_smoke"}},
            ),
        ]
        for event in positive_events:
            recorded = subprocess.run(
                [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(event)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            require(recorded.returncode == 0, f"queue_db.py positive smoke が失敗しました: {recorded.stderr}")

        database = runtime_root / "queue" / "state.sqlite"
        with sqlite3.connect(database) as connection:
            counts = {
                "events": connection.execute("SELECT COUNT(*) FROM events WHERE workflow_id = 'workflow_smoke'").fetchone()[0],
                "quests": connection.execute("SELECT COUNT(*) FROM quests WHERE quest_id = 'quest_smoke'").fetchone()[0],
                "assignments": connection.execute("SELECT COUNT(*) FROM assignments WHERE workflow_id = 'workflow_smoke'").fetchone()[0],
                "reports": connection.execute("SELECT COUNT(*) FROM reports WHERE report_id = 'advisor_report_smoke'").fetchone()[0],
                "trials": connection.execute("SELECT COUNT(*) FROM trials WHERE trial_id = 'trial_smoke'").fetchone()[0],
            }
            advisor_assignment_kind, advisor_parent_id = connection.execute("SELECT kind, parent_id FROM assignments WHERE assignment_id = 'advisor_assignment_smoke'").fetchone()
        require(counts == {"events": 5, "quests": 1, "assignments": 2, "reports": 1, "trials": 1}, f"queue_db.py positive smoke の反映件数が不正です: {counts}")
        require(advisor_assignment_kind == "advisory_consultation", "queue_db.py は assignment.kind を role で上書きしないでください。")
        require(advisor_parent_id == "assignment_smoke", "queue_db.py は advisor assignment の owner_assignment_id を normalized parent_id に保存してください。")
        dump = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "dump", "assignments"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(dump.returncode == 0 and "assignment_smoke" in dump.stdout and "task_id" not in dump.stdout, "queue_db.py dump assignments の positive smoke が不正です。")

        inbox_created_at = "2026-01-02T03:04:05+00:00"
        valid_message = {
            "id": "msg_valid_smoke",
            "sender": "validator",
            "recipient": "adventurer",
            "created_at": inbox_created_at,
            "type": "message",
            "trusted": False,
            "workflow_id": "workflow_smoke",
            "payload": {"summary": "positive smoke"},
            "status": "unread",
        }
        valid_inbox = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "add-inbox-message", json.dumps(valid_message)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(valid_inbox.returncode == 0, "queue_db.py add-inbox-message の positive smoke が失敗しました: " + valid_inbox.stderr)
        with sqlite3.connect(database) as connection:
            stored_message = connection.execute("SELECT created_at, payload_json FROM inbox_messages WHERE message_id = 'msg_valid_smoke'").fetchone()
        require(stored_message is not None and stored_message[0] == inbox_created_at, "queue_db.py は message.created_at を inbox_messages.created_at に保存してください。")
        require(json.loads(stored_message[1])["created_at"] == inbox_created_at, "queue_db.py は message.created_at を payload_json にも保持してください。")

        invalid = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(invalid_event)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(invalid.returncode != 0 and "operation" in invalid.stderr, "queue_db.py は invalid operation を拒否してください。")
        invalid_depth = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(invalid_trial_depth_event)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(invalid_depth.returncode != 0 and "trial.depth" in invalid_depth.stderr, "queue_db.py は空の Trial depth を拒否してください。")
        invalid_report_depth = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(invalid_report_trial_depth_event)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(invalid_report_depth.returncode != 0 and "report.trial_depth" in invalid_report_depth.stderr, "queue_db.py は空の report.trial_depth を拒否してください。")
        missing_workflow_id = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(missing_workflow_id_event)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(missing_workflow_id.returncode != 0 and "workflow_id" in missing_workflow_id.stderr, "queue_db.py は workflow_id key missing event を拒否してください。")
        missing_inbox_field = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "add-inbox-message", json.dumps(missing_inbox_field_message)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(missing_inbox_field.returncode != 0 and "created_at" in missing_inbox_field.stderr, "queue_db.py は required inbox message field missing を拒否してください。")
        for legacy_key in legacy_scout_keys:
            legacy_scout_payload_event = {
                "event_id": f"evt_legacy_{legacy_key}",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "actor": "validator",
                "event_type": "assignment_created",
                "entity": {"type": "assignment", "id": f"legacy_{legacy_key}"},
                "operation": "append",
                "workflow_id": None,
                "structured_data_usage": {"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []},
                "payload": {"assignment": {"id": f"legacy_{legacy_key}", "worker_id": "adventurer", legacy_key: {"questions": []}, "status": "idle"}},
                "event_safety": {"safety_items": [], "human_confirmation_required": []},
            }
            legacy_scout_payload = subprocess.run(
                [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(legacy_scout_payload_event)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            require(legacy_scout_payload.returncode != 0 and legacy_key in legacy_scout_payload.stderr, f"queue_db.py は legacy {legacy_key} payload を拒否してください。")
        retired_spark_assignment = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "record-event", json.dumps(retired_spark_assignment_event)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(retired_spark_assignment.returncode != 0 and "spark" in retired_spark_assignment.stderr, "queue_db.py は廃止済み spark assignment を拒否してください。")
        retired_message = subprocess.run(
            [sys.executable, str(script), "--runtime-root", str(runtime_root), "add-inbox-message", json.dumps(retired_spark_message)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(retired_message.returncode != 0 and "spark" in retired_message.stderr, "queue_db.py は廃止済み spark recipient を拒否してください。")

        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                INSERT INTO events(
                  event_id, timestamp, actor, event_type, entity_type, entity_id, entity_json,
                  operation, workflow_id, structured_data_usage_json, payload_json, event_safety_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "evt_audit_invalid_operation",
                    "2026-01-01T00:00:00+00:00",
                    "validator",
                    "status_changed",
                    "status",
                    "invalid_operation",
                    json.dumps({"type": "status", "id": "invalid_operation"}),
                    "merge",
                    None,
                    json.dumps({"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []}),
                    json.dumps({}),
                    json.dumps({"safety_items": [], "human_confirmation_required": []}),
                ),
            )
            connection.execute(
                """
                INSERT INTO events(
                  event_id, timestamp, actor, event_type, entity_type, entity_id, entity_json,
                  operation, workflow_id, structured_data_usage_json, payload_json, event_safety_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "evt_audit_invalid_report_trial_depth",
                    "2026-01-01T00:00:00+00:00",
                    "validator",
                    "report_recorded",
                    "report",
                    "invalid_report_trial_depth",
                    json.dumps({"type": "report", "id": "invalid_report_trial_depth"}),
                    "append",
                    None,
                    json.dumps({"structured_inputs": [], "decision_rationale": "negative smoke", "evidence_refs": []}),
                    json.dumps({"report": {"id": "invalid_report_trial_depth", "trial_depth": ""}}),
                    json.dumps({"safety_items": [], "human_confirmation_required": []}),
                ),
            )
            connection.execute(
                """
                INSERT INTO reports(report_id, worker_id, workflow_id, decision, status, payload_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    "invalid_report_trial_depth",
                    "inquisitor",
                    None,
                    None,
                    "draft",
                    json.dumps({"id": "invalid_report_trial_depth", "trial_depth": ""}),
                ),
            )
            connection.execute(
                """
                INSERT INTO assignments(assignment_id, parent_id, worker_id, kind, workflow_id, status, payload_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "audit_legacy_scout_assignment",
                    "quest_smoke",
                    "spark",
                    "assignment",
                    "workflow_smoke",
                    "active",
                    json.dumps({
                        "id": "audit_legacy_scout_assignment",
                        "worker_id": "spark",
                        "scout_plan": {},
                        "scout_usage": {},
                        "scout_calls": 1,
                        "scout_policy": {},
                        "spark_request": {},
                    }),
                ),
            )
            connection.execute(
                """
                INSERT INTO assignments(assignment_id, parent_id, worker_id, kind, workflow_id, status, payload_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "audit_bad_advisor_parent",
                    "quest_smoke",
                    "advisor",
                    "advisory_consultation",
                    "workflow_smoke",
                    "active",
                    json.dumps({
                        "id": "audit_bad_advisor_parent",
                        "quest_id": "quest_smoke",
                        "owner_assignment_id": "assignment_smoke",
                        "worker_id": "advisor",
                        "kind": "advisory_consultation",
                    }),
                ),
            )
            connection.execute(
                """
                INSERT INTO inbox_messages(message_id, recipient, workflow_id, status, payload_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    "audit_legacy_spark_message",
                    "spark",
                    "workflow_smoke",
                    "unread",
                    json.dumps({"id": "audit_legacy_spark_message", "recipient": "spark"}),
                ),
            )
            connection.commit()
        audit = subprocess.run(
            [sys.executable, str(audit_script), "--runtime-root", str(runtime_root), "--static-root", str(ROOT / "template/.agents/orchestra"), "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(audit.returncode != 0 and "operation" in (audit.stdout + audit.stderr), "queue_audit.py は invalid operation を検出してください。")
        require(audit.returncode != 0 and "trial_depth" in (audit.stdout + audit.stderr), "queue_audit.py は invalid report.trial_depth を検出してください。")
        for legacy_key in legacy_scout_keys:
            require(audit.returncode != 0 and legacy_key in (audit.stdout + audit.stderr), f"queue_audit.py は legacy {legacy_key} payload を検出してください。")
        require(audit.returncode != 0 and "spark" in (audit.stdout + audit.stderr), "queue_audit.py は廃止済み spark 値を検出してください。")
        require(audit.returncode != 0 and "parent_id" in (audit.stdout + audit.stderr), "queue_audit.py は advisor assignment parent_id 不整合を検出してください。")


def validate_install_upgrade_smoke() -> None:
    install_script = ROOT / "scripts/install.py"
    legacy_template_paths = [
        Path(".codex/agents/spark.toml"),
        Path(".agents/orchestra/queue/templates/adventurer_task.yaml"),
        Path(".agents/orchestra/queue/templates/inquisitor_task.yaml"),
    ]

    def run_install_with_mutated_source(mutation: str, mutate: object) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            source = temp_root / "template"
            target = temp_root / "guild"
            shutil.copytree(ROOT / "template", source)
            mutate(source)
            result = subprocess.run(
                [sys.executable, str(install_script), "--target", str(target), "--source", str(source), "--mode", "copy", "--dry-run"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            require(result.returncode != 0, f"install.py は不正な source template を拒否してください: {mutation}")
            return result

    def replace_text(path: Path, old: str, new: str) -> None:
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    bad_depth = run_install_with_mutated_source(
        "agents.max_depth != 4",
        lambda source: replace_text(source / ".codex/config.toml", "max_depth = 4", "max_depth = 3"),
    )
    require("agents.max_depth" in (bad_depth.stdout + bad_depth.stderr), "install.py の max_depth 拒否 message は対象 field を示してください。")

    missing_advisor = run_install_with_mutated_source(
        "missing advisor.toml",
        lambda source: (source / ".codex/agents/advisor.toml").unlink(),
    )
    require("advisor.toml" in (missing_advisor.stdout + missing_advisor.stderr), "install.py の advisor 不足拒否 message は advisor.toml を示してください。")

    writable_advisor = run_install_with_mutated_source(
        "advisor not read-only",
        lambda source: replace_text(source / ".codex/agents/advisor.toml", 'sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'),
    )
    require("sandbox_mode" in (writable_advisor.stdout + writable_advisor.stderr), "install.py の advisor sandbox 拒否 message は sandbox_mode を示してください。")

    weak_advisor_reasoning = run_install_with_mutated_source(
        "advisor reasoning not xhigh",
        lambda source: replace_text(source / ".codex/agents/advisor.toml", 'model_reasoning_effort = "xhigh"', 'model_reasoning_effort = "high"'),
    )
    require("model_reasoning_effort" in (weak_advisor_reasoning.stdout + weak_advisor_reasoning.stderr), "install.py の advisor reasoning 拒否 message は model_reasoning_effort を示してください。")

    weak_advisor_contract = run_install_with_mutated_source(
        "advisor 契約不足",
        lambda source: replace_text(source / ".codex/agents/advisor.toml", "追加 subagent 起動", "追加相談"),
    )
    require("developer_instructions" in (weak_advisor_contract.stdout + weak_advisor_contract.stderr), "install.py の advisor 契約拒否 message は developer_instructions を示してください。")

    with tempfile.TemporaryDirectory() as tmp:
        incompatible_target = Path(tmp) / "incompatible-guild"
        database = incompatible_target / ".orchestra/queue/state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute(" ".join(["CREATE", "TABLE", "tickets(ticket_id", "TEXT", "PRIMARY", "KEY)"]))
            connection.execute(" ".join(["CREATE", "TABLE", "assignments(task_id", "TEXT", "PRIMARY", "KEY,", "status", "TEXT)"]))
            connection.commit()

        incompatible = subprocess.run(
            [sys.executable, str(install_script), "--target", str(incompatible_target), "--mode", "copy", "--backup"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        incompatible_output = incompatible.stdout + incompatible.stderr
        require(incompatible.returncode != 0, "install.py は v2 風 runtime DB の通常更新を拒否してください。")
        require(
            "--backup --reset-runtime" in incompatible_output and "--clean-install" in incompatible_output,
            "install.py の v2 風 DB 拒否 message は reset-runtime / clean-install を案内してください。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        old_version_target = Path(tmp) / "old-version-guild"
        database = old_version_target / ".orchestra/queue/state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute(" ".join(["CREATE", "TABLE", "queue_metadata(key", "TEXT", "NOT", "NULL", "PRIMARY", "KEY,", "value", "TEXT)"]))
            connection.execute("INSERT INTO queue_metadata(key, value) VALUES('schema_version', '2.0')")
            connection.commit()

        old_version = subprocess.run(
            [sys.executable, str(install_script), "--target", str(old_version_target), "--mode", "copy", "--backup"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        old_version_output = old_version.stdout + old_version.stderr
        require(old_version.returncode != 0, "install.py は schema_version=2.0 runtime DB の通常更新を拒否してください。")
        require(
            "--backup --reset-runtime" in old_version_output and "--clean-install" in old_version_output,
            "install.py の schema_version=2.0 拒否 message は reset-runtime / clean-install を案内してください。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        fake_v3_target = Path(tmp) / "fake-v3-guild"
        database = fake_v3_target / ".orchestra/queue/state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute(" ".join(["CREATE", "TABLE", "queue_metadata(key", "TEXT", "NOT", "NULL", "PRIMARY", "KEY,", "value", "TEXT", "NOT", "NULL,", "updated_at", "TEXT)"]))
            connection.execute("INSERT INTO queue_metadata(key, value) VALUES('schema_version', '3.0')")
            connection.execute(" ".join(["CREATE", "TABLE", "tickets(ticket_id", "TEXT", "PRIMARY", "KEY)"]))
            connection.execute(" ".join(["CREATE", "TABLE", "assignments(task_id", "TEXT", "PRIMARY", "KEY,", "status", "TEXT)"]))
            connection.commit()

        fake_v3 = subprocess.run(
            [sys.executable, str(install_script), "--target", str(fake_v3_target), "--mode", "copy", "--backup"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        fake_v3_output = fake_v3.stdout + fake_v3.stderr
        require(fake_v3.returncode != 0, "install.py は schema_version=3.0 でも旧物理 schema の runtime DB を拒否してください。")
        require(
            "--backup --reset-runtime" in fake_v3_output and "--clean-install" in fake_v3_output and ("tickets" in fake_v3_output or "task_id" in fake_v3_output),
            "install.py の旧物理 schema 拒否 message は reset-runtime / clean-install と mismatch detail を案内してください。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        legacy_rank_target = Path(tmp) / "legacy-rank-guild"
        installed = subprocess.run(
            [sys.executable, str(install_script), "--target", str(legacy_rank_target), "--mode", "copy"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(installed.returncode == 0, "install.py の legacy rank smoke 用 install が失敗しました: " + installed.stderr)
        database = legacy_rank_target / ".orchestra/queue/state.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                INSERT INTO quests(quest_id, workflow_id, rank, status, payload_json)
                VALUES('quest_legacy_rank', 'workflow_legacy_rank', 'campaign', 'active', '{}')
                """
            )
            connection.commit()
        legacy_rank = subprocess.run(
            [sys.executable, str(install_script), "--target", str(legacy_rank_target), "--mode", "copy", "--backup"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        legacy_rank_output = legacy_rank.stdout + legacy_rank.stderr
        require(legacy_rank.returncode != 0, "install.py は旧 campaign rank を含む runtime DB の通常更新を拒否してください。")
        require(
            "campaign" in legacy_rank_output and "guild_quest" in legacy_rank_output and "--backup --reset-runtime" in legacy_rank_output and "--clean-install" in legacy_rank_output,
            "install.py の旧 rank 拒否 message は campaign -> guild_quest と reset-runtime / clean-install を案内してください。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        legacy_value_target = Path(tmp) / "legacy-value-guild"
        installed = subprocess.run(
            [sys.executable, str(install_script), "--target", str(legacy_value_target), "--mode", "copy"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(installed.returncode == 0, "install.py の旧 runtime 値 smoke 用 install が失敗しました: " + installed.stderr)
        database = legacy_value_target / ".orchestra/queue/state.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                INSERT INTO assignments(assignment_id, parent_id, worker_id, kind, workflow_id, status, payload_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "assignment_legacy_value",
                    "quest_legacy_value",
                    "spark",
                    "assignment",
                    "workflow_legacy_value",
                    "active",
                    json.dumps({
                        "id": "assignment_legacy_value",
                        "worker_id": "spark",
                        "scout_plan": {},
                    }),
                ),
            )
            connection.commit()
        legacy_value = subprocess.run(
            [sys.executable, str(install_script), "--target", str(legacy_value_target), "--mode", "copy", "--backup"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        legacy_value_output = legacy_value.stdout + legacy_value.stderr
        require(legacy_value.returncode != 0, "install.py は旧 JSON key / 廃止済み agent 値を含む runtime DB の通常更新を拒否してください。")
        require(
            "scout_plan" in legacy_value_output and "spark" in legacy_value_output and "--backup --reset-runtime" in legacy_value_output and "--clean-install" in legacy_value_output,
            "install.py の旧 runtime 値拒否 message は旧 key / 廃止済み agent と reset-runtime / clean-install を案内してください。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        reset_target = Path(tmp) / "reset-guild"
        database = reset_target / ".orchestra/queue/state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute(" ".join(["CREATE", "TABLE", "tickets(ticket_id", "TEXT", "PRIMARY", "KEY)"]))
            connection.commit()
        reset = subprocess.run(
            [sys.executable, str(install_script), "--target", str(reset_target), "--mode", "copy", "--backup", "--reset-runtime"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(reset.returncode == 0, "install.py --backup --reset-runtime は v2 風 DB で成功してください: " + reset.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        clean_target = Path(tmp) / "clean-guild"
        database = clean_target / ".orchestra/queue/state.sqlite"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute(" ".join(["CREATE", "TABLE", "tickets(ticket_id", "TEXT", "PRIMARY", "KEY)"]))
            connection.commit()
        clean = subprocess.run(
            [sys.executable, str(install_script), "--target", str(clean_target), "--mode", "copy", "--clean-install"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(clean.returncode == 0, "install.py --clean-install は v2 風 DB で成功してください: " + clean.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        prune_target = Path(tmp) / "prune-guild"
        for rel in legacy_template_paths:
            path = prune_target / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("legacy: true\n", encoding="utf-8")

        installed = subprocess.run(
            [sys.executable, str(install_script), "--target", str(prune_target), "--mode", "copy"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(installed.returncode == 0, "install.py の通常 install smoke が失敗しました: " + installed.stderr)
        remaining = [str(rel) for rel in legacy_template_paths if (prune_target / rel).exists()]
        require(not remaining, "install.py は削除済み旧 template を prune してください: " + ", ".join(remaining))


def run_claude_compat(helper: Path, target: Path, *args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(helper), "--target-repo-root", str(target), "--work-path", "packages/web/src/app.ts", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(result.returncode == 0, f"claude_compat.py {' '.join(args)} が失敗しました: {result.stderr or result.stdout}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"claude_compat.py の JSON 出力を parse できません: {exc}\n{result.stdout}") from exc
    require(isinstance(payload, dict), "claude_compat.py の出力は JSON object にしてください。")
    return payload


def validate_claude_compat_smoke() -> None:
    helper = ROOT / "template/.agents/orchestra/scripts/claude_compat.py"
    require(helper.exists(), "template/.agents/orchestra/scripts/claude_compat.py が必要です。")
    py_compile = subprocess.run(
        [sys.executable, "-m", "py_compile", str(helper)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(py_compile.returncode == 0, "claude_compat.py は Python として parse できる必要があります: " + py_compile.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "repo"
        outside = Path(tmp) / "outside.md"
        (target / "packages/web/src").mkdir(parents=True)
        (target / ".claude/rules").mkdir(parents=True)
        (target / ".claude/skills/deploy").mkdir(parents=True)
        (target / ".claude/skills/skipme").mkdir(parents=True)
        (target / ".claude/commands").mkdir(parents=True)
        (target / ".claude/agents/researcher").mkdir(parents=True)
        (target / ".git").mkdir(parents=True)
        (target / "packages/web/.claude/skills/deploy").mkdir(parents=True)
        (target / "packages/web/.claude/skills/forked").mkdir(parents=True)
        (target / "packages/web/.claude/skills/pluginish/.claude-plugin").mkdir(parents=True)
        (target / "packages/web/vendor/.git").mkdir(parents=True)
        (target / "packages/web/vendor/.claude/skills/nested").mkdir(parents=True)
        (target / "secret-token").mkdir(parents=True)
        (target / "binary").mkdir(parents=True)
        (target / "large").mkdir(parents=True)

        (target / "packages/web/src/app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        (target / "CLAUDE.md").write_text(
            "# Root Claude\n"
            "@docs/context.md\n"
            "@.claude/settings.json\n"
            "@.mcp.json\n"
            "@.git/config\n"
            "@.claude/agents/researcher/CLAUDE.md\n"
            "!printf omit-context\n",
            encoding="utf-8",
        )
        (target / "docs").mkdir()
        (target / "docs/context.md").write_text("Imported context.\n", encoding="utf-8")
        (target / ".mcp.json").write_text('{"sentinel":"MCP_RENDER_SENTINEL"}\n', encoding="utf-8")
        (target / ".git/config").write_text("[remote]\nurl = GIT_RENDER_SENTINEL\n", encoding="utf-8")
        (target / ".claude/CLAUDE.md").write_text("# Project Claude\n", encoding="utf-8")
        (target / ".claude/agents/researcher/CLAUDE.md").write_text("AGENT_RENDER_SENTINEL\n", encoding="utf-8")
        (target / "packages/web/CLAUDE.md").write_text("# Web Claude\n", encoding="utf-8")
        (target / "packages/web/vendor/CLAUDE.md").write_text("NESTED_GIT_CLAUDE_SENTINEL\n", encoding="utf-8")
        (target / "packages/web/vendor/.claude/skills/nested/SKILL.md").write_text("---\ndescription: Nested git skill\n---\nNESTED_GIT_SKILL_SENTINEL\n", encoding="utf-8")
        (target / "binary/CLAUDE.md").write_bytes(b"binary\0context\n")
        (target / "large/CLAUDE.md").write_text("large context\n" * 12000, encoding="utf-8")
        (target / "secret-token/CLAUDE.md").write_text("do not read\n", encoding="utf-8")
        (target / "excluded").mkdir()
        (target / "excluded/CLAUDE.md").write_text("excluded\n", encoding="utf-8")
        (target / ".claude/settings.json").write_text(
            json.dumps(
                {
                    "claudeMdExcludes": ["**/excluded/CLAUDE.md"],
                    "skillOverrides": {"skipme": "off", "deploy": "user-invocable-only"},
                    "disableSkillShellExecution": True,
                    "env": {"SECRET_TOKEN": "SETTINGS_ENV_SENTINEL"},
                    "permissions": {"allow": ["Bash(*)"]},
                    "hooks": {"PreToolUse": "HOOKS_SENTINEL"},
                    "model": "MODEL_SENTINEL",
                }
            ),
            encoding="utf-8",
        )
        (target / ".claude/rules/api.md").write_text(
            "---\npaths:\n  - \"packages/web/**/*.ts\"\n---\nUse API rules.\n",
            encoding="utf-8",
        )
        outside.write_text("outside\n", encoding="utf-8")
        try:
            os.symlink(outside, target / ".claude/rules/symlink.md")
        except OSError:
            pass
        (target / ".claude/skills/deploy/SKILL.md").write_text(
            "---\ndescription: Deploy root app\nallowed-tools: Bash(git status)\n---\nDeploy root.\n!`printf omit-root`\n",
            encoding="utf-8",
        )
        (target / ".claude/skills/skipme/SKILL.md").write_text(
            "---\ndescription: Hidden skill\n---\nDo not expose.\n",
            encoding="utf-8",
        )
        (target / ".claude/commands/review.md").write_text(
            "---\ndescription: Review command\n---\nReview $ARGUMENTS.\n",
            encoding="utf-8",
        )
        (target / "packages/web/.claude/skills/deploy/SKILL.md").write_text(
            "---\ndescription: Deploy web app\narguments: [env]\nallowed-tools: Bash(git status)\nmodel: opus\n"
            "effort: high\n---\nDeploy $env.\n!`printf omit-nested`\n",
            encoding="utf-8",
        )
        (target / "packages/web/.claude/skills/forked/SKILL.md").write_bytes(
            b"---\r\n"
            b"description: Forked research\r\n"
            b"context: fork\r\n"
            b"hooks: unsafe\r\n"
            b"allowed-tools: Bash(git status)\r\n"
            b"model: opus\r\n"
            b"effort: high\r\n"
            b"---\r\n"
            b"Research.\r\n",
        )
        (target / "packages/web/.claude/skills/pluginish/.claude-plugin/plugin.json").write_text("{}", encoding="utf-8")
        (target / "packages/web/.claude/skills/pluginish/SKILL.md").write_text(
            "---\ndescription: Plugin skill\n---\nPlugin の内容。\n",
            encoding="utf-8",
        )

        scan = run_claude_compat(helper, target, "scan")
        scan_text = json.dumps(scan, ensure_ascii=False)
        settings = mapping(scan.get("settings"), "claude_compat.scan.settings")
        require("env" in sequence(settings.get("redacted_keys_present"), "claude_compat.scan.settings.redacted_keys_present"), "claude_compat は env を redacted key として扱ってください。")
        require("hooks" in sequence(settings.get("redacted_keys_present"), "claude_compat.scan.settings.redacted_keys_present"), "claude_compat は hooks を redacted key として扱ってください。")
        require("model" in sequence(settings.get("ignored_keys_present"), "claude_compat.scan.settings.ignored_keys_present"), "claude 互換設定は非対応設定項目を無視項目として扱ってください。")
        for sentinel in ("SETTINGS_ENV_SENTINEL", "HOOKS_SENTINEL", "MODEL_SENTINEL", "MCP_RENDER_SENTINEL", "GIT_RENDER_SENTINEL"):
            require(sentinel not in scan_text, f"claude 互換 scan は検証値 `{sentinel}` を露出しないでください。")
        context_cards = sequence(scan.get("context_cards"), "claude_compat.scan.context_cards")
        skill_cards = sequence(scan.get("skill_cards"), "claude_compat.scan.skill_cards")
        context_by_path = {str(mapping(card, "context_card").get("path")): mapping(card, "context_card") for card in context_cards}
        require(context_by_path["packages/web/CLAUDE.md"].get("applicable") is True, "入れ子の CLAUDE.md は work path に適用される必要があります。")
        require(context_by_path["excluded/CLAUDE.md"].get("status") == "skipped", "claudeMdExcludes は CLAUDE.md を skip してください。")
        require(context_by_path["secret-token/CLAUDE.md"].get("reason") == "secret_like_path", "secret-like CLAUDE.md は skip してください。")
        require(context_by_path["binary/CLAUDE.md"].get("reason") == "binary_content", "NUL 入り CLAUDE.md は skip してください。")
        require(context_by_path["large/CLAUDE.md"].get("reason") == "too_large", "上限超過 CLAUDE.md は skip してください。")
        require("packages/web/vendor/CLAUDE.md" not in context_by_path, "nested git repo 内の CLAUDE.md は scan しないでください。")
        if ".claude/rules/symlink.md" in context_by_path:
            require(context_by_path[".claude/rules/symlink.md"].get("reason") == "symlink_path", "symlink rule は skip してください。")
        skills_by_name = {str(mapping(card, "skill_card").get("qualified_name")): mapping(card, "skill_card") for card in skill_cards}
        require("deploy" in skills_by_name and "packages/web:deploy" in skills_by_name, "root と入れ子の同名 Skill は qualified name を持つ必要があります。")
        require(skills_by_name["skipme"].get("status") == "skipped", "skillOverrides.off は skill を skip してください。")
        require(skills_by_name["packages/web:pluginish"].get("reason") == "plugin_manifest_present", "plugin manifest を持つ skill は skip してください。")
        require(skills_by_name["packages/web:forked"].get("auto_candidate") is False, "context: fork skill は auto candidate にしないでください。")
        forked_unsupported = sequence(skills_by_name["packages/web:forked"].get("unsupported_fields"), "claude_compat.forked.unsupported_fields")
        for metadata_key in ("allowed-tools", "context", "effort", "hooks", "model"):
            require(metadata_key in forked_unsupported, f"CRLF frontmatter の {metadata_key} は unsupported_fields に検出してください。")
        forked_unsafe = sequence(skills_by_name["packages/web:forked"].get("unsafe_fields"), "claude_compat.forked.unsafe_fields")
        for metadata_key in ("context", "hooks"):
            require(metadata_key in forked_unsafe, f"CRLF frontmatter の {metadata_key} は unsafe_fields に検出してください。")
        require("packages/web/vendor:nested" not in skills_by_name, "nested git repo 内の SKILL.md は scan しないでください。")

        rendered = run_claude_compat(helper, target, "render-skill", "--skill", "packages/web:deploy", "--arguments", "staging")
        require(rendered.get("status") == "rendered", "明示 skill render は成功してください。")
        require("omit-nested" not in str(rendered.get("content")), "動的 command 本文をそのまま render しないでください。")
        require("shell command omitted" in str(rendered.get("content")), "動的 command は無害な marker にしてください。")
        require("Deploy staging" in str(rendered.get("content")), "skill arguments を置換してください。")
        rendered_unsupported = sequence(rendered.get("unsupported_fields"), "claude_compat.render_skill.unsupported_fields")
        for metadata_key in ("allowed-tools", "model", "effort"):
            require(metadata_key in rendered_unsupported, f"{metadata_key} は unsupported_fields に留めてください。")
        rendered_skill_text = json.dumps(rendered, ensure_ascii=False)
        for codex_key in ("authority", "model_reasoning_effort", "sandbox_mode"):
            require(codex_key not in rendered_skill_text, f"Claude metadata を Codex 権限 key `{codex_key}` へ変換しないでください。")

        forked = run_claude_compat(helper, target, "render-skill", "--skill", "packages/web:forked")
        require(forked.get("status") == "skipped_unsafe", "context: fork skill は render せず skipped_unsafe にしてください。")
        require("context" in sequence(forked.get("blocking_fields"), "claude_compat.forked.blocking_fields"), "CRLF frontmatter の context は blocking field にしてください。")
        require("hooks" in sequence(forked.get("blocking_fields"), "claude_compat.forked.blocking_fields"), "hooks は Codex 権限に変換せず blocking field にしてください。")

        rendered_context = run_claude_compat(helper, target, "render-context")
        rendered_text = json.dumps(rendered_context, ensure_ascii=False)
        require("Imported context." in rendered_text, "安全な repo 内 @import は render-context に取り込んでください。")
        for omitted in (".claude/settings.json", ".mcp.json", ".git/config", ".claude/agents/researcher/CLAUDE.md"):
            require(f"[import omitted: {omitted}]" in rendered_text, f"危険な @import `{omitted}` は omit marker にしてください。")
            require(f"import_skipped:{omitted}:" in rendered_text, f"危険な @import `{omitted}` は warning reason を残してください。")
        for sentinel in (
            "SETTINGS_ENV_SENTINEL",
            "HOOKS_SENTINEL",
            "MODEL_SENTINEL",
            "MCP_RENDER_SENTINEL",
            "GIT_RENDER_SENTINEL",
            "AGENT_RENDER_SENTINEL",
            "NESTED_GIT_CLAUDE_SENTINEL",
            "NESTED_GIT_SKILL_SENTINEL",
            "binary\\u0000context",
            "large context",
        ):
            require(sentinel not in rendered_text, f"claude 互換 render-context は検証値 `{sentinel}` を露出しないでください。")
        require("omit-context" not in rendered_text, "CLAUDE.md の動的 command 本文をそのまま render しないでください。")
        require("shell command omitted" in rendered_text, "CLAUDE.md の動的 command は無害な marker にしてください。")


def validate_agents() -> None:
    require(tomllib is not None, "TOML 検証には tomllib/tomli が必要です。")
    require(not (ROOT / "template/.codex/agents/spark.toml").exists(), "template/.codex/agents/spark.toml を戻さないでください。")
    for rel in sorted((ROOT / "template/.codex/agents").glob("*.toml")):
        raw = rel.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        for key in ("name", "description", "model", "model_reasoning_effort", "sandbox_mode", "developer_instructions"):
            require(key in data, f"{rel.relative_to(ROOT)} に {key} が必要です。")
        require("Guild Law" in raw, f"{rel.relative_to(ROOT)} は Guild Law を参照してください。")
    config = tomllib.loads(read("template/.codex/config.toml"))
    config_text = read("template/.codex/config.toml")
    require(config.get("model") == "gpt-5.5", "template/.codex/config.toml の model は gpt-5.5 にしてください。")
    require(config.get("sandbox_mode") == "read-only", "Root sandbox は read-only にしてください。")
    agents_config = mapping(config.get("agents"), "template/.codex/config.toml.agents")
    require(agents_config.get("max_depth") == 4, "template/.codex/config.toml の agents.max_depth は 4 にしてください。")
    for token in LEGACY_ROUTE_COMMENT_TERMS:
        require(token not in config_text, f"template/.codex/config.toml に旧固定 route コメント `{token}` を戻さないでください。")
    require("mapmaking" in config_text and "guild_quest" in config_text and "advisor" in config_text and "terminal worker" in config_text, "template/.codex/config.toml の agent コメントは Quest Rank と advisor 境界を説明してください。")
    advisor = tomllib.loads(read("template/.codex/agents/advisor.toml"))
    advisor_text = read("template/.codex/agents/advisor.toml")
    require(advisor.get("sandbox_mode") == "read-only", "advisor.toml の sandbox_mode は read-only にしてください。")
    require(advisor.get("model_reasoning_effort") == "xhigh", "advisor.toml の model_reasoning_effort は xhigh にしてください。")
    require_tokens(advisor_text, ("terminal worker", "追加 subagent", "実装", "採否", "Ledger", "owner synthesis", "Guild Law", "confidence-based", "confidence delta", "同じ unknown", "owner が根拠確認"), "template/.codex/agents/advisor.toml")
    cartographer_text = read("template/.codex/agents/cartographer.toml")
    require_tokens(cartographer_text, ("設計", "実装計画", "方針整理", "アーキテクチャ", "mapmaking", "read-only advisor"), "template/.codex/agents/cartographer.toml")
    inquisitor = read("template/.codex/agents/inquisitor.toml")
    courier = tomllib.loads(read("template/.codex/agents/courier.toml"))
    require(courier.get("model") == "gpt-5.3-codex-spark", "courier.toml の model は gpt-5.3-codex-spark にしてください。")
    require(courier.get("model_reasoning_effort") == "xhigh", "courier.toml の model_reasoning_effort は xhigh にしてください。")
    require_tokens(
        inquisitor,
        (
            "scope boundary",
            "safety items",
            "edge_cases",
            "error_handling",
            "security",
            "accessibility",
            "compatibility",
            "focused_trial",
            "multi_focus_trial",
            "safety_gate",
            "subassignments",
            "authority / boundaries",
            "既定で検討",
            "使わない場合",
            "architecture",
            "regression",
            "validation",
            "Trial evidence",
            "confidence-based",
            "owner confidence",
        ),
        "template/.codex/agents/inquisitor.toml",
    )


def validate_docs_and_instructions() -> None:
    full_contract_paths = [
        "template/AGENTS.md",
        "template/.agents/orchestra/instructions/common.md",
        "README.md",
        "docs/orchestration-runtime.md",
        "docs/guild-quest-lifecycle.md",
        "docs/customization.md",
    ]
    role_paths = [
        "template/.agents/orchestra/instructions/receptionist.md",
        "template/.agents/orchestra/instructions/advisor.md",
        "template/.agents/orchestra/instructions/cartographer.md",
        "template/.agents/orchestra/instructions/guildmaster.md",
        "template/.agents/orchestra/instructions/party_leader.md",
        "template/.agents/orchestra/instructions/adventurer.md",
        "template/.agents/orchestra/instructions/inquisitor.md",
    ]
    for rel in full_contract_paths:
        text = read(rel)
        require_tokens(text, GUILD_TERMS, rel)
        require("target_repo_root" in text or rel == "README.md", f"{rel} は target_repo_root 境界を説明してください。")
    for rel in role_paths:
        text = read(rel)
        require("Guild Law" in text, f"{rel} は Guild Law を参照してください。")
        require("Quest" in text, f"{rel} は Quest を参照してください。")
    combined = "\n".join(read(rel) for rel in full_contract_paths + role_paths)
    for token in LEGACY_PRIMARY_TERMS:
        require(token not in combined, f"docs/instructions に旧固定 contract `{token}` が残っています。")
    for token in VOCABULARY_DRIFT_TERMS:
        require(token not in combined, f"docs/instructions に表記揺れ `{token}` が残っています。")
    for token in AMBIGUOUS_INQUISITOR_TERMS:
        require(token not in combined, f"docs/instructions に曖昧な inquisitor 表記 `{token}` が残っています。")
    require("Trial 統合担当の `inquisitor`" in combined, "docs/instructions は Trial 統合担当の `inquisitor` 表記を使ってください。")
    common = read("template/.agents/orchestra/instructions/common.md")
    agents = read("template/AGENTS.md")
    runtime_readme = read("template/.agents/orchestra/README.md")
    require_tokens(common, ("Root", "target_repo_root", "実装", "Trial", "品質採否", "Ledger"), "template/.agents/orchestra/instructions/common.md")
    require_tokens(agents, ("Root", "target_repo_root", "実装", "Trial", "品質採否", "Ledger"), "template/AGENTS.md")
    require_tokens(agents, DEFAULT_INTAKE_TOKENS + ("短い説明", "orchestration-template workflow", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS + GUILD_SKILL_PRIORITY_TOKENS, "template/AGENTS.md")
    require_tokens(common, DEFAULT_INTAKE_TOKENS + ("短い説明", "orchestration-template workflow", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS + GUILD_SKILL_PRIORITY_TOKENS, "template/.agents/orchestra/instructions/common.md")
    require_tokens(runtime_readme, DEFAULT_INTAKE_TOKENS + ("短い説明", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS[:1] + GUILD_SKILL_PRIORITY_TOKENS[:3], "template/.agents/orchestra/README.md")
    customization = read("docs/customization.md")
    orchestration_runtime = read("docs/orchestration-runtime.md")
    adventurer = read("template/.agents/orchestra/instructions/adventurer.md")
    adventurer_toml = read("template/.codex/agents/adventurer.toml")
    deployment = read("docs/deployment-patterns.md")
    prompt_recipes = read("docs/prompt-recipes.md")
    require_tokens(
        deployment,
        ("target_repo_root", ".agents/orchestra", ".orchestra", "v3", "schema_version=3.0", "--backup --reset-runtime", "--clean-install", "必要 table / column", "campaign", "guild_quest"),
        "docs/deployment-patterns.md",
    )
    require_tokens(
        prompt_recipes,
        ("target_repo_root", "担当者が確認した根拠", "Trial 深度", "v3 schema", "--backup --reset-runtime", "--clean-install"),
        "docs/prompt-recipes.md",
    )
    require_tokens(
        orchestration_runtime,
        DEFAULT_INTAKE_TOKENS + ("短い説明", "orchestration-template workflow", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS + GUILD_SKILL_PRIORITY_TOKENS,
        "docs/orchestration-runtime.md",
    )
    combined_runtime_text = "\n".join(read(rel) for rel in full_contract_paths + role_paths)
    for token in ("spark", "Scout", "scout"):
        require(token not in combined_runtime_text, f"docs/instructions に廃止済み `{token}` が残っています。")
    for rel, text in (
        ("docs/customization.md", customization),
        ("template/.agents/orchestra/instructions/adventurer.md", adventurer),
        ("template/.codex/agents/adventurer.toml", adventurer_toml),
    ):
        require("追加調査" in text or "自己調査" in text or "調査" in text, f"{rel} は追加調査の扱いを説明してください。")
    inquisitor = read("template/.agents/orchestra/instructions/inquisitor.md")
    require_tokens(
        inquisitor,
        tuple(sorted(TRIAL_REQUIRED_CHECKS | TRIAL_CONDITIONAL_CHECKS | TRIAL_DEPTH_GUARDRAILS)),
        "template/.agents/orchestra/instructions/inquisitor.md",
    )
    require_tokens(
        inquisitor,
        (
            "Trial 統合担当の `inquisitor`",
            "focused_trial",
            "multi_focus_trial",
            "subassignments",
            "authority / boundaries",
            "既定で検討",
            "使わない場合",
            "architecture",
            "regression",
            "validation",
            "Trial evidence",
        ),
        "template/.agents/orchestra/instructions/inquisitor.md",
    )
    advisor_instruction = read("template/.agents/orchestra/instructions/advisor.md")
    require_tokens(
        advisor_instruction,
        ("terminal worker", "追加 subagent", "実装", "品質採否", "Ledger", "Guild Law", "Quest Charter", "confidence-based", "confidence_delta_min_percent", "同じ unknown"),
        "template/.agents/orchestra/instructions/advisor.md",
    )


def validate_skills() -> None:
    skills_root = ROOT / "template/.agents/skills"
    require(skills_root.exists(), "template/.agents/skills が必要です。")
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        require(text.startswith("---\n"), f"{skill_md.relative_to(ROOT)} は frontmatter で始めてください。")
        for section in ("## 使う時", "## 入力", "## 手順", "## 出力", "## 安全", "## 停止条件"):
            require(section in text, f"{skill_md.relative_to(ROOT)} に {section} が必要です。")
        require("未信頼" in text or "外部入力" in text or "秘密" in text, f"{skill_md.relative_to(ROOT)} は安全境界を明記してください。")
    final_review = read("template/.agents/skills/branch-implementation-final-review/SKILL.md")
    require_tokens(
        final_review,
        (
            "read-only `advisor`",
            "1段",
            "未信頼入力",
            "採否",
            "重大度分類",
            "追加 subagent 起動",
            "デッドコード",
            "未使用の関数",
            "変数",
            "設定",
            "到達不能分岐",
            "不要ファイル",
            "本質的ではないテストコード",
            "削除対象",
            "最適化対象",
            "直接編集せず",
            "検証観点",
            "保留理由",
        ),
        "template/.agents/skills/branch-implementation-final-review/SKILL.md",
    )
    require(
        "追加観点が必要な場合は、Root または `party_leader`" not in final_review,
        "branch-implementation-final-review skill は advisor 契約と衝突する追加観点返却ルールを戻さないでください。",
    )
    design_mapmaking = read("template/.agents/skills/repository-design-mapmaking/SKILL.md")
    design_mapmaking_frontmatter = design_mapmaking.split("---\n", 2)[1]
    require_tokens(
        design_mapmaking_frontmatter,
        ("設計", "実装計画", "方針整理", "アーキテクチャ", "cartographer", "mapmaking"),
        "template/.agents/skills/repository-design-mapmaking/SKILL.md frontmatter",
    )
    require_tokens(
        design_mapmaking,
        ("read-only `cartographer`", "tool_unavailable", "target_repo_root", "advisor synthesis", "未信頼入力"),
        "template/.agents/skills/repository-design-mapmaking/SKILL.md",
    )
    use_guild_workflow = read("template/.agents/skills/use-guild-workflow/SKILL.md")
    require_tokens(
        use_guild_workflow,
        (
            "always_guild_intake",
            "Default Guild Intake",
            "use-guild-workflow",
            "target_repo_root",
            "full Quest",
            "orchestration-template workflow",
            "短い回答",
            "未信頼",
            "類似 Skill",
            "owner: codex-guild-orchestra",
            "非ギルド Skill",
        ),
        "template/.agents/skills/use-guild-workflow/SKILL.md",
    )
    require(
        "明示がない通常作業へ、この Skill を無理に適用しない" not in use_guild_workflow,
        "use-guild-workflow は always_guild_intake と衝突する旧トリガー文言を戻さないでください。",
    )

    runtime_readme = read("template/.agents/orchestra/README.md")
    require(
        "Ledger 反映と、Root または Quest Charter が明示した local Git 操作だけ" in runtime_readme,
        "template/.agents/orchestra/README.md の courier 説明は Ledger と明示 local Git 操作に限定してください。",
    )


def validate_stop_hook() -> None:
    text = read("template/.codex/hooks/stop_quality_gate.py")
    require("Quest" in text and "Trial" in text and "Risk" in text, "stop_quality_gate.py は Quest / Trial / Risk の最終要約を促してください。")


def main() -> int:
    checks = [
        validate_dependencies,
        validate_required_paths,
        validate_version,
        validate_settings,
        validate_queue_templates,
        validate_sqlite_schema,
        validate_queue_db_smoke,
        validate_install_upgrade_smoke,
        validate_claude_compat_smoke,
        validate_agents,
        validate_active_prose_vocabulary,
        validate_docs_and_instructions,
        validate_skills,
        validate_stop_hook,
    ]
    for check in checks:
        check()
    print("validate: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"validate: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
