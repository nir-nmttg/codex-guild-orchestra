"""repository 全体の基本検証。"""

from __future__ import annotations

from .core import ROOT, read, require, tomllib, yaml
from .rules import ACTIVE_PROSE_DRIFT_TERMS, ACTIVE_PROSE_PATHS, REQUIRED_PATHS

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
