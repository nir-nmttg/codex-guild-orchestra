#!/usr/bin/env python3
"""未翻訳らしい英語文を検出する軽量監査。"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "docs/localization-allowlist.txt"
SCAN_ROOTS = [
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / "scripts",
    ROOT / "template",
]
SCAN_EXTENSIONS = {".md", ".toml", ".json", ".py", ".yaml", ".yml"}
EXCLUDED_NAMES = {
    "localization-allowlist.txt",
}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+#/_-]*")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
URL_RE = re.compile(r"https?://\S+|git@github\.com:\S+")
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
COMMAND_PREFIX_RE = re.compile(
    r"^(\$|>|\.?/|python3?\b|pip\b|npm\b|git\b|docker\b|make\b|bash\b|sh\b|cp\b|mv\b|rm\b|mkdir\b|mktemp\b|export\b|tmp=)"
)
MACOS_OPEN_APP_COMMAND_RE = re.compile(r"^open\s+-a(?:\s|$)")
CONTEXTUAL_SCHEMA_WORDS = {
    "data",
    "review",
    "default",
    "no",
    "pending",
    "report",
    "summary",
    "status",
    "message",
    "settings",
    "read",
    "write",
    "changes",
    "verification",
}


def load_allowlist() -> set[str]:
    terms: set[str] = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        terms.add(normalize_word(stripped))
    return terms


def iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in SCAN_EXTENSIONS and path.name not in EXCLUDED_NAMES:
                files.append(path)
    return files


def normalize_word(word: str) -> str:
    return word.strip(".,:;!?()[]{}<>\"'").lower()


def is_machine_like_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if COMMAND_PREFIX_RE.search(stripped):
        return True
    if MACOS_OPEN_APP_COMMAND_RE.search(stripped):
        return True
    if stripped.startswith(".venv/"):
        return True
    if stripped.startswith("#") and (":" in stripped or "/" in stripped):
        return True
    if re.match(r"^[A-Za-z0-9_./{}$:-]+\s*[:=]", stripped):
        return True
    machine_markers = ("{", "}", "[", "]", "$(", "->", "::", " = ", " == ", " != ")
    if any(marker in stripped for marker in machine_markers):
        return True
    if "/" in stripped and " " not in stripped:
        return True
    return False


def looks_like_prose(text: str) -> bool:
    words = [normalize_word(word) for word in WORD_RE.findall(text)]
    return len(words) >= 2 and not is_machine_like_text(text)


def strip_noise(line: str) -> str:
    line = URL_RE.sub("", line)

    def keep_prose(match: re.Match[str]) -> str:
        content = match.group(0)[1:-1]
        return f" {content} " if looks_like_prose(content) else " "

    return INLINE_CODE_RE.sub(keep_prose, line)


def should_skip_line(path: Path, line: str, in_code_block: bool) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if in_code_block and is_machine_like_text(stripped):
        return True
    toml_machine_keys = (
        "name",
        "model",
        "model_reasoning_effort",
        "sandbox_mode",
        "approval_policy",
        "network_access",
        "max_threads",
        "max_depth",
        "job_max_runtime_seconds",
        "hooks",
    )
    if path.suffix == ".toml" and re.match(rf"^({'|'.join(toml_machine_keys)})\s*=", stripped):
        return True
    if path.suffix == ".json" and '"command"' in stripped:
        return True
    return False


def should_report_finding(text: str, words: list[str], unapproved: list[str]) -> bool:
    if CJK_RE.search(text):
        unapproved = [word for word in unapproved if word not in CONTEXTUAL_SCHEMA_WORDS]
        return len(unapproved) >= 3
    if is_machine_like_text(text):
        return False
    if len(unapproved) >= 3:
        return True
    if len(unapproved) >= 2 and len(words) >= 2:
        return True
    return False


def audit_file(path: Path, allowlist: set[str]) -> list[tuple[int, str, list[str]]]:
    if path.suffix == ".py":
        return audit_python_file(path, allowlist)

    findings: list[tuple[int, str, list[str]]] = []
    in_code_block = False

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if path.suffix == ".md" and line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if should_skip_line(path, line, in_code_block):
            continue

        text = strip_noise(line)
        words = [normalize_word(word) for word in WORD_RE.findall(text)]
        unapproved = [word for word in words if word and word not in allowlist]

        if should_report_finding(text, words, unapproved):
            findings.append((lineno, line.rstrip(), unapproved))

    return findings


def audit_python_file(path: Path, allowlist: set[str]) -> list[tuple[int, str, list[str]]]:
    findings: list[tuple[int, str, list[str]]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if " " not in node.value and "\n" not in node.value:
            continue

        for offset, line in enumerate(node.value.splitlines()):
            if is_machine_like_text(line):
                continue
            text = strip_noise(line)
            words = [normalize_word(word) for word in WORD_RE.findall(text)]
            unapproved = [word for word in words if word and word not in allowlist]
            if should_report_finding(text, words, unapproved):
                lineno = getattr(node, "lineno", 1) + offset
                findings.append((lineno, line, unapproved))

    return findings


def main() -> int:
    allowlist = load_allowlist()
    all_findings: list[tuple[Path, int, str, list[str]]] = []

    for path in iter_scan_files():
        for lineno, line, words in audit_file(path, allowlist):
            all_findings.append((path, lineno, line, words))

    if all_findings:
        print("未翻訳の可能性がある英語文を検出しました。")
        print("技術用語として残す場合は docs/localization-allowlist.txt に追加してください。")
        for path, lineno, line, words in all_findings:
            rel = path.relative_to(ROOT)
            joined = ", ".join(words[:8])
            print(f"- {rel}:{lineno}: {line}")
            print(f"  未許可語: {joined}")
        return 1

    print("OK: 日本語化監査に成功しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
