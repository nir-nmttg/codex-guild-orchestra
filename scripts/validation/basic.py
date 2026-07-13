"""repository 全体の基本検証。"""

from __future__ import annotations

import re

from .core import ROOT, read, require, tomllib, yaml
from .rules import ACTIVE_PROSE_DRIFT_TERMS, ACTIVE_PROSE_PATHS, REQUIRED_PATHS


LEGACY_BRAND_RE = re.compile("codex" + r"[-_ ]guild", re.IGNORECASE)
BRAND_SCAN_EXTENSIONS = {".json", ".md", ".py", ".sh", ".sql", ".toml", ".txt", ".yaml", ".yml"}
BRAND_SCAN_FILENAMES = {"Dockerfile", "LICENSE", "Makefile", "VERSION", ".dockerignore", ".gitignore"}
BRAND_SCAN_ROOTS = (".github", "docs", "scripts", "template")
BRAND_ROOT_FILES = (".dockerignore", ".gitignore", "CHANGELOG.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "Dockerfile", "LICENSE", "Makefile", "README.md", "SECURITY.md", "VERSION", "compose.yaml")
BRAND_SENSITIVE_PATH_TERMS = {".ssh", "api_key", "auth", "credential", "credentials", "key", "password", "pii", "private_key", "secret", "secrets", "token", "tokens"}


def _is_sensitive_brand_path(rel: str) -> bool:
    parts = [part.casefold() for part in rel.split("/")]
    split_terms = {
        term
        for part in parts
        for term in re.split(r"[^a-z0-9]+", part.strip("."))
        if term
    }
    return any(term in split_terms or term in parts for term in BRAND_SENSITIVE_PATH_TERMS)


def validate_brand_identity() -> None:
    require(LEGACY_BRAND_RE.search("Codex" + " Guild") is not None, "旧ブランド検出patternが表示名を検出できません。")
    require(LEGACY_BRAND_RE.search("codex" + "-guild-wrapper") is not None, "旧ブランド検出patternがhyphen identifierを検出できません。")
    require(LEGACY_BRAND_RE.search("codex" + "_guild_wrapper") is not None, "旧ブランド検出patternがunderscore identifierを検出できません。")
    require(LEGACY_BRAND_RE.search("OpenAI Codex integration") is None, "Codex製品一般の説明を旧ブランドとして扱わないでください。")

    paths = [ROOT / rel for rel in BRAND_ROOT_FILES]
    for rel in BRAND_SCAN_ROOTS:
        paths.extend((ROOT / rel).rglob("*"))

    matches: list[str] = []
    for path in sorted(paths):
        rel = path.relative_to(ROOT)
        if _is_sensitive_brand_path(rel.as_posix()):
            continue
        if LEGACY_BRAND_RE.search(rel.as_posix()):
            matches.append(str(rel))
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix not in BRAND_SCAN_EXTENSIONS and path.name not in BRAND_SCAN_FILENAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            require(False, f"旧ブランド監査で {rel} を読めません: {exc}")
        if LEGACY_BRAND_RE.search(text):
            matches.append(str(rel))
    require(not matches, "旧ブランド由来の名前が残っています: " + ", ".join(matches))


def validate_active_prose_vocabulary() -> None:
    paths = list(ACTIVE_PROSE_PATHS)
    skills_root = ROOT / "template/.agents/skills"
    if skills_root.exists():
        paths.extend(str(path.relative_to(ROOT)) for path in sorted(skills_root.glob("*/SKILL.md")))

    for rel in paths:
        text = read(rel)
        for token in ACTIVE_PROSE_DRIFT_TERMS:
            require(token not in text, f"{rel} に Guild 命名から外れる表現 `{token}` が残っています。")


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
