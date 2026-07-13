"""repository 全体の基本検証。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re

from .core import ROOT, read, require, tomllib, yaml
from .rules import ACTIVE_PROSE_DRIFT_TERMS, ACTIVE_PROSE_PATHS, REQUIRED_PATHS


LEGACY_BRAND_RE = re.compile(
    "(?:" + "codex" + r"[-_ ]guild|\b" + ("c" + "go") + r"\b|" + ("c" + "go") + r"[_-])",
    re.IGNORECASE,
)
BRAND_SCAN_EXTENSIONS = {".json", ".md", ".py", ".sh", ".sql", ".toml", ".txt", ".yaml", ".yml"}
BRAND_SCAN_FILENAMES = {"Dockerfile", "LICENSE", "Makefile", "VERSION", ".dockerignore", ".gitignore"}
BRAND_SCAN_ROOTS = (".github", "docs", "scripts", "template")
BRAND_SENSITIVE_COMPONENTS = {
    ".aws",
    ".env",
    ".envrc",
    ".kube",
    ".mcp",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".ssh",
    "envrc",
    "id_dsa",
    "id_ecdsa",
    "id_ecdsa_sk",
    "id_ed25519",
    "id_ed25519_sk",
    "id_rsa",
    "netrc",
    "npmrc",
    "pypirc",
    "service-account",
    "service_account",
}
BRAND_SENSITIVE_PATH_TERMS = {"auth", "credential", "credentials", "key", "keys", "oauth", "password", "passwords", "private_key", "secret", "secrets", "token", "tokens"}
BRAND_SECRET_SUFFIXES = {".jks", ".key", ".keystore", ".p12", ".pem", ".pfx"}
BRAND_PII_RE = re.compile(r"(?:^|[-_.])(pii|personal[-_]?data|customer[-_]?export)(?:$|[-_.])", re.IGNORECASE)
BRAND_SERVICE_ACCOUNT_RE = re.compile(r"(?:^|[-_.])service[-_]?accounts?(?:$|[-_.])", re.IGNORECASE)
REQUIRED_ROOT_BRAND_COVERAGE = {"LICENSE.ja.md", "SUPPORT.md", "THIRD_PARTY_NOTICES.md", "requirements.txt"}


def _is_sensitive_brand_path(rel: str) -> bool:
    parts = [part.casefold() for part in rel.split("/")]
    for part in parts:
        path_part = PurePosixPath(part)
        split_terms = {term for term in re.split(r"[^a-z0-9]+", part.strip(".")) if term}
        if (
            any(
                part.startswith(component)
                and (len(part) == len(component) or not part[len(component)].isalnum())
                for component in BRAND_SENSITIVE_COMPONENTS
            )
            or path_part.suffix.casefold() in BRAND_SECRET_SUFFIXES
            or bool(split_terms & BRAND_SENSITIVE_PATH_TERMS)
            or BRAND_PII_RE.search(part) is not None
            or BRAND_SERVICE_ACCOUNT_RE.search(part) is not None
        ):
            return True
    return False


def _brand_tree_paths(root: Path) -> list[Path]:
    pending = [root]
    paths: list[Path] = []
    while pending:
        directory = pending.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError as exc:
            require(False, f"旧ブランド監査でdirectoryを列挙できません: {directory}: {exc}")
        for path in children:
            paths.append(path)
            rel = path.relative_to(ROOT).as_posix()
            if path.is_symlink() or _is_sensitive_brand_path(rel):
                continue
            if path.is_dir():
                pending.append(path)
    return paths


def validate_brand_identity() -> None:
    legacy_acronym = "c" + "go"
    sensitive_legacy_path = "docs/" + legacy_acronym + "-secret.txt"
    require(LEGACY_BRAND_RE.search("Codex" + " Guild") is not None, "旧ブランド検出patternが表示名を検出できません。")
    require(LEGACY_BRAND_RE.search("codex" + "-guild-wrapper") is not None, "旧ブランド検出patternがhyphen identifierを検出できません。")
    require(LEGACY_BRAND_RE.search("codex" + "_guild_wrapper") is not None, "旧ブランド検出patternがunderscore identifierを検出できません。")
    require(LEGACY_BRAND_RE.search(legacy_acronym) is not None, "旧略称検出patternが単独略称を検出できません。")
    require(LEGACY_BRAND_RE.search(legacy_acronym + "_eval") is not None, "旧略称検出patternがunderscore identifierを検出できません。")
    require(LEGACY_BRAND_RE.search(legacy_acronym + "-snapshot") is not None, "旧略称検出patternがhyphen identifierを検出できません。")
    require(LEGACY_BRAND_RE.search("OpenAI Codex integration") is None, "Codex製品一般の説明を旧ブランドとして扱わないでください。")
    require(LEGACY_BRAND_RE.search("CODEX_HOOK_PAYLOAD") is None, "Codex hook payloadを旧ブランドとして扱わないでください。")
    require(
        LEGACY_BRAND_RE.search(sensitive_legacy_path) is not None and _is_sensitive_brand_path(sensitive_legacy_path),
        "機密らしいpathはpathnameの旧ブランドだけを検出し、contentを読まないでください。",
    )
    for rel in (
        ".env.yaml",
        "service-account.json",
        "service_account.json",
        "id_rsa.txt",
        "id_ed25519.pub.bak",
        ".envrc",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "client-secret.pem",
        "customer-export.csv",
        "passwords.yaml",
        "api-keys.json",
        "keys.txt",
        "private-keys.yaml",
        "service-accounts.json",
        "prod-service-account.json",
        "gcp_service_account.json",
    ):
        require(_is_sensitive_brand_path(rel), f"secret-like pathをcontent読取前に拒否してください: {rel}")
    for rel in (
        "LICENSE.ja.md",
        "SUPPORT.md",
        "THIRD_PARTY_NOTICES.md",
        "requirements.txt",
        "docs/keyboard-shortcuts.md",
        "docs/keynote.md",
        "docs/authoring-guide.md",
        "docs/service-accounting.md",
        "docs/accountability.md",
    ):
        require(not _is_sensitive_brand_path(rel), f"通常のdoc pathをsecret-likeとして除外しないでください: {rel}")

    root_paths = list(ROOT.iterdir())
    covered_root_text_files = {
        path.name
        for path in root_paths
        if not path.is_symlink()
        and path.is_file()
        and (path.suffix in BRAND_SCAN_EXTENSIONS or path.name in BRAND_SCAN_FILENAMES)
    }
    require(REQUIRED_ROOT_BRAND_COVERAGE <= covered_root_text_files, "root直下の既存text fileを旧ブランド監査対象にしてください。")

    paths = list(root_paths)
    for rel in BRAND_SCAN_ROOTS:
        scan_root = ROOT / rel
        require(not scan_root.is_symlink() and scan_root.is_dir(), f"旧ブランド監査rootが通常directoryではありません: {rel}")
        paths.extend(_brand_tree_paths(scan_root))

    matches: list[str] = []
    for path in sorted(paths):
        rel = path.relative_to(ROOT)
        if LEGACY_BRAND_RE.search(rel.as_posix()):
            matches.append(str(rel))
        if _is_sensitive_brand_path(rel.as_posix()):
            continue
        if path.is_symlink() or not path.is_file():
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
