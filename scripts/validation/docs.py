"""agent / documentation / skill / hook の契約検証。"""

from __future__ import annotations

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
    STATE_CHANGE_GUARD_OPERATION_TOKENS,
    STATE_CHANGE_GUARD_TOKENS,
    TRIAL_CONDITIONAL_CHECKS,
    TRIAL_DEPTH_GUARDRAILS,
    TRIAL_REQUIRED_CHECKS,
    VOCABULARY_DRIFT_TERMS,
)

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
    require_tokens(config_text, ("focus reviewer", "workers.inquisitor.max_parallel", "autonomy_budget.subassignments"), "template/.codex/config.toml")
    advisor = tomllib.loads(read("template/.codex/agents/advisor.toml"))
    advisor_text = read("template/.codex/agents/advisor.toml")
    require(advisor.get("sandbox_mode") == "read-only", "advisor.toml の sandbox_mode は read-only にしてください。")
    require(advisor.get("model_reasoning_effort") == "xhigh", "advisor.toml の model_reasoning_effort は xhigh にしてください。")
    require_tokens(advisor_text, ("terminal worker", "追加 subagent", "実装", "採否", "Ledger", "owner synthesis", "Guild Law", "confidence-based", "confidence delta", "同じ unknown", "owner が根拠確認"), "template/.codex/agents/advisor.toml")
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
    require(courier.get("model") == "gpt-5.3-codex-spark", "courier.toml の model は gpt-5.3-codex-spark にしてください。")
    require(courier.get("model_reasoning_effort") == "xhigh", "courier.toml の model_reasoning_effort は xhigh にしてください。")
    require_tokens(courier_text, STATE_CHANGE_GUARD_TOKENS + ("branch/commit",), "template/.codex/agents/courier.toml")
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
        ("intent_analysis", "implementation_strategy", "intent_alignment", "confirmation_needed", "intent_coverage", "本質的な成果", "過剰実装"),
        "docs/instructions intent analysis contract",
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
    require("docker image inspect" in hook_shell and "CODEX_GUILD_ORCHESTRA_DOCKER_SKIP_BUILD=1" in hook_shell, "stop_quality_gate.sh は cold build せず既存 runtime image だけで実行してください。")
