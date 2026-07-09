"""agent / documentation / skill / hook の契約検証。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import tempfile

from .core import ROOT, mapping, read, require, require_tokens, sequence, tomllib
from .rules import (
    AMBIGUOUS_INQUISITOR_TERMS,
    DEFAULT_INTAKE_CONFIRMATION_TOKENS,
    DEFAULT_INTAKE_TOKENS,
    FOCUS_REVIEWER_CONTRACT_TOKENS,
    GUILD_SKILL_PRIORITY_TOKENS,
    GUILD_TERMS,
    LEGACY_PRIMARY_TERMS,
    LEGACY_ROUTE_COMMENT_TERMS,
    QUEUE_TEMPLATE_PATHS,
    STATE_CHANGE_GUARD_OPERATION_TOKENS,
    STATE_CHANGE_GUARD_TOKENS,
    TRIAL_CONDITIONAL_CHECKS,
    TRIAL_DEPTH_GUARDRAILS,
    TRIAL_REQUIRED_CHECKS,
    VOCABULARY_DRIFT_TERMS,
    ACTIVE_PROSE_PATHS,
)

EXPECTED_AGENT_SANDBOX_MODES = {
    "adventurer": "workspace-write",
    "advisor": "read-only",
    "cartographer": "read-only",
    "courier": "workspace-write",
    "guildmaster": "read-only",
    "inquisitor": "read-only",
    "quest_sentinel": "read-only",
    "party_leader": "read-only",
}
EXPECTED_AGENT_MODEL_CONFIGS = {
    "adventurer": ("gpt-5.6-terra", "high"),
    "advisor": ("gpt-5.6-luna", "high"),
    "cartographer": ("gpt-5.6-sol", "high"),
    "courier": ("gpt-5.3-codex-spark", "xhigh"),
    "guildmaster": ("gpt-5.6-sol", "xhigh"),
    "inquisitor": ("gpt-5.6-sol", "high"),
    "quest_sentinel": ("gpt-5.6-luna", "medium"),
    "party_leader": ("gpt-5.6-terra", "high"),
}


def validate_audit_english_path_guard() -> None:
    spec = importlib.util.spec_from_file_location("audit_english_guard", ROOT / "scripts/audit_english.py")
    require(spec is not None and spec.loader is not None, "scripts/audit_english.py を import できるようにしてください。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for rel in ("docs/credentials.md", "docs/secrets.md", "docs/tokens.md", "docs/api_key.txt", "docs/auth.json"):
        try:
            module.ensure_not_sensitive_path(ROOT / rel)
        except SystemExit:
            continue
        require(False, f"audit_english.py は secret-like path を読む前に拒否してください: {rel}")

    for rel in ("docs/keyboard-shortcuts.md", "docs/authoring-guide.md"):
        try:
            module.ensure_not_sensitive_path(ROOT / rel)
        except SystemExit as exc:
            require(False, f"audit_english.py は無害な path を secret-like と誤判定しないでください: {rel}: {exc}")

    original_root = module.ROOT
    with tempfile.TemporaryDirectory() as tmp:
        fake_root = Path(tmp) / "repo"
        fake_root.mkdir()
        external = Path(tmp) / "external.txt"
        external.write_text("external\n", encoding="utf-8")
        outside = Path(tmp) / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        link = fake_root / "docs" / "keyboard-shortcuts.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(external)
        module.ROOT = fake_root
        try:
            module.ensure_not_sensitive_path(outside)
        except SystemExit:
            pass
        else:
            require(False, "audit_english.py は root 外 path を読む前に拒否してください。")
        try:
            module.ensure_not_sensitive_path(link)
        except SystemExit:
            pass
        else:
            require(False, "audit_english.py は scan 対象内の symlink を読む前に拒否してください。")
        finally:
            module.ROOT = original_root
ROLE_INSTRUCTION_REFS = {
    "adventurer": ".agents/orchestra/instructions/adventurer.md",
    "advisor": ".agents/orchestra/instructions/advisor.md",
    "cartographer": ".agents/orchestra/instructions/cartographer.md",
    "guildmaster": ".agents/orchestra/instructions/guildmaster.md",
    "inquisitor": ".agents/orchestra/instructions/inquisitor.md",
    "party_leader": ".agents/orchestra/instructions/party_leader.md",
}
COMMON_INSTRUCTION_REF = ".agents/orchestra/instructions/common.md"
SETTINGS_REF = ".agents/orchestra/config/settings.yaml"


def _contains_split_legacy_quest_awareness_term(text: str) -> bool:
    return re.search(r"meta[`'\" +/_\-.]{1,40}cognitive", text, flags=re.IGNORECASE) is not None


LEGACY_DIRECT_CASEFOLD_TOKENS = (
    "fa" "ble",
    "fa" "ble-style-task-loop",
    "meta" "cognitive",
    "meta" "cognitive_controller",
    "meta" "cognitive-task-loop",
    "meta" "cognitive-runtime",
    "invoke_" "meta" "cognitive_controller",
    "meta-" "recognition",
    "meta " "recognition",
    "meta_" "recognition",
    "cognitive_" "failure_memory",
    "メタ認" "知",
    "メタ認" "識",
)


def validate_agents() -> None:
    require(tomllib is not None, "TOML 検証には tomllib/tomli が必要です。")
    require(not (ROOT / "template/.codex/agents/spark.toml").exists(), "template/.codex/agents/spark.toml を戻さないでください。")
    agent_paths = sorted((ROOT / "template/.codex/agents").glob("*.toml"))
    actual_agent_names = {path.stem for path in agent_paths}
    require(actual_agent_names == set(EXPECTED_AGENT_SANDBOX_MODES), "template/.codex/agents の role 一覧が期待値と一致しません: " + ", ".join(sorted(actual_agent_names)))
    for rel in agent_paths:
        raw = rel.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        for key in ("name", "description", "model", "model_reasoning_effort", "sandbox_mode", "developer_instructions"):
            require(key in data, f"{rel.relative_to(ROOT)} に {key} が必要です。")
        role = rel.stem
        require(data.get("name") == role, f"{rel.relative_to(ROOT)} の name は filename と一致させてください。")
        require(data.get("sandbox_mode") == EXPECTED_AGENT_SANDBOX_MODES[role], f"{rel.relative_to(ROOT)} の sandbox_mode は {EXPECTED_AGENT_SANDBOX_MODES[role]} にしてください。")
        expected_model, expected_effort = EXPECTED_AGENT_MODEL_CONFIGS[role]
        require(data.get("model") == expected_model, f"{rel.relative_to(ROOT)} の model は {expected_model} にしてください。")
        require(data.get("model_reasoning_effort") == expected_effort, f"{rel.relative_to(ROOT)} の model_reasoning_effort は {expected_effort} にしてください。")
        require("Guild Law" in raw, f"{rel.relative_to(ROOT)} は Guild Law を参照してください。")
        require(COMMON_INSTRUCTION_REF.removeprefix(".agents/orchestra/") in raw, f"{rel.relative_to(ROOT)} は実在する common instruction path を参照してください。")
        require((ROOT / "template" / COMMON_INSTRUCTION_REF).exists(), f"{COMMON_INSTRUCTION_REF} が存在しません。")
        role_ref = ROLE_INSTRUCTION_REFS.get(role)
        if role_ref is not None:
            require(role_ref.removeprefix(".agents/orchestra/") in raw, f"{rel.relative_to(ROOT)} は実在する role instruction path を参照してください。")
            require((ROOT / "template" / role_ref).exists(), f"{role_ref} が存在しません。")
        if role == "quest_sentinel":
            require(SETTINGS_REF.removeprefix(".agents/orchestra/") in raw, f"{rel.relative_to(ROOT)} は実在する settings path を参照してください。")
            require((ROOT / "template" / SETTINGS_REF).exists(), f"{SETTINGS_REF} が存在しません。")
    config = tomllib.loads(read("template/.codex/config.toml"))
    config_text = read("template/.codex/config.toml")
    require(config.get("model") == "gpt-5.6-sol", "template/.codex/config.toml の model は gpt-5.6-sol にしてください。")
    require("model_context_window" not in config, "model_context_window は model catalog に追随させ、Root config で固定しないでください。")
    require("model_reasoning_effort" not in config, "Root の model_reasoning_effort は config で固定しないでください。")
    require(config.get("sandbox_mode") == "read-only", "Root sandbox は read-only にしてください。")
    require(config.get("approval_policy") == "on-request", "template/.codex/config.toml の approval_policy は on-request にしてください。")
    require(config.get("approvals_reviewer") == "auto_review", "template/.codex/config.toml の approvals_reviewer は auto_review にしてください。")
    require(config.get("web_search") == "cached", "template/.codex/config.toml の web_search は cached にしてください。")
    require(config.get("allow_login_shell") is False, "template/.codex/config.toml の allow_login_shell は false にしてください。")
    sandbox_workspace_write = mapping(config.get("sandbox_workspace_write"), "template/.codex/config.toml.sandbox_workspace_write")
    require(sandbox_workspace_write.get("network_access") is False, "workspace-write 時の network_access は false にしてください。")
    shell_environment_policy = mapping(config.get("shell_environment_policy"), "template/.codex/config.toml.shell_environment_policy")
    excluded_env = set(sequence(shell_environment_policy.get("exclude"), "template/.codex/config.toml.shell_environment_policy.exclude"))
    require({"*secret*", "*token*", "*credential*", "*password*", "*key*", "*auth*"} <= excluded_env, "shell_environment_policy.exclude の secret deny glob が不足しています。")
    require("mcp_servers" not in config and "[mcp" not in config_text.casefold(), "MCP server は既定設定へ追加しないでください。")
    agents_config = mapping(config.get("agents"), "template/.codex/config.toml.agents")
    require(agents_config.get("max_depth") == 4, "template/.codex/config.toml の agents.max_depth は 4 にしてください。")
    for token in LEGACY_ROUTE_COMMENT_TERMS:
        require(token not in config_text, f"template/.codex/config.toml に旧固定 route コメント `{token}` を戻さないでください。")
    require("mapmaking" in config_text and "guild_quest" in config_text and "advisor" in config_text and "terminal worker" in config_text and "quest_sentinel" in config_text, "template/.codex/config.toml の agent コメントは Quest Rank と advisor / quest_sentinel 境界を説明してください。")
    require_tokens(config_text, ("focus reviewer", "workers.inquisitor.max_parallel", "autonomy_budget.subassignments"), "template/.codex/config.toml")
    advisor = tomllib.loads(read("template/.codex/agents/advisor.toml"))
    advisor_text = read("template/.codex/agents/advisor.toml")
    require(advisor.get("sandbox_mode") == "read-only", "advisor.toml の sandbox_mode は read-only にしてください。")
    require_tokens(advisor_text, ("terminal worker", "追加 subagent", "実装", "採否", "Ledger", "owner synthesis", "Guild Law", "confidence-based", "confidence delta", "同じ unknown", "owner が根拠確認"), "template/.codex/agents/advisor.toml")
    controller = tomllib.loads(read("template/.codex/agents/quest_sentinel.toml"))
    controller_text = read("template/.codex/agents/quest_sentinel.toml")
    require(controller.get("sandbox_mode") == "read-only", "quest_sentinel.toml の sandbox_mode は read-only にしてください。")
    require_tokens(
        controller_text,
        ("quest_awareness", "unknowns", "assumptions", "confidence", "verification status", "control signal", "実装", "採否", "Ledger", "Git 操作", "外部送信", "75%", "50%", "first failure", "security-sensitive", "control_decision", "rationale", "required_next_action", "escalation_required"),
        "template/.codex/agents/quest_sentinel.toml",
    )
    cartographer_text = read("template/.codex/agents/cartographer.toml")
    require_tokens(cartographer_text, ("設計", "実装計画", "方針整理", "アーキテクチャ", "mapmaking", "read-only advisor", "intent_analysis", "implementation_strategy"), "template/.codex/agents/cartographer.toml")
    party_leader_text = read("template/.codex/agents/party_leader.toml")
    require_tokens(party_leader_text, ("intent_analysis", "implementation_strategy", "confirmation_needed", "escalation"), "template/.codex/agents/party_leader.toml")
    adventurer_text = read("template/.codex/agents/adventurer.toml")
    require_tokens(adventurer_text, ("intent_analysis", "implementation_strategy", "intent_alignment", "本質的な成果", "最小十分"), "template/.codex/agents/adventurer.toml")
    guildmaster_text = read("template/.codex/agents/guildmaster.toml")
    require_tokens(guildmaster_text, ("intent_analysis", "implementation_strategy", "Party"), "template/.codex/agents/guildmaster.toml")
    inquisitor = read("template/.codex/agents/inquisitor.toml")
    courier = tomllib.loads(read("template/.codex/agents/courier.toml"))
    courier_text = read("template/.codex/agents/courier.toml")
    require_tokens(
        courier_text,
        STATE_CHANGE_GUARD_TOKENS
        + (
            "branch/commit",
            "memory_candidate_for_courier_review",
            "memory persistence authority",
            "sanitized summary",
            "prevention artifact",
            "ledger disposition",
            "trusted_instruction_from_external_input",
            "raw log",
            "secret_or_pii",
            "direct_static_runtime_write",
        ),
        "template/.codex/agents/courier.toml",
    )
    require_tokens(
        inquisitor,
        (
            "scope boundary",
            "intent_analysis",
            "intent_coverage",
            "本質的な成果",
            "confirmation_needed",
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
            "focus reviewer",
            "追加 reviewer 0..1",
            "workers.inquisitor.max_parallel",
            "cost reason",
            "finding disposition",
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
    quest_awareness_doc = read("docs/quest-awareness-runtime.md")
    require_tokens(
        quest_awareness_doc,
        ("Guild-native runtime", "正本は常に", "Quest Awareness", "自己意識ではなく", "作業中の監視、評価、制御", "制御領域", "intent_analysis", "quest_awareness", "control_decision", "implementation_strategy", "intent_coverage", "confidence-based control signal", "quest_sentinel", "invoke_security_review", "Trial 統合担当の `inquisitor`", "safety_gate", "stop_for_user_approval", "認知ミス補正", "read-only reference", "Ledger", "courier", "fixture_mode: static_contract_example", "live model 判定は正本にせず", "live model 出力に依存する CI 判定", "作らないもの"),
        "docs/quest-awareness-runtime.md",
    )
    agent_memory = read("docs/agent-memory.md")
    require_tokens(
        agent_memory,
        ("Authority Boundary", "read-only reference", "Ledger", "courier", "memory persistence authority", "raw log", "秘密値", "PII", "外部入力", "Cognitive Failure Types", "Prevention artifact", "Promotion Rule", "assumed_without_evidence", "premature_confidence", "scope_drift", "曖昧な entry"),
        "docs/agent-memory.md",
    )
    runtime_agent_memory = read("template/.agents/orchestra/docs/agent-memory.md")
    require_tokens(
        runtime_agent_memory,
        ("Authority Boundary", "read-only reference", "Ledger", "courier", "memory persistence authority", "raw log", "秘密値", "PII", "外部入力", "Cognitive Failure Types", "Prevention artifact", "Promotion Rule", "assumed_without_evidence", "premature_confidence", "scope_drift", "曖昧な entry"),
        "template/.agents/orchestra/docs/agent-memory.md",
    )
    audit_english = read("scripts/audit_english.py")
    require_tokens(
        audit_english,
        ("SENSITIVE_PATH_TERMS", "ensure_not_sensitive_path", "secret-like path", "読まずに除外"),
        "scripts/audit_english.py",
    )
    validate_audit_english_path_guard()
    golden_quest_fixture_paths = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "scripts/validation/fixtures/golden_quests").glob("*.yaml")
    ]
    template_skill_paths = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "template/.agents/skills").glob("*/SKILL.md")
    ]
    legacy_guard_allowlist_paths = {
        "scripts/install.py",
        "scripts/validation/docs.py",
        "scripts/validation/golden_quests.py",
        "scripts/validation/install_smoke.py",
        "scripts/validation/runtime_smoke.py",
        "template/.agents/orchestra/scripts/queue_db.py",
        "template/.agents/orchestra/scripts/queue_audit.py",
    }
    active_legacy_scan_paths = sorted(set(ACTIVE_PROSE_PATHS + QUEUE_TEMPLATE_PATHS + tuple(template_skill_paths) + tuple(golden_quest_fixture_paths)))
    for rel in active_legacy_scan_paths:
        text = read(rel).casefold()
        for token in LEGACY_DIRECT_CASEFOLD_TOKENS:
            require(token not in text, f"{rel} に比喩依存または旧語彙 `{token}` を入れないでください。")
    legacy_quest_awareness_scan_paths = sorted(set(active_legacy_scan_paths + [
        "scripts/install.py",
        "scripts/validation/docs.py",
        "scripts/validation/golden_quests.py",
        "scripts/validation/install_smoke.py",
        "scripts/validation/runtime_smoke.py",
        "template/.agents/orchestra/scripts/queue_db.py",
        "template/.agents/orchestra/scripts/queue_audit.py",
    ] + golden_quest_fixture_paths))
    for rel in legacy_quest_awareness_scan_paths:
        text = read(rel).casefold()
        for token in (
            "meta" "cognitive",
            "meta" "cognitive_controller",
            "meta" "cognitive-task-loop",
            "meta" "cognitive-runtime",
            "invoke_" "meta" "cognitive_controller",
        ):
            require(token not in text, f"{rel} に旧 quest_awareness 命名 `{token}` を直書きしないでください。")
    split_legacy_scan_paths = sorted(set(active_legacy_scan_paths) - legacy_guard_allowlist_paths)
    for rel in split_legacy_scan_paths:
        require(
            not _contains_split_legacy_quest_awareness_term(read(rel)),
            f"{rel} に旧 quest_awareness 命名の split 表記を入れないでください。",
        )
    combined = "\n".join(read(rel) for rel in full_contract_paths + role_paths)
    for token in LEGACY_PRIMARY_TERMS:
        require(token not in combined, f"docs/instructions に旧固定 contract `{token}` が残っています。")
    for token in VOCABULARY_DRIFT_TERMS:
        require(token not in combined, f"docs/instructions に表記揺れ `{token}` が残っています。")
    for token in AMBIGUOUS_INQUISITOR_TERMS:
        require(token not in combined, f"docs/instructions に曖昧な inquisitor 表記 `{token}` が残っています。")
    require("Trial 統合担当の `inquisitor`" in combined, "docs/instructions は Trial 統合担当の `inquisitor` 表記を使ってください。")
    require_tokens(
        combined,
        ("intent_analysis", "quest_awareness", "control_decision", "implementation_strategy", "intent_alignment", "confirmation_needed", "intent_coverage", "本質的な成果", "過剰実装"),
        "docs/instructions intent analysis contract",
    )
    common = read("template/.agents/orchestra/instructions/common.md")
    agents = read("template/AGENTS.md")
    orchestration_runtime = read("docs/orchestration-runtime.md")
    require_tokens(
        agents,
        ("`quest_awareness`: goal", "intake から Quest Charter", "owner から Trial", "Trial から Ledger / final", "`control_decision`", "`validation_evidence`"),
        "template/AGENTS.md quest_awareness handoff contract",
    )
    require_tokens(
        common,
        ("`quest_awareness`: goal", "intake から Quest Charter", "owner から Trial", "Trial から Ledger / final", "`control_decision`", "`validation_evidence`", ".agents/orchestra/docs/agent-memory.md"),
        "template/.agents/orchestra/instructions/common.md quest_awareness handoff contract",
    )
    receptionist = read("template/.agents/orchestra/instructions/receptionist.md")
    require_tokens(
        receptionist,
        ("`quest_awareness`", "initial `quest_awareness`", "confidence", "verification status"),
        "template/.agents/orchestra/instructions/receptionist.md quest_awareness charter contract",
    )
    require_tokens(
        orchestration_runtime,
        ("`quest_awareness`", "Handoff", "owner -> Trial", "Trial -> Ledger / final", "`validation_evidence`", "`revise_plan`"),
        "docs/orchestration-runtime.md quest_awareness handoff contract",
    )
    small_fix_use_case = read("docs/use-cases/02-small-fix-solo-quest.md")
    require_tokens(
        small_fix_use_case,
        ("`quest_awareness`", "`control_decision`", "`intent_alignment`", "`validation_evidence`"),
        "docs/use-cases/02-small-fix-solo-quest.md handoff contract",
    )
    focused_trial_use_case = read("docs/use-cases/04-focused-trial-after-implementation.md")
    require_tokens(
        focused_trial_use_case,
        ("`quest_awareness`", "`control_decision`", "cost reason", "finding disposition"),
        "docs/use-cases/04-focused-trial-after-implementation.md handoff contract",
    )
    require_tokens(
        combined,
        ("Handoff Sufficiency", "intent_alignment", "validation_evidence", "finding disposition", "needs_human", "request_changes"),
        "docs/instructions handoff sufficiency contract",
    )
    require_tokens(combined, FOCUS_REVIEWER_CONTRACT_TOKENS + ("validation result", "blast radius", "coupling"), "docs/instructions focus reviewer contract")
    common = read("template/.agents/orchestra/instructions/common.md")
    agents = read("template/AGENTS.md")
    runtime_readme = read("template/.agents/orchestra/README.md")
    require_tokens(common, ("Root", "target_repo_root", "実装", "Trial", "品質採否", "Ledger"), "template/.agents/orchestra/instructions/common.md")
    require_tokens(agents, ("Root", "target_repo_root", "実装", "Trial", "品質採否", "Ledger"), "template/AGENTS.md")
    require_tokens(agents, DEFAULT_INTAKE_TOKENS + ("短い説明", "orchestration-template workflow", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS + GUILD_SKILL_PRIORITY_TOKENS, "template/AGENTS.md")
    require_tokens(common, DEFAULT_INTAKE_TOKENS + ("短い説明", "orchestration-template workflow", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS + GUILD_SKILL_PRIORITY_TOKENS, "template/.agents/orchestra/instructions/common.md")
    require_tokens(agents, ("State Change Guard",) + STATE_CHANGE_GUARD_TOKENS, "template/AGENTS.md state change guard")
    require_tokens(common, ("State Change Guard",) + STATE_CHANGE_GUARD_TOKENS, "template/.agents/orchestra/instructions/common.md state change guard")
    require_tokens(agents, STATE_CHANGE_GUARD_OPERATION_TOKENS, "template/AGENTS.md state change guarded operations")
    require_tokens(common, STATE_CHANGE_GUARD_OPERATION_TOKENS, "template/.agents/orchestra/instructions/common.md state change guarded operations")
    require_tokens(runtime_readme, DEFAULT_INTAKE_TOKENS + ("短い説明", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS[:1] + GUILD_SKILL_PRIORITY_TOKENS[:3], "template/.agents/orchestra/README.md")
    require_tokens(runtime_readme, STATE_CHANGE_GUARD_TOKENS, "template/.agents/orchestra/README.md state change guard")
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
            "focus reviewer",
            "追加",
            "workers.inquisitor.max_parallel",
            "finding disposition",
            "cost reason",
            "advisor ではありません",
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
            "適切な共通化余地",
            "過度な共通化リスク",
            "同じ責務",
            "呼び出し契約",
            "見送り理由",
            "追加検証観点",
            "focus reviewer",
            "追加 reviewer 0..1",
            "workers.inquisitor.max_parallel",
            "autonomy_budget.subassignments",
            "focus 分割",
            "finding disposition",
            "skip reason",
            "cost reason",
            "対応可能な Minor",
            "保留できる Minor",
            "保留理由",
            "再検討条件",
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
    require_tokens(use_guild_workflow, ("State Change Guard",) + STATE_CHANGE_GUARD_TOKENS, "template/.agents/skills/use-guild-workflow/SKILL.md state change guard")
    require(
        "明示がない通常作業へ、この Skill を無理に適用しない" not in use_guild_workflow,
        "use-guild-workflow は always_guild_intake と衝突する旧トリガー文言を戻さないでください。",
    )
    quest_awareness_skill = read("template/.agents/skills/quest-awareness-loop/SKILL.md")
    require_tokens(
        quest_awareness_skill,
        ("quest_awareness", "control_decision", "confidence", "75%", "50%", "failed test", "first failure", "security-sensitive", "scope drift", "contradictory evidence", "未信頼"),
        "template/.agents/skills/quest-awareness-loop/SKILL.md",
    )

    runtime_readme = read("template/.agents/orchestra/README.md")
    require(
        "Ledger 反映と、Root または Quest Charter が明示した local Git 操作だけ" in runtime_readme,
        "template/.agents/orchestra/README.md の courier 説明は Ledger と明示 local Git 操作に限定してください。",
    )
    skill_state_change_targets = {
        "template/.agents/skills/git-split-commits-from-diff/SKILL.md": ("stage / commit", "PR ready"),
        "template/.agents/skills/git-branch-from-session/SKILL.md": ("branch 作成", "PR ready"),
        "template/.agents/skills/git-rename-unpushed-branch-from-diff/SKILL.md": ("branch rename", "PR ready"),
        "template/.agents/skills/github-safe-push-from-branch/SKILL.md": ("push", "人間確認"),
        "template/.agents/skills/github-pull-request-from-branch/SKILL.md": ("push / PR 作成", "人間確認"),
        "template/.agents/skills/browser-research-readonly/SKILL.md": ("ブラウザ送信", "状態更新"),
    }
    for rel, tokens in skill_state_change_targets.items():
        require_tokens(read(rel), tokens + ("明示指示", "Quest Charter", "tool / MCP / Web 出力"), f"{rel} state change guard")


def validate_stop_hook() -> None:
    text = read("template/.codex/hooks/stop_quality_gate.py")
    require("Quest" in text and "Trial" in text and "Risk" in text, "stop_quality_gate.py は Quest / Trial / Risk の最終要約を促してください。")
    hooks = read("template/.codex/hooks.json")
    hook_shell = read("template/.codex/hooks/stop_quality_gate.sh")
    require("stop_quality_gate.sh" in hooks, "hooks.json は Docker runner 用 stop_quality_gate.sh を呼び出してください。")
    require("python3" not in hooks and "/usr/bin/env python" not in hooks, "hooks.json は host Python を直接探索しないでください。")
    require("valid_root()" in hooks and "*/repositories/*" in hooks and "$1/repositories" in hooks, "hooks.json は repositories/<repo> 配下の偽 runtime を Stop hook root として採用しないでください。")
    require("docker image inspect" in hook_shell and "CODEX_GUILD_ORCHESTRA_DOCKER_SKIP_BUILD=1" in hook_shell, "stop_quality_gate.sh は cold build せず既存 runtime image だけで実行してください。")
