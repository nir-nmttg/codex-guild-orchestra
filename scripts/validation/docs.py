"""Prompt surface、agent config、docs、skills、hook の契約検証。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import tempfile

from .core import ROOT, load_yaml, mapping, read, require, sequence, tomllib, yaml


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
    "adventurer": ("gpt-5.6-terra", "high"),
    "sage": ("gpt-5.6-luna", "xhigh"),
    "cartographer": ("gpt-5.6-sol", "high"),
    "courier": ("gpt-5.3-codex-spark", "xhigh"),
    "examiner": ("gpt-5.6-terra", "high"),
    "guildmaster": ("gpt-5.6-sol", "xhigh"),
    "inquisitor": ("gpt-5.6-sol", "xhigh"),
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

VSCODE_SKILL_FRONTMATTER_FIELDS = {
    "argument-hint",
    "compatibility",
    "context",
    "description",
    "disable-model-invocation",
    "license",
    "metadata",
    "name",
    "user-invocable",
}


def _line_count(rel: str) -> int:
    return len(read(rel).splitlines())


def _validated_model_policy() -> tuple[str, dict[str, tuple[str, str]]]:
    settings = mapping(load_yaml("template/.agents/orchestra/config/settings.yaml"), "settings.yaml")
    policy = mapping(settings.get("model_policy"), "settings.model_policy")
    require(
        set(policy)
        == {
            "root_model",
            "root_project_local_reasoning_effort",
            "root_user_selectable_reasoning_efforts",
            "fixed_pair_per_subagent",
            "subagent_pairs",
        },
        "settings.model_policy は定義済みのRoot方針とsubagent pairだけを含めてください。",
    )
    root_model = policy.get("root_model")
    require(root_model == "gpt-5.6-sol", "settings.model_policy.root_model は gpt-5.6-sol にしてください。")
    require(
        policy.get("root_project_local_reasoning_effort") == "unset",
        "settings.model_policy はRoot reasoning effortをproject-localで固定しないでください。",
    )
    require(
        sequence(policy.get("root_user_selectable_reasoning_efforts"), "settings.model_policy.root_user_selectable_reasoning_efforts")
        == ["high", "xhigh", "ultra"],
        "settings.model_policy のRoot選択肢は high / xhigh / ultra にしてください。",
    )
    require(policy.get("fixed_pair_per_subagent") is True, "settings.model_policy はsubagentごとの固定pairを要求してください。")

    pairs = mapping(policy.get("subagent_pairs"), "settings.model_policy.subagent_pairs")
    require(set(pairs) == set(EXPECTED_AGENT_MODEL_CONFIGS), "settings.model_policy.subagent_pairs は定義済みの10 roleだけを含めてください。")
    normalized: dict[str, tuple[str, str]] = {}
    for role, expected_pair in EXPECTED_AGENT_MODEL_CONFIGS.items():
        pair = mapping(pairs.get(role), f"settings.model_policy.subagent_pairs.{role}")
        require(set(pair) == {"model", "model_reasoning_effort"}, f"settings.model_policy.subagent_pairs.{role} はmodel/effortの固定pairにしてください。")
        actual_pair = (pair.get("model"), pair.get("model_reasoning_effort"))
        require(actual_pair == expected_pair, f"settings.model_policy.subagent_pairs.{role} は {expected_pair[0]} / {expected_pair[1]} にしてください。")
        normalized[role] = expected_pair
    return str(root_model), normalized


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
    expected_root_model, expected_agent_model_configs = _validated_model_policy()
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
        require((data["model"], data["model_reasoning_effort"]) == expected_agent_model_configs[role], f"{rel} のmodel/effortが不正です。")
        features = mapping(data.get("features"), f"{rel}.features")
        expected_multi_agent = role == "inquisitor"
        require(features.get("multi_agent") is expected_multi_agent, f"{rel} のmulti_agentはinquisitorだけtrueにしてください。")
        developer = str(data["developer_instructions"])
        require(len(developer.splitlines()) <= 18, f"{rel} のdeveloper_instructionsをrole固有の18行以内にしてください。")
        require("instructions/common.md" not in developer and "config/settings.yaml" not in developer, f"{rel} はcommon/settingsを常時再読込しないでください。")
        for token in QUALITY_REDUCING_TOKENS:
            require(token not in developer, f"{rel} に旧制約 `{token}` が残っています。")

    config = tomllib.loads(read("template/.codex/config.toml"))
    require(config.get("model") == expected_root_model, "Root templateのmodelはSolにしてください。")
    require("model_reasoning_effort" not in config, "Root templateでreasoning effortを固定しないでください。")
    require(config.get("sandbox_mode") == "read-only", "Root sandboxはread-onlyにしてください。")
    require(config.get("approval_policy") == "on-request" and config.get("approvals_reviewer") == "auto_review", "Root approval contractが不正です。")
    require(config.get("web_search") == "cached" and config.get("allow_login_shell") is False, "Root web/shell contractが不正です。")
    require(mapping(config.get("sandbox_workspace_write"), "config.sandbox_workspace_write").get("network_access") is True, "workspace-write networkは有効にしてください。")
    agents = mapping(config.get("agents"), "config.agents")
    require(agents.get("max_threads") == 64 and agents.get("max_depth") == 2, "agent concurrencyはmax_threads=64/max_depth=2にしてください。")
    require(agents.get("job_max_runtime_seconds") == 2400, "agent job runtimeは2400秒にしてください。")


def _validate_parallelism_doc(rel: str, text: str) -> None:
    allocation_contracts = {
        "docs/agent-deployment.md": (
            "非adventurer合計16の計48",
            "global 64との差16",
        ),
        "docs/orchestration-runtime.md": (
            "role別上限の合計は48",
            "うち非adventurerは16",
            "globalとの差16",
        ),
    }
    require(rel in allocation_contracts, f"{rel} のrole配分検証契約が未定義です。")
    required = (
        "adventurer.max_parallel=32",
        "max_threads=64",
        "未割当headroom",
        *allocation_contracts[rel],
    )
    require(all(token in text for token in required), f"{rel} にtotal 48 / non-adventurer 16 / 未割当headroom 16の契約が必要です。")
    require(
        all(old not in text for old in ("adventurer.max_parallel=48", "adventurer.max_parallel=64", "非adventurerの16枠を予約", "追加スロット制限を設けません")),
        f"{rel} に旧adventurer占有・残余割当契約を残さないでください。",
    )


def _markdown_h2_section(rel: str, text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    require(text.count(marker) == 1, f"{rel} にH2 section `{heading}` を1つ定義してください。")
    start = text.index(marker)
    end = text.find("\n## ", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def _validate_current_deployment_docs() -> None:
    readme = _markdown_h2_section("README.md", read("README.md"), "仕組み")
    for token in ("`sage`はLuna/xhigh", "`inquisitor`はSol/xhigh"):
        require(token in readme, f"README.md の現行deployment説明に `{token}` が必要です。")

    changelog = _markdown_h2_section("CHANGELOG.md", read("CHANGELOG.md"), "[Unreleased]")
    for token in (
        "`sage`をLuna/xhigh",
        "`inquisitor`をSol/xhigh",
        "`job_max_runtime_seconds`を1800秒から2400秒へ延長",
    ):
        require(token in changelog, f"CHANGELOG.md のUnreleased契約に `{token}` が必要です。")

    deployment_text = read("docs/agent-deployment.md")
    configuration = _markdown_h2_section("docs/agent-deployment.md", deployment_text, "Configuration")
    require("job_max_runtime_seconds = 2400" in configuration, "agent-deployment.md の現行job runtimeは2400秒にしてください。")
    deployment_pairs = _markdown_h2_section("docs/agent-deployment.md", deployment_text, "Deployment role pairs")
    for row in (
        "| `sage` | `gpt-5.6-luna` | `read-only` | `xhigh` |",
        "| `inquisitor` | `gpt-5.6-sol` | `read-only` | `xhigh` |",
    ):
        require(row in deployment_pairs, f"agent-deployment.md の現行role pair表に `{row}` が必要です。")
    for token in ("`sage`はLuna/xhigh", "`inquisitor`はSol/xhigh"):
        require(token in deployment_pairs, f"agent-deployment.md の現行pair説明に `{token}` が必要です。")

    selection_text = read("docs/model-selection-evaluation.md")
    fixed_matrix = _markdown_h2_section("docs/model-selection-evaluation.md", selection_text, "固定マトリクス")
    for row in (
        "| `sage` | `gpt-5.6-luna` | `xhigh` |",
        "| `inquisitor` | `gpt-5.6-sol` | `xhigh` |",
        "| `inquisitor` | Sol `xhigh` / Sol `high` |",
        "| `sage` | Luna `xhigh` / Terra `xhigh` / Sol `xhigh`",
        "別dimensionの診断用effort challengerはLuna `high`",
    ):
        require(row in fixed_matrix, f"model-selection-evaluation.md の現行固定マトリクスに `{row}` が必要です。")
    for token in ("`sage`のみxhighでLuna/Terra/Solを比べます", "`inquisitor`はSol/xhighをdeploymentへ固定"):
        require(token in selection_text, f"model-selection-evaluation.md の現行evaluation説明に `{token}` が必要です。")


def validate_docs_and_instructions() -> None:
    require(_line_count("template/AGENTS.md") <= 125, "AGENTS.mdを125行以内のcompact kernelにしてください。")
    require(_line_count("template/.agents/orchestra/instructions/common.md") <= 55, "common.mdを55行以内にしてください。")
    require(_line_count("template/.agents/orchestra/config/settings.yaml") <= 240, "settings.yamlを240行以内の機械契約にしてください。")

    agents = read("template/AGENTS.md")
    for token in ("target_repo_root", "success_criteria", "State changes", "Evidence-based control", "Rootだけ", "artificer", "stale_evidence", "結論を先"):
        require(token in agents, f"AGENTS.md のcompact kernelに `{token}` が必要です。")
    for token in QUALITY_REDUCING_TOKENS:
        require(token not in agents, f"AGENTS.md に旧制約 `{token}` が残っています。")
    for token in (
        "対象repoを読まない回答・説明",
        "Rootはcoordinationとjudgeに専念",
        "対象repoの調査、実装、検証、browser、debug、review evidence収集",
        "Rootだけがtop-level custom agent",
        "`inquisitor`だけがdepth 2の`examiner`",
        "`high`、`xhigh`、`ultra`",
        "Rootは返されたevidenceをsuccess criteriaとsnapshotへ照合して次actionを決めます",
    ):
        require(token in agents, f"AGENTS.md にRoot coordination-only契約 `{token}` が必要です。")
    for stale_root_contract in (
        "説明とread-only調査は不要なQuestを作らずRootが直接進めます",
        "read-only fast pathはRootが継続できる",
        "Rootが変更に直接対応する検証を実行",
        "Rootが`examiner`を直接起動",
    ):
        require(stale_root_contract not in agents, f"AGENTS.md に旧Root直接作業契約 `{stale_root_contract}` を戻さないでください。")

    common = read("template/.agents/orchestra/instructions/common.md")
    require("custom agentの起動時promptへ重ねて読み込みません" in common, "common.mdは常時promptではないことを明記してください。")
    require("数値confidence" in common and "要求しません" in common, "common.mdは数値confidenceを要求しないでください。")
    for token in (
        "担当roleの完了を待ってevidenceをgate",
        "対象repoの探索、コード・差分・repo文書の読み取り、実装、validation、browser、debug、review evidence収集",
        "Rootへreportを返します",
    ):
        require(token in common, f"common.md にRoot/worker report loop `{token}` が必要です。")

    deployment = read("docs/agent-deployment.md")
    runtime = read("docs/orchestration-runtime.md")
    for rel, text in (("docs/agent-deployment.md", deployment), ("docs/orchestration-runtime.md", runtime)):
        _validate_parallelism_doc(rel, text)
    _validate_current_deployment_docs()

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
        end_marker = text.find("\n---\n", 4)
        require(end_marker != -1, f"{rel} のfrontmatterを `---` で閉じてください。")
        require(yaml is not None, "Skill frontmatter検証にはPyYAMLが必要です。")
        try:
            document = yaml.safe_load(text[4:end_marker])  # type: ignore[union-attr]
        except yaml.YAMLError as exc:  # type: ignore[union-attr]
            require(False, f"{rel} のfrontmatterをYAMLとして読めません: {exc}")
        frontmatter = mapping(document, f"{rel} frontmatter")
        require(all(isinstance(key, str) for key in frontmatter), f"{rel} のfrontmatter keyは文字列にしてください。")
        unexpected_fields = sorted(set(frontmatter) - VSCODE_SKILL_FRONTMATTER_FIELDS)
        require(
            not unexpected_fields,
            f"{rel} にVS Code Agent Skills schema非対応のfrontmatter fieldがあります: " + ", ".join(unexpected_fields),
        )

        name = frontmatter.get("name")
        description = frontmatter.get("description")
        require(isinstance(name, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is not None, f"{rel}.name はhyphen-caseにしてください。")
        require(len(name) <= 64 and name == skill_md.parent.name, f"{rel}.name は64文字以内で親directory名と一致させてください。")
        require(isinstance(description, str) and 1 <= len(description) <= 1024, f"{rel}.description は1〜1024文字にしてください。")

        skill_metadata = mapping(frontmatter.get("metadata"), f"{rel}.metadata")
        require(
            all(isinstance(key, str) and isinstance(value, str) for key, value in skill_metadata.items()),
            f"{rel}.metadata は文字列key/valueのmappingにしてください。",
        )
        require(skill_metadata.get("owner") == "agent-guild-orchestra", f"{rel}.metadata.owner は agent-guild-orchestra にしてください。")
        require(isinstance(skill_metadata.get("scope"), str) and bool(skill_metadata["scope"]), f"{rel}.metadata.scope を空でない文字列にしてください。")

        for key in ("argument-hint", "license"):
            if key in frontmatter:
                require(isinstance(frontmatter[key], str) and bool(frontmatter[key]), f"{rel}.{key} は空でない文字列にしてください。")
        if "compatibility" in frontmatter:
            compatibility = frontmatter["compatibility"]
            require(isinstance(compatibility, str) and 1 <= len(compatibility) <= 500, f"{rel}.compatibility は1〜500文字にしてください。")
        if "context" in frontmatter:
            require(frontmatter["context"] == "fork", f"{rel}.context はVS Codeが対応する `fork` にしてください。")
        for key in ("disable-model-invocation", "user-invocable"):
            if key in frontmatter:
                require(isinstance(frontmatter[key], bool), f"{rel}.{key} はboolにしてください。")

        openai_yaml = skill_md.parent / "agents/openai.yaml"
        require(openai_yaml.is_file(), f"{rel} には agents/openai.yaml が必要です。")
        openai_rel = str(openai_yaml.relative_to(ROOT))
        openai_document = mapping(load_yaml(openai_rel), openai_rel)
        interface = mapping(openai_document.get("interface"), f"{openai_rel}.interface")
        for key in ("display_name", "short_description", "default_prompt"):
            require(
                isinstance(interface.get(key), str) and bool(interface[key].strip()),
                f"{openai_rel}.interface.{key} は空でない文字列にしてください。",
            )
        short_description = interface["short_description"]
        require(25 <= len(short_description) <= 64, f"{openai_rel}.interface.short_description は25〜64文字にしてください。")
        require(
            f"${name}" in interface["default_prompt"],
            f"{openai_rel}.interface.default_prompt は `${name}` を明示してください。",
        )
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
    estimate_skill = read("template/.agents/skills/communicate-work-estimates/SKILL.md")
    for token in ("開始時", "subagentへ委任", "critical path", "残り時間", "増加だけでなく"):
        require(token in estimate_skill, f"communicate-work-estimates skillに `{token}` が必要です。")


def validate_stop_hook() -> None:
    text = read("template/.codex/hooks/stop_quality_gate.py")
    require("Quest" in text and "Trial" in text and "Risk" in text, "stop_quality_gate.py はQuest/Trial/Riskの要約を促してください。")
    hooks = read("template/.codex/hooks.json")
    shell = read("template/.codex/hooks/stop_quality_gate.sh")
    require("stop_quality_gate.sh" in hooks, "hooks.json はstop_quality_gate.shを呼び出してください。")
    require("python3" not in hooks and "/usr/bin/env python" not in hooks, "hooks.json はhost Pythonを直接探索しないでください。")
    require("valid_root()" in hooks and "*/repositories/*" in hooks and "$1/repositories" in hooks, "hooks.json のroot guardが不足しています。")
    require("docker image inspect" in shell and "AGENT_GUILD_ORCHESTRA_DOCKER_SKIP_BUILD=1" in shell, "Stop hookはcold buildせず既存imageを使ってください。")
    strict_env = "AGENT_GUILD_ORCHESTRA_STOP_QUALITY_STRICT"
    legacy_strict_env = "CODEX" + "_STOP_QUALITY_STRICT"
    require(strict_env in text and strict_env in shell, "Stop hookはAgent Guild固有のstrict環境変数を使ってください。")
    require(legacy_strict_env not in text and legacy_strict_env not in shell, "Stop hookに旧strict環境変数を残さないでください。")
    for rel in ("scripts/docker_python.sh", "template/.agents/orchestra/scripts/docker_python.sh"):
        runner = read(rel)
        require("CODEX_HOOK_PAYLOAD" in runner, f"{rel} はCodex hook payloadをコンテナへ渡してください。")
        require(strict_env in runner and legacy_strict_env not in runner, f"{rel} はAgent Guild固有のstrict環境変数だけを渡してください。")
