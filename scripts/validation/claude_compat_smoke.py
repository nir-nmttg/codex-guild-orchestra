"""Claude 互換 helper の smoke 検証。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import ROOT, ValidationError, mapping, require, sequence


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
        (target / "packages/web/src").mkdir(parents=True)
        (target / ".claude/skills/deploy").mkdir(parents=True)
        (target / ".git").mkdir(parents=True)
        (target / "packages/web/src/app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        (target / "docs").mkdir()
        (target / "docs/context.md").write_text("Imported context.\n", encoding="utf-8")
        (target / ".mcp.json").write_text('{"sentinel":"MCP_RENDER_SENTINEL"}\n', encoding="utf-8")
        (target / ".git/config").write_text("[remote]\nurl = GIT_RENDER_SENTINEL\n", encoding="utf-8")
        (target / "CLAUDE.md").write_text(
            "# Root Claude\n"
            "@docs/context.md\n"
            "@.mcp.json\n"
            "@.git/config\n"
            "!printf omit-context\n",
            encoding="utf-8",
        )
        (target / ".claude/settings.json").write_text(
            json.dumps({"env": {"SECRET_TOKEN": "SETTINGS_ENV_SENTINEL"}, "hooks": {"PreToolUse": "HOOKS_SENTINEL"}, "model": "MODEL_SENTINEL"}),
            encoding="utf-8",
        )
        (target / ".claude/skills/deploy/SKILL.md").write_text(
            "---\ndescription: Deploy root app\nallowed-tools: Bash(git status)\n---\nDeploy root.\n!`printf omit-root`\n",
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

        skill_cards = sequence(scan.get("skill_cards"), "claude_compat.scan.skill_cards")
        skill_names = {str(mapping(card, "skill_card").get("qualified_name")) for card in skill_cards}
        require("deploy" in skill_names, "claude_compat scan は repo 内 skill を検出してください。")

        rendered = run_claude_compat(helper, target, "render-skill", "--skill", "deploy")
        require(rendered.get("status") == "rendered", "明示 skill render は成功してください。")
        require("omit-root" not in str(rendered.get("content")), "動的 command 本文をそのまま render しないでください。")
        require("shell command omitted" in str(rendered.get("content")), "動的 command は無害な marker にしてください。")
        require("allowed-tools" in sequence(rendered.get("unsupported_fields"), "claude_compat.render_skill.unsupported_fields"), "Claude metadata は Codex 権限へ変換せず unsupported_fields に留めてください。")

        rendered_context = run_claude_compat(helper, target, "render-context")
        rendered_text = json.dumps(rendered_context, ensure_ascii=False)
        require("Imported context." in rendered_text, "安全な repo 内 @import は render-context に取り込んでください。")
        for omitted in (".mcp.json", ".git/config"):
            require(f"[import omitted: {omitted}]" in rendered_text, f"危険な @import `{omitted}` は omit marker にしてください。")
        for sentinel in ("MCP_RENDER_SENTINEL", "GIT_RENDER_SENTINEL", "SETTINGS_ENV_SENTINEL", "HOOKS_SENTINEL", "MODEL_SENTINEL"):
            require(sentinel not in rendered_text, f"claude 互換 render-context は検証値 `{sentinel}` を露出しないでください。")
