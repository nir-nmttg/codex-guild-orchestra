"""Prompt surface、agent config、docs、skills、hook の契約検証。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

from .core import ROOT, mapping, read, require, sequence, tomllib


EXPECTED_AGENT_SANDBOX_MODES = {
    "adventurer": "workspace-write",
    "sage": "read-only",
    "cartographer": "read-only",
    "courier": "workspace-write",
    "examiner": "read-only",
    "guildmaster": "read-only",
    "inquisitor": "read-only",
    "artificer": "workspace-write",
    "captain": "read-only",
    "warden": "read-only",
}

EXPECTED_AGENT_MODEL_CONFIGS = {
    "adventurer": ("gpt-5.6-sol", "high"),
    "sage": ("gpt-5.6-sol", "high"),
    "cartographer": ("gpt-5.6-sol", "high"),
    "courier": ("gpt-5.3-codex-spark", "xhigh"),
    "examiner": ("gpt-5.6-sol", "high"),
    "guildmaster": ("gpt-5.6-sol", "xhigh"),
    "inquisitor": ("gpt-5.6-sol", "high"),
    "artificer": ("gpt-5.6-sol", "high"),
    "captain": ("gpt-5.6-sol", "high"),
    "warden": ("gpt-5.6-sol", "high"),
}

RUNTIME_PROSE = (
    "template/AGENTS.md",
    "template/.agents/orchestra/instructions/common.md",
    "template/.agents/orchestra/README.md",
    "README.md",
    "docs/orchestration-runtime.md",
    "docs/guild-quest-lifecycle.md",
    "docs/quest-awareness-runtime.md",
    "docs/customization.md",
    "docs/prompt-recipes.md",
    "docs/agent-deployment.md",
)

QUALITY_REDUCING_TOKENS = (
    "always_guild_intake",
    "confidence_percent",
    "confidence_target_percent",
    "confidence_delta_min_percent",
    "confidence が 75%",
    "confidence が 50%",
    "cost reason",
    "cost_reason_required_always",
    "extra_file_reads",
    "validation_iterations",
)


def _line_count(rel: str) -> int:
    return len(read(rel).splitlines())


def validate_audit_english_path_guard() -> None:
    spec = importlib.util.spec_from_file_location("audit_english_guard", ROOT / "scripts/audit_english.py")
    require(spec is not None and spec.loader is not None, "scripts/audit_english.py をimportできません。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for rel in ("docs/credentials.md", "docs/secrets.md", "docs/tokens.md", "docs/api_key.txt", "docs/auth.json"):
        try:
            module.ensure_not_sensitive_path(ROOT / rel)
        except SystemExit:
            continue
        require(False, f"audit_english.py はsecret-like pathを読む前に拒否してください: {rel}")

    for rel in ("docs/keyboard-shortcuts.md", "docs/authoring-guide.md"):
        try:
            module.ensure_not_sensitive_path(ROOT / rel)
        except SystemExit as exc:
            require(False, f"audit_english.py が無害なpathを拒否しました: {rel}: {exc}")

    original_root = module.ROOT
    with tempfile.TemporaryDirectory() as tmp:
        fake_root = Path(tmp) / "repo"
        fake_root.mkdir()
        external = Path(tmp) / "external.txt"
        external.write_text("external\n", encoding="utf-8")
        link = fake_root / "docs" / "keyboard-shortcuts.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(external)
        module.ROOT = fake_root
        try:
            try:
                module.ensure_not_sensitive_path(link)
            except SystemExit:
                pass
            else:
                require(False, "audit_english.py はsymlinkを読む前に拒否してください。")
        finally:
            module.ROOT = original_root


def validate_agents() -> None:
    require(tomllib is not None, "TOML検証にはtomllib/tomliが必要です。")
    agent_paths = sorted((ROOT / "template/.codex/agents").glob("*.toml"))
    actual = {path.stem for path in agent_paths}
    require(actual == set(EXPECTED_AGENT_SANDBOX_MODES), "custom agent一覧が期待値と一致しません: " + ", ".join(sorted(actual)))

    for path in agent_paths:
        rel = str(path.relative_to(ROOT))
        raw = path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        role = path.stem
        for key in ("name", "description", "model", "model_reasoning_effort", "sandbox_mode", "developer_instructions"):
            require(key in data, f"{rel} に {key} が必要です。")
        require(data["name"] == role, f"{rel} のnameはfilenameと一致させてください。")
        require(data["sandbox_mode"] == EXPECTED_AGENT_SANDBOX_MODES[role], f"{rel} のsandbox_modeが不正です。")
        require((data["model"], data["model_reasoning_effort"]) == EXPECTED_AGENT_MODEL_CONFIGS[role], f"{rel} のmodel/effortが不正です。")
        features = mapping(data.get("features"), f"{rel}.features")
        require(features.get("multi_agent") is False, f"{rel} はterminal agentとしてmulti_agent=falseにしてください。")
        developer = str(data["developer_instructions"])
        require(len(developer.splitlines()) <= 18, f"{rel} のdeveloper_instructionsをrole固有の18行以内にしてください。")
        require("instructions/common.md" not in developer and "config/settings.yaml" not in developer, f"{rel} はcommon/settingsを常時再読込しないでください。")
        for token in QUALITY_REDUCING_TOKENS:
            require(token not in developer, f"{rel} に旧制約 `{token}` が残っています。")

    config = tomllib.loads(read("template/.codex/config.toml"))
    require(
        config.get("model") == "gpt-5.6-sol" and config.get("model_reasoning_effort") == "high",
        "Root templateの既定値はSol/highにしてください。利用者overrideはhigh/xhigh/maxだけを許可します。",
    )
    require(config.get("sandbox_mode") == "read-only", "Root sandboxはread-onlyにしてください。")
    require(config.get("approval_policy") == "on-request" and config.get("approvals_reviewer") == "auto_review", "Root approval contractが不正です。")
    require(config.get("web_search") == "cached" and config.get("allow_login_shell") is False, "Root web/shell contractが不正です。")
    require(mapping(config.get("sandbox_workspace_write"), "config.sandbox_workspace_write").get("network_access") is True, "workspace-write networkは有効にしてください。")
    agents = mapping(config.get("agents"), "config.agents")
    require(agents.get("max_threads") == 6 and agents.get("max_depth") == 1, "agent concurrencyはmax_threads=6/max_depth=1にしてください。")


def validate_docs_and_instructions() -> None:
    require(_line_count("template/AGENTS.md") <= 125, "AGENTS.mdを125行以内のcompact kernelにしてください。")
    require(_line_count("template/.agents/orchestra/instructions/common.md") <= 55, "common.mdを55行以内にしてください。")
    require(_line_count("template/.agents/orchestra/config/settings.yaml") <= 240, "settings.yamlを240行以内の機械契約にしてください。")

    agents = read("template/AGENTS.md")
    for token in ("target_repo_root", "success_criteria", "State changes", "Evidence-based control", "Rootだけ", "artificer", "stale_evidence", "結論を先"):
        require(token in agents, f"AGENTS.md のcompact kernelに `{token}` が必要です。")
    for token in QUALITY_REDUCING_TOKENS:
        require(token not in agents, f"AGENTS.md に旧制約 `{token}` が残っています。")

    common = read("template/.agents/orchestra/instructions/common.md")
    require("custom agentの起動時promptへ重ねて読み込みません" in common, "common.mdは常時promptではないことを明記してください。")
    require("数値confidence" in common and "要求しません" in common, "common.mdは数値confidenceを要求しないでください。")

    role_paths = sorted((ROOT / "template/.agents/orchestra/instructions").glob("*.md"))
    for path in role_paths:
        rel = str(path.relative_to(ROOT))
        require(len(path.read_text(encoding="utf-8").splitlines()) <= 65, f"{rel} を65行以内のrole referenceにしてください。")

    for rel in RUNTIME_PROSE:
        text = read(rel)
        for token in QUALITY_REDUCING_TOKENS:
            require(token not in text, f"{rel} に旧制約 `{token}` が残っています。")

    use_case_root = ROOT / "docs/use-cases"
    use_case_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(use_case_root.glob("*.md")))
    for token in QUALITY_REDUCING_TOKENS:
        require(token not in use_case_text, f"docs/use-cases に旧制約 `{token}` が残っています。")
    for token in ("evidence_state", "artificer", "risk-triggered", "例外"):
        require(token in use_case_text, f"docs/use-cases は新設計 `{token}` を説明してください。")

    quest_control = read("docs/quest-awareness-runtime.md")
    for token in ("evidence_state", "blocking_unknowns", "failed_checks", "scope_drift", "high_risk_triggers", "数値confidenceを使わ"):
        require(token in quest_control, f"quest-awareness-runtime.md に `{token}` が必要です。")

    validate_audit_english_path_guard()


def validate_skills() -> None:
    skills_root = ROOT / "template/.agents/skills"
    require(skills_root.exists(), "template/.agents/skills が必要です。")
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        rel = str(skill_md.relative_to(ROOT))
        text = skill_md.read_text(encoding="utf-8")
        require(text.startswith("---\n"), f"{rel} はfrontmatterで始めてください。")
        for section in ("## 使う時", "## 入力", "## 手順", "## 出力", "## 安全", "## 停止条件"):
            require(section in text, f"{rel} に {section} が必要です。")
        require("未信頼" in text or "外部入力" in text or "秘密" in text, f"{rel} は安全境界を明記してください。")
        for token in QUALITY_REDUCING_TOKENS:
            require(token not in text, f"{rel} に旧制約 `{token}` が残っています。")

    control_skill = read("template/.agents/skills/quest-awareness-loop/SKILL.md")
    for token in ("evidence_state", "blocking_unknowns", "failed_checks", "scope drift", "contradictory evidence"):
        require(token in control_skill, f"quest-awareness-loop skillに `{token}` が必要です。")
    guild_skill = read("template/.agents/skills/use-guild-workflow/SKILL.md")
    require("risk-adaptive" in guild_skill and "fast path" in guild_skill, "use-guild-workflowはrisk-adaptive fast pathを説明してください。")


def validate_stop_hook() -> None:
    text = read("template/.codex/hooks/stop_quality_gate.py")
    require("Quest" in text and "Trial" in text and "Risk" in text, "stop_quality_gate.py はQuest/Trial/Riskの要約を促してください。")
    hooks = read("template/.codex/hooks.json")
    shell = read("template/.codex/hooks/stop_quality_gate.sh")
    require("stop_quality_gate.sh" in hooks, "hooks.json はstop_quality_gate.shを呼び出してください。")
    require("python3" not in hooks and "/usr/bin/env python" not in hooks, "hooks.json はhost Pythonを直接探索しないでください。")
    require("valid_root()" in hooks and "*/repositories/*" in hooks and "$1/repositories" in hooks, "hooks.json のroot guardが不足しています。")
    require("docker image inspect" in shell and "CODEX_GUILD_ORCHESTRA_DOCKER_SKIP_BUILD=1" in shell, "Stop hookはcold buildせず既存imageを使ってください。")
