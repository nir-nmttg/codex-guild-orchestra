#!/usr/bin/env python3
"""未翻訳らしい英語文を検出する軽量監査。"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / "scripts",
    ROOT / "template",
]
SCAN_EXTENSIONS = {".md", ".toml", ".json", ".py", ".yaml", ".yml"}
SENSITIVE_PATH_TERMS = {
    ".ssh",
    "api_key",
    "auth",
    "credential",
    "credentials",
    "key",
    "password",
    "passwords",
    "pii",
    "private_key",
    "secret",
    "secrets",
    "token",
    "tokens",
}
PATH_TERM_RE = re.compile(r"[^a-z0-9]+")

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+#/_-]*")
NATURAL_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
URL_RE = re.compile(r"https?://\S+|git@github\.com:\S+")
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_.-]*\}")
HUMAN_PROSE_LABEL_RE = re.compile(r"^([A-Za-z][A-Za-z -]{0,30}):\s+(.+)$")
COMMAND_PREFIX_RE = re.compile(
    r"^(\$|>|\.?/|python3?\b|pip\b|npm\b|git\b|docker\b|make\b|bash\b|sh\b|cp\b|mv\b|rm\b|mkdir\b|mktemp\b|export\b|tmp=)"
)
MACOS_OPEN_APP_COMMAND_RE = re.compile(r"^open\s+-a(?:\s|$)")
SQL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_.\"]*"
SQL_SELECT_RE = re.compile(
    rf"^SELECT\b.+\bFROM\s+{SQL_IDENTIFIER}(\s+(WHERE|JOIN|ORDER\s+BY|GROUP\s+BY|LIMIT)\b|;?$)",
    re.IGNORECASE,
)
SQL_INSERT_RE = re.compile(
    rf"^INSERT\s+INTO\s+{SQL_IDENTIFIER}(\s*\(|\s+(VALUES|SELECT)\b|;?$)",
    re.IGNORECASE,
)
SQL_UPDATE_RE = re.compile(r"^UPDATE\s+[A-Za-z_][A-Za-z0-9_.\"]*\s+SET\b", re.IGNORECASE)
SQL_DELETE_RE = re.compile(
    rf"^DELETE\s+FROM\s+{SQL_IDENTIFIER}(\s+(WHERE|RETURNING)\b|;?$)",
    re.IGNORECASE,
)
SQL_SCHEMA_RE = re.compile(
    rf"^(CREATE|DROP|ALTER)\s+(TABLE|INDEX|VIEW|TRIGGER)\s+{SQL_IDENTIFIER}"
    r"(\s*\(|\s+(ADD|DROP|RENAME|AS|ON)\b|;?$)",
    re.IGNORECASE,
)
SQL_PRAGMA_RE = re.compile(r"^PRAGMA\s+[A-Za-z_][A-Za-z0-9_.]*(\s*[=;(]|$)", re.IGNORECASE)
SQL_WITH_RE = re.compile(r"^WITH\s+[A-Za-z_][A-Za-z0-9_]*\s+AS\s*\(.+\bSELECT\b", re.IGNORECASE)
SQL_CLAUSE_RE = re.compile(
    r"^(WHERE|FROM|GROUP\s+BY|ORDER\s+BY|ON\s+CONFLICT|VALUES)\b",
    re.IGNORECASE,
)
SQL_WHERE_FRAGMENT_RE = re.compile(
    r"(=|<>|!=|<=|>=|<|>|\bIS\s+(NOT\s+)?NULL\b|\bLIKE\b|\bIN\s*\(|\bBETWEEN\b.+\bAND\b)",
    re.IGNORECASE,
)
SQL_FROM_FRAGMENT_RE = re.compile(r"\b(WHERE|JOIN|ORDER\s+BY|GROUP\s+BY|LIMIT)\b", re.IGNORECASE)
SQL_ORDER_GROUP_FRAGMENT_RE = re.compile(r"[,().]|\b(ASC|DESC|COLLATE)\b", re.IGNORECASE)
SQL_ON_CONFLICT_FRAGMENT_RE = re.compile(r"\bDO\s+(UPDATE|NOTHING)\b|\(.+\)", re.IGNORECASE)
SQL_VALUES_FRAGMENT_RE = re.compile(r"^VALUES\s*\(", re.IGNORECASE)
ENGLISH_FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "then",
    "this",
    "to",
    "with",
    "without",
    "you",
    "your",
    "when",
    "where",
    "while",
    "will",
}
HUMAN_PROSE_LABELS = {
    "caution",
    "decision",
    "error",
    "important",
    "note",
    "result",
    "status",
    "tip",
    "warning",
}


def iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            ensure_not_sensitive_path(root)
            files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in SCAN_EXTENSIONS:
                ensure_not_sensitive_path(path)
                files.append(path)
    return files


def ensure_not_sensitive_path(path: Path) -> None:
    try:
        relative = path.relative_to(ROOT)
    except ValueError as exc:
        raise SystemExit(f"root 外の path は audit_english.py で読まずに除外してください: {path}") from exc
    if path.is_symlink():
        raise SystemExit(f"symlink path は audit_english.py で読まずに除外してください: {relative}")
    try:
        path.resolve(strict=False).relative_to(ROOT)
    except ValueError as exc:
        raise SystemExit(f"root 外へ解決される path は audit_english.py で読まずに除外してください: {relative}") from exc
    parts = [part.casefold() for part in relative.parts]
    split_terms = {
        term
        for part in parts
        for term in PATH_TERM_RE.split(part.strip("."))
        if term
    }
    if any(term in split_terms or term in parts for term in SENSITIVE_PATH_TERMS):
        raise SystemExit(f"secret-like path は audit_english.py で読まずに除外してください: {relative}")


def normalize_word(word: str) -> str:
    return word.strip(".,:;!?()[]{}<>\"'").lower()


def strip_placeholders(text: str) -> str:
    return PLACEHOLDER_RE.sub(" ", text)


def strip_human_prose_label(text: str) -> str:
    stripped = text.strip()
    match = HUMAN_PROSE_LABEL_RE.match(stripped)
    if not match:
        return stripped
    label = match.group(1).strip()
    if label.lower() not in HUMAN_PROSE_LABELS or not label[:1].isupper():
        return stripped
    return match.group(2).strip()


def looks_like_english_sentence(text: str) -> bool:
    stripped = text.strip()
    if not re.search(r"[.!?]$", stripped):
        return False
    words = natural_words(stripped)
    return len(words) >= 4 and bool(set(words) & ENGLISH_FUNCTION_WORDS)


def prose_label_rhs(text: str) -> str | None:
    match = HUMAN_PROSE_LABEL_RE.match(text.strip())
    if not match:
        return None
    label = match.group(1).strip()
    rhs = match.group(2).strip()
    human_facing_label = label.lower() in HUMAN_PROSE_LABELS and label[:1].isupper()
    if human_facing_label or looks_like_english_sentence(rhs):
        return rhs
    return None


def looks_like_sql_text(text: str) -> bool:
    if any(
        pattern.search(text)
        for pattern in (
            SQL_SELECT_RE,
            SQL_INSERT_RE,
            SQL_UPDATE_RE,
            SQL_DELETE_RE,
            SQL_SCHEMA_RE,
            SQL_PRAGMA_RE,
            SQL_WITH_RE,
        )
    ):
        return True
    clause_match = SQL_CLAUSE_RE.search(text)
    if not clause_match:
        return False
    clause = clause_match.group(1).upper().replace(" ", "_")
    if clause == "WHERE":
        return bool(SQL_WHERE_FRAGMENT_RE.search(text))
    if clause == "FROM":
        return bool(SQL_FROM_FRAGMENT_RE.search(text))
    if clause in {"GROUP_BY", "ORDER_BY"}:
        return bool(SQL_ORDER_GROUP_FRAGMENT_RE.search(text))
    if clause == "ON_CONFLICT":
        return bool(SQL_ON_CONFLICT_FRAGMENT_RE.search(text))
    if clause == "VALUES":
        return bool(SQL_VALUES_FRAGMENT_RE.search(text))
    return False


def is_machine_like_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    stripped = prose_label_rhs(stripped) or stripped
    stripped = strip_human_prose_label(stripped)
    if COMMAND_PREFIX_RE.search(stripped):
        return True
    if MACOS_OPEN_APP_COMMAND_RE.search(stripped):
        return True
    if looks_like_sql_text(stripped):
        return True
    if stripped.startswith(".venv/"):
        return True
    if stripped.startswith("#") and (":" in stripped or "/" in stripped):
        return True
    if re.match(r"^[A-Za-z0-9_./{}$:-]+\s*[:=]", stripped):
        return True
    stripped = strip_placeholders(stripped)
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
    line = strip_placeholders(line)

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


def natural_words(text: str) -> list[str]:
    return [
        normalize_word(word)
        for word in WORD_RE.findall(text)
        if NATURAL_WORD_RE.fullmatch(word)
    ]


def english_spans_in_cjk_text(text: str) -> list[str]:
    spans: list[str] = []
    for span in CJK_RE.split(text):
        stripped = span.strip(" \t:：,，.。;；()（）[]【】「」『』")
        if stripped and WORD_RE.search(stripped):
            spans.append(stripped)
    return spans


def should_report_finding(text: str, words: list[str]) -> bool:
    if CJK_RE.search(text):
        for span in english_spans_in_cjk_text(text):
            span_words = natural_words(span)
            if is_machine_like_text(span):
                continue
            if len(span_words) >= 4 and bool(set(span_words) & ENGLISH_FUNCTION_WORDS):
                return True
        return False
    if is_machine_like_text(text):
        return False
    return len(words) >= 4 and bool(set(words) & ENGLISH_FUNCTION_WORDS)


def audit_file(path: Path) -> list[tuple[int, str, list[str]]]:
    if path.suffix == ".py":
        return audit_python_file(path)

    findings: list[tuple[int, str, list[str]]] = []
    in_code_block = False

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if path.suffix == ".md" and line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if should_skip_line(path, line, in_code_block):
            continue

        text = strip_noise(line)
        words = natural_words(text)

        if should_report_finding(text, words):
            findings.append((lineno, line.rstrip(), words))

    return findings


def audit_python_file(path: Path) -> list[tuple[int, str, list[str]]]:
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
            words = natural_words(text)
            if should_report_finding(text, words):
                lineno = getattr(node, "lineno", 1) + offset
                findings.append((lineno, line, words))

    return findings


def main() -> int:
    all_findings: list[tuple[Path, int, str, list[str]]] = []

    for path in iter_scan_files():
        for lineno, line, words in audit_file(path):
            all_findings.append((path, lineno, line, words))

    if all_findings:
        print("未翻訳の可能性がある英語文を検出しました。")
        print("技術用語の単語列ではなく英語の説明文として残っていないか確認してください。")
        for path, lineno, line, words in all_findings:
            rel = path.relative_to(ROOT)
            joined = ", ".join(words[:8])
            print(f"- {rel}:{lineno}: {line}")
            print(f"  検出語: {joined}")
        return 1

    print("OK: 日本語化監査に成功しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
