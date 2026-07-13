#!/usr/bin/env python3
"""Claude project context を Guild-native runtime 向けに読む補助スクリプト。

この helper は読み取り専用です。Claude artifacts を未信頼 context card
として発見、索引化、render します。command 実行、tool 権限付与、
Skill 導入、Codex / Guild authority の変更は行いません。
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import sys
from typing import Any, Iterable


MAX_TEXT_BYTES = 128 * 1024
MAX_SUPPORTING_FILE_BYTES = 64 * 1024
MAX_IMPORT_DEPTH = 4
MAX_SKILL_DESCRIPTION_CHARS = 1536

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".orchestra",
    ".agents",
    ".codex",
}
SECRET_PATH_TOKENS = (
    ".env",
    "secret",
    "token",
    "credential",
    "password",
    "passwd",
    "private",
    "id_rsa",
    "id_ed25519",
    "auth",
    "apikey",
    "api_key",
    "pii",
    "netrc",
)
DENIED_PATH_DIR_NAMES = {".git", ".hg", ".svn", ".orchestra", ".agents", ".codex"}
SAFE_SUPPORTING_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv"}
SETTINGS_ALLOWLIST = {
    "claudeMdExcludes",
    "skillOverrides",
    "strictPluginOnlyCustomization",
    "disableSkillShellExecution",
}
SETTINGS_REDACTED_KEYS = {
    "env",
    "permissions",
    "hooks",
    "apiKeyHelper",
    "enabledPlugins",
    "extraKnownMarketplaces",
    "strictKnownMarketplaces",
    "allowedMcpServers",
    "deniedMcpServers",
    "disabledMcpjsonServers",
    "enabledMcpjsonServers",
    "enableAllProjectMcpServers",
}
SKILL_METADATA_ALLOWLIST = {
    "name",
    "description",
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "paths",
}
SKILL_UNSUPPORTED_FIELDS = {
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "hooks",
    "shell",
}
SKILL_BLOCKING_FIELDS = {"disallowed-tools", "context", "agent", "hooks"}
DYNAMIC_COMMAND_MARKER = "[shell command omitted by agent-guild-orchestra]"


class CompatError(Exception):
    """利用者へ返す互換性エラー。"""


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_secret_like_path(rel_path: str) -> bool:
    folded = rel_path.casefold()
    return any(token in folded for token in SECRET_PATH_TOKENS)


def denied_claude_compat_path(rel_path: str) -> str | None:
    parts = PurePosixPath(rel_path).parts
    if any(part in DENIED_PATH_DIR_NAMES for part in parts):
        return "denied_runtime_path"
    if parts and parts[-1] == ".mcp.json":
        return "denied_mcp_config"
    for index, part in enumerate(parts):
        if part != ".claude" or index + 1 >= len(parts):
            continue
        child = parts[index + 1]
        if child == "agents":
            return "denied_claude_agents"
        if child.startswith("settings") and child.endswith(".json"):
            return "denied_claude_settings"
    return None


def has_symlink_component(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def crosses_nested_git_repo(path: Path, root: Path) -> bool:
    current = path.parent if path.is_file() or path.suffix else path
    try:
        current.relative_to(root)
    except ValueError:
        return True
    while current != root:
        if (current / ".git").exists():
            return True
        current = current.parent
    return False


def safety_check_file(path: Path, root: Path, *, max_bytes: int = MAX_TEXT_BYTES) -> tuple[bool, str | None]:
    if has_symlink_component(path, root):
        return False, "symlink_path"
    resolved = path.resolve(strict=False)
    if not is_relative_to(resolved, root):
        return False, "outside_target_repo"
    if not path.exists() or not path.is_file():
        return False, "not_a_file"
    if crosses_nested_git_repo(path, root):
        return False, "nested_git_repo"
    rel = rel_posix(path, root)
    denied_reason = denied_claude_compat_path(rel)
    if denied_reason:
        return False, denied_reason
    if is_secret_like_path(rel):
        return False, "secret_like_path"
    try:
        size = path.stat().st_size
    except OSError:
        return False, "stat_failed"
    if size > max_bytes:
        return False, "too_large"
    return True, None


def read_text_file(path: Path, root: Path, *, max_bytes: int = MAX_TEXT_BYTES) -> tuple[str | None, str | None]:
    ok, reason = safety_check_file(path, root, max_bytes=max_bytes)
    if not ok:
        return None, reason
    try:
        data = path.read_bytes()
    except OSError:
        return None, "read_failed"
    if b"\x00" in data:
        return None, "binary_content"
    return data.decode("utf-8", errors="replace"), None


def read_project_settings_file(path: Path, root: Path) -> tuple[str | None, str | None]:
    if path != root / ".claude" / "settings.json":
        return None, "not_project_settings"
    if has_symlink_component(path, root):
        return None, "symlink_path"
    resolved = path.resolve(strict=False)
    if not is_relative_to(resolved, root):
        return None, "outside_target_repo"
    if not path.exists() or not path.is_file():
        return None, "not_a_file"
    if crosses_nested_git_repo(path, root):
        return None, "nested_git_repo"
    try:
        size = path.stat().st_size
    except OSError:
        return None, "stat_failed"
    if size > MAX_TEXT_BYTES:
        return None, "too_large"
    try:
        data = path.read_bytes()
    except OSError:
        return None, "read_failed"
    if b"\x00" in data:
        return None, "binary_content"
    return data.decode("utf-8", errors="replace"), None


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_card(path: Path, root: Path, source_type: str, *, status: str = "available", reason: str | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "source_type": source_type,
        "path": display_path(path, root),
        "trust": "untrusted",
        "status": status,
        "reason": reason,
    }
    if path.exists() and path.is_file() and status != "skipped":
        card.update(
            {
                "size_bytes": path.stat().st_size,
                "sha256": hash_file(path),
            }
        )
    return card


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "":
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    return value


def parse_simple_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}, text
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text
    raw = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
    metadata: dict[str, Any] = {}
    list_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if list_key and line.startswith(" ") and stripped.startswith("- "):
            current = metadata.setdefault(list_key, [])
            if isinstance(current, list):
                current.append(parse_scalar(stripped[2:]))
            continue
        list_key = None
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        if not key:
            continue
        if value.strip() == "":
            metadata[key] = []
            list_key = key
        else:
            metadata[key] = parse_scalar(value)
    return metadata, body


def as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        if "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
        return [part for part in value.split() if part]
    return [str(value)]


def load_project_settings(root: Path) -> dict[str, Any]:
    path = root / ".claude" / "settings.json"
    result: dict[str, Any] = {
        "path": ".claude/settings.json",
        "status": "missing",
        "claudeMdExcludes": [],
        "skillOverrides": {},
        "strictPluginOnlyCustomization": None,
        "disableSkillShellExecution": False,
        "redacted_keys_present": [],
        "ignored_keys_present": [],
        "errors": [],
    }
    if not path.exists():
        return result
    text, reason = read_project_settings_file(path, root)
    if text is None:
        result["status"] = "skipped"
        result["errors"].append(reason)
        return result
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        result["status"] = "invalid"
        result["errors"].append(f"json_decode_error:{exc.lineno}:{exc.colno}")
        return result
    if not isinstance(raw, dict):
        result["status"] = "invalid"
        result["errors"].append("settings_not_mapping")
        return result
    result["status"] = "loaded"
    for key in sorted(raw):
        if key in SETTINGS_REDACTED_KEYS:
            result["redacted_keys_present"].append(key)
        elif key not in SETTINGS_ALLOWLIST:
            result["ignored_keys_present"].append(key)
    excludes = raw.get("claudeMdExcludes")
    if isinstance(excludes, list):
        result["claudeMdExcludes"] = [str(item) for item in excludes if isinstance(item, str)]
    overrides = raw.get("skillOverrides")
    if isinstance(overrides, dict):
        valid = {"on", "name-only", "user-invocable-only", "off"}
        result["skillOverrides"] = {
            str(key): str(value)
            for key, value in overrides.items()
            if isinstance(value, str) and value in valid
        }
    strict = raw.get("strictPluginOnlyCustomization")
    if isinstance(strict, (bool, list)):
        result["strictPluginOnlyCustomization"] = strict
    result["disableSkillShellExecution"] = raw.get("disableSkillShellExecution") is True
    return result


def public_settings_summary(settings: dict[str, Any]) -> dict[str, Any]:
    allowlisted_keys_present: list[str] = []
    for key in sorted(SETTINGS_ALLOWLIST):
        value = settings.get(key)
        if key == "claudeMdExcludes" and value:
            allowlisted_keys_present.append(key)
        elif key == "skillOverrides" and value:
            allowlisted_keys_present.append(key)
        elif key == "strictPluginOnlyCustomization" and value is not None:
            allowlisted_keys_present.append(key)
        elif key == "disableSkillShellExecution" and value is True:
            allowlisted_keys_present.append(key)
    return {
        "path": settings.get("path"),
        "status": settings.get("status"),
        "allowlisted_keys_present": allowlisted_keys_present,
        "redacted_keys_present": sorted(as_string_list(settings.get("redacted_keys_present"))),
        "ignored_keys_present": sorted(as_string_list(settings.get("ignored_keys_present"))),
        "errors": as_string_list(settings.get("errors")),
    }


def expand_braces(pattern: str) -> list[str]:
    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return [pattern]
    before = pattern[: match.start()]
    after = pattern[match.end() :]
    return [before + part + after for part in match.group(1).split(",")]


def glob_matches(path: str, patterns: Iterable[str]) -> bool:
    candidates = [path, "/" + path]
    for pattern in patterns:
        for expanded in expand_braces(pattern):
            normalized = expanded.replace("\\", "/")
            if any(fnmatch.fnmatch(candidate, normalized) for candidate in candidates):
                return True
    return False


def excluded_by_claude_md(path: Path, root: Path, patterns: Iterable[str]) -> bool:
    if not patterns:
        return False
    absolute = path.resolve().as_posix()
    relative = rel_posix(path, root)
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        for expanded in expand_braces(normalized):
            if fnmatch.fnmatch(absolute, expanded) or fnmatch.fnmatch(relative, expanded):
                return True
    return False


def iter_target_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        kept_dirs = []
        for dirname in sorted(dirnames):
            child = current / dirname
            if dirname in IGNORED_DIR_NAMES and dirname != ".claude":
                continue
            if child.is_symlink():
                continue
            if child != root and (child / ".git").exists():
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            yield current / filename


def scope_dir_for_claude_file(path: Path) -> Path:
    if path.name == "CLAUDE.md" and path.parent.name == ".claude":
        return path.parent.parent
    return path.parent


def scope_dir_for_claude_subdir(path: Path, marker: str) -> Path:
    parts = path.parts
    for index, part in enumerate(parts):
        if part == ".claude" and index + 1 < len(parts) and parts[index + 1] == marker:
            return Path(*parts[:index])
    return path.parent


def normalize_work_paths(root: Path, values: list[str]) -> list[Path]:
    if not values:
        return [root]
    result = []
    for value in values:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        resolved = path.resolve(strict=False)
        if not is_relative_to(resolved, root):
            raise CompatError(f"work path が target_repo_root の外です: {value}")
        result.append(resolved)
    return result


def work_dirs_for_matching(work_paths: list[Path]) -> list[Path]:
    result = []
    for path in work_paths:
        if path.exists() and path.is_file():
            result.append(path.parent.resolve())
        elif path.suffix:
            result.append(path.parent.resolve())
        else:
            result.append(path.resolve(strict=False))
    return result


def is_scope_applicable(scope_dir: Path, work_paths: list[Path]) -> bool:
    scope = scope_dir.resolve(strict=False)
    return any(is_relative_to(work, scope) for work in work_paths)


def parse_paths_frontmatter(text: str) -> list[str]:
    metadata, _body = parse_simple_frontmatter(text)
    return as_string_list(metadata.get("paths"))


def rule_is_applicable(path: Path, root: Path, work_paths: list[Path], text: str) -> tuple[bool, list[str]]:
    patterns = parse_paths_frontmatter(text)
    if not patterns:
        return True, []
    scope_dir = scope_dir_for_claude_subdir(path, "rules").resolve(strict=False)
    for work in work_paths:
        rel_root = work.relative_to(root).as_posix()
        rel_scope = work.relative_to(scope_dir).as_posix() if is_relative_to(work, scope_dir) else rel_root
        if glob_matches(rel_root, patterns) or glob_matches(rel_scope, patterns):
            return True, patterns
    return False, patterns


def neutralize_dynamic_shell(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    output: list[str] = []
    in_shell_fence = False
    shell_fence_marker: str | None = None
    in_generic_fence = False
    generic_fence_marker: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if in_shell_fence:
            if shell_fence_marker and stripped.startswith(shell_fence_marker):
                in_shell_fence = False
                shell_fence_marker = None
            continue
        if in_generic_fence:
            output.append(line)
            if generic_fence_marker and stripped.startswith(generic_fence_marker):
                in_generic_fence = False
                generic_fence_marker = None
            continue
        if stripped.startswith("```!") or stripped.startswith("~~~!"):
            warnings.append("fenced_shell_command_omitted")
            shell_fence_marker = stripped[:3]
            output.append(DYNAMIC_COMMAND_MARKER)
            in_shell_fence = True
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            generic_fence_marker = stripped[:3]
            output.append(line)
            in_generic_fence = True
            continue
        if stripped.startswith("!`"):
            warnings.append("line_shell_command_omitted")
            output.append(DYNAMIC_COMMAND_MARKER)
            continue
        if stripped.startswith("!") and not stripped.startswith("!["):
            warnings.append("line_shell_command_omitted")
            output.append(DYNAMIC_COMMAND_MARKER)
            continue
        replaced, count = re.subn(r"(^|(?<=\s))!`[^`]*`", DYNAMIC_COMMAND_MARKER, line)
        if count:
            warnings.append("inline_shell_command_omitted")
        output.append(replaced)
    return "\n".join(output) + ("\n" if text.endswith("\n") else ""), sorted(set(warnings))


def render_imports(text: str, root: Path, source_path: Path, *, depth: int = 0, seen: set[Path] | None = None) -> tuple[str, list[str]]:
    seen = seen or set()
    warnings: list[str] = []
    if depth > MAX_IMPORT_DEPTH:
        return text, ["import_depth_limit"]
    output: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            output.append(line)
            continue
        if not in_fence and stripped.startswith("@") and len(stripped) > 1:
            import_ref = stripped[1:].strip()
            if import_ref.startswith(("http://", "https://", "~", "/")) or ".." in PurePosixPath(import_ref).parts:
                warnings.append(f"import_skipped:{import_ref}:unsafe_ref")
                output.append(f"[import omitted: {import_ref}]")
                continue
            import_candidate = source_path.parent / import_ref
            import_path = import_candidate.resolve(strict=False)
            if import_path in seen:
                warnings.append(f"import_skipped:{import_ref}:cycle")
                output.append(f"[import omitted: {import_ref}]")
                continue
            imported, reason = read_text_file(import_candidate, root)
            if imported is None:
                warnings.append(f"import_skipped:{import_ref}:{reason}")
                output.append(f"[import omitted: {import_ref}]")
                continue
            seen.add(import_path)
            rendered, child_warnings = render_imports(imported, root, import_candidate, depth=depth + 1, seen=seen)
            warnings.extend(child_warnings)
            output.append(f"[imported from {rel_posix(import_path, root)}]\n{rendered.rstrip()}\n[/imported]")
            continue
        output.append(line)
    return "\n".join(output) + ("\n" if text.endswith("\n") else ""), sorted(set(warnings))


def first_paragraph(text: str) -> str | None:
    lines: list[str] = []
    for line in text.strip().splitlines():
        if line.strip() == "":
            if lines:
                break
            continue
        if line.lstrip().startswith("#"):
            continue
        lines.append(line.strip())
    if not lines:
        return None
    return " ".join(lines)[:MAX_SKILL_DESCRIPTION_CHARS]


def skill_command_from_path(path: Path, root: Path) -> tuple[str, str, Path]:
    if path.name == "SKILL.md":
        skill_dir = path.parent
        parts = path.parts
        for index in range(len(parts) - 1, 0, -1):
            if parts[index] == "skills" and parts[index - 1] == ".claude":
                scope_dir = Path(*parts[: index - 1])
                command = skill_dir.name
                return command, "claude_skill", scope_dir
    if path.suffix == ".md" and path.parent.name == "commands" and path.parent.parent.name == ".claude":
        return path.stem, "claude_command", path.parent.parent.parent
    raise CompatError(f"Claude Skill または command ではありません: {path}")


def plugin_manifest_present(skill_path: Path) -> bool:
    skill_dir = skill_path.parent if skill_path.name == "SKILL.md" else skill_path.parent
    return (skill_dir / ".claude-plugin" / "plugin.json").exists()


def strict_locks_skills(settings: dict[str, Any]) -> bool:
    value = settings.get("strictPluginOnlyCustomization")
    if value is True:
        return True
    if isinstance(value, list):
        return "skills" in value
    return False


def skill_override_for(name: str, qualified_name: str, settings: dict[str, Any]) -> str:
    overrides = settings.get("skillOverrides")
    if not isinstance(overrides, dict):
        return "on"
    return str(overrides.get(qualified_name) or overrides.get(name) or "on")


def parse_skill_file(path: Path, root: Path) -> tuple[dict[str, Any], str, str | None]:
    text, reason = read_text_file(path, root)
    if text is None:
        return {}, "", reason
    metadata, body = parse_simple_frontmatter(text)
    return metadata, body, None


def build_skill_index(root: Path, work_paths: list[Path], settings: dict[str, Any]) -> list[dict[str, Any]]:
    raw_cards: list[dict[str, Any]] = []
    command_counts: dict[str, int] = {}
    for path in iter_target_files(root):
        is_skill = path.name == "SKILL.md" and ".claude" in path.parts and "skills" in path.parts
        is_command = path.suffix == ".md" and path.parent.name == "commands" and path.parent.parent.name == ".claude"
        if not is_skill and not is_command:
            continue
        ok, reason = safety_check_file(path, root)
        if not ok:
            raw_cards.append(file_card(path, root, "claude_skill", status="skipped", reason=reason))
            continue
        try:
            command, source_type, scope_dir = skill_command_from_path(path, root)
        except CompatError:
            continue
        scope_rel = "." if scope_dir.resolve() == root else scope_dir.resolve().relative_to(root).as_posix()
        qualified_name = command if scope_rel == "." else f"{scope_rel}:{command}"
        command_counts[command] = command_counts.get(command, 0) + 1
        metadata, body, read_reason = parse_skill_file(path, root)
        if read_reason:
            raw_cards.append(file_card(path, root, source_type, status="skipped", reason=read_reason))
            continue
        paths = as_string_list(metadata.get("paths"))
        applicable = True
        if paths:
            applicable = any(
                glob_matches(work.relative_to(root).as_posix(), paths)
                or (is_relative_to(work, scope_dir) and glob_matches(work.relative_to(scope_dir).as_posix(), paths))
                for work in work_paths
            )
        override = skill_override_for(command, qualified_name, settings)
        unsupported_fields = sorted(key for key in metadata if key in SKILL_UNSUPPORTED_FIELDS)
        unsafe_fields = sorted(key for key in unsupported_fields if key in SKILL_BLOCKING_FIELDS)
        status = "available"
        reason_value: str | None = None
        if strict_locks_skills(settings):
            status = "skipped"
            reason_value = "strictPluginOnlyCustomization.skills"
        elif override == "off":
            status = "skipped"
            reason_value = "skillOverrides.off"
        elif plugin_manifest_present(path):
            status = "skipped"
            reason_value = "plugin_manifest_present"
        card = file_card(path, root, source_type, status=status, reason=reason_value)
        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip():
            description = first_paragraph(body)
        if override == "name-only":
            description = None
        disable_model = metadata.get("disable-model-invocation") is True
        user_invocable = metadata.get("user-invocable") is not False and override != "off"
        model_visible = not disable_model and override not in {"user-invocable-only", "off"}
        card.update(
            {
                "name": str(metadata.get("name") or command),
                "command_name": command,
                "qualified_name": qualified_name,
                "scope": scope_rel,
                "description": description[:MAX_SKILL_DESCRIPTION_CHARS] if isinstance(description, str) else None,
                "when_to_use": metadata.get("when_to_use") if isinstance(metadata.get("when_to_use"), str) else None,
                "paths": paths,
                "applicable": applicable,
                "override": override,
                "model_visible": model_visible,
                "user_invocable": user_invocable,
                "auto_candidate": status == "available" and applicable and model_visible and not unsafe_fields,
                "unsupported_fields": unsupported_fields,
                "unsafe_fields": unsafe_fields,
            }
        )
        raw_cards.append(card)
    for card in raw_cards:
        command = card.get("command_name")
        if isinstance(command, str):
            aliases = [str(card.get("qualified_name"))]
            if command_counts.get(command, 0) == 1 or card.get("scope") == ".":
                aliases.insert(0, command)
            card["aliases"] = sorted(set(alias for alias in aliases if alias and alias != "None"))
    return sorted(raw_cards, key=lambda item: str(item.get("qualified_name") or item.get("path")))


def scan_context(root: Path, work_paths: list[Path], settings: dict[str, Any]) -> list[dict[str, Any]]:
    excludes = settings.get("claudeMdExcludes") if isinstance(settings.get("claudeMdExcludes"), list) else []
    cards: list[dict[str, Any]] = []
    work_dirs = work_dirs_for_matching(work_paths)
    for path in iter_target_files(root):
        source_type: str | None = None
        if path.name == "CLAUDE.local.md":
            source_type = "claude_local_md"
        elif path.name == "CLAUDE.md" and path.parent.name != ".claude":
            source_type = "claude_md"
        elif path.name == "CLAUDE.md" and path.parent.name == ".claude":
            source_type = "claude_project_md"
        elif path.suffix == ".md" and ".claude" in path.parts and "rules" in path.parts:
            source_type = "claude_rule"
        if source_type is None:
            continue
        if source_type == "claude_local_md":
            cards.append(file_card(path, root, source_type, status="skipped", reason="local_claude_md"))
            continue
        ok, reason = safety_check_file(path, root)
        if not ok:
            cards.append(file_card(path, root, source_type, status="skipped", reason=reason))
            continue
        if excluded_by_claude_md(path, root, excludes):
            cards.append(file_card(path, root, source_type, status="skipped", reason="claudeMdExcludes"))
            continue
        text, read_reason = read_text_file(path, root)
        if text is None:
            cards.append(file_card(path, root, source_type, status="skipped", reason=read_reason))
            continue
        patterns: list[str] = []
        if source_type == "claude_rule":
            applicable, patterns = rule_is_applicable(path, root, work_paths, text)
            scope_dir = scope_dir_for_claude_subdir(path, "rules")
        else:
            scope_dir = scope_dir_for_claude_file(path)
            applicable = any(is_scope_applicable(scope_dir, [work_dir]) for work_dir in work_dirs)
        card = file_card(path, root, source_type)
        card.update(
            {
                "scope": "." if scope_dir.resolve() == root else scope_dir.resolve().relative_to(root).as_posix(),
                "applicable": applicable,
                "paths": patterns,
            }
        )
        cards.append(card)
    return sorted(cards, key=lambda item: str(item.get("path")))


def render_context(root: Path, work_paths: list[Path], settings: dict[str, Any]) -> dict[str, Any]:
    cards = [card for card in scan_context(root, work_paths, settings) if card.get("status") == "available" and card.get("applicable")]
    rendered: list[dict[str, Any]] = []
    for card in cards:
        path = root / str(card["path"])
        text, reason = read_text_file(path, root)
        if text is None:
            rendered.append({**card, "status": "skipped", "reason": reason})
            continue
        imported, import_warnings = render_imports(text, root, path)
        inert, dynamic_warnings = neutralize_dynamic_shell(imported)
        rendered.append({**card, "content": inert, "warnings": sorted(set(import_warnings + dynamic_warnings))})
    return {
        "schema_version": "1.0",
        "target_repo_root": root.as_posix(),
        "trust": "untrusted",
        "rendered_context": rendered,
    }


def find_skill(name: str, index: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        card
        for card in index
        if name == card.get("qualified_name") or name == card.get("command_name") or name in card.get("aliases", [])
    ]
    if not matches:
        raise CompatError(f"Claude skill not found: {name}")
    available = [card for card in matches if card.get("status") == "available"]
    if len(available) == 1:
        return available[0]
    if len(available) > 1:
        names = ", ".join(str(card.get("qualified_name")) for card in available)
        raise CompatError(f"Claude Skill 名が曖昧です。qualified name を使ってください: {names}")
    return matches[0]


def replace_arguments(content: str, metadata: dict[str, Any], arguments: str) -> str:
    args = shlex.split(arguments) if arguments else []
    rendered = content
    for index, value in enumerate(args):
        rendered = rendered.replace(f"$ARGUMENTS[{index}]", value)
        rendered = re.sub(rf"(?<!\\)\${index}\b", value, rendered)
    for index, name in enumerate(as_string_list(metadata.get("arguments"))):
        if index < len(args):
            rendered = re.sub(rf"(?<!\\)\${re.escape(name)}\b", args[index], rendered)
    if "$ARGUMENTS" in rendered:
        rendered = rendered.replace("$ARGUMENTS", arguments)
    elif arguments:
        rendered = rendered.rstrip() + f"\n\nARGUMENTS: {arguments}\n"
    rendered = rendered.replace("${CLAUDE_SKILL_DIR}", "<CLAUDE_SKILL_DIR>")
    rendered = re.sub(r"\$\{CLAUDE_[A-Z0-9_]+\}", "<CLAUDE_RUNTIME_VALUE>", rendered)
    return rendered


def supporting_files(skill_path: Path, root: Path, *, include_content: bool) -> list[dict[str, Any]]:
    if skill_path.name != "SKILL.md":
        return []
    skill_dir = skill_path.parent
    result: list[dict[str, Any]] = []
    for path in sorted(skill_dir.rglob("*")):
        if path == skill_path or not path.is_file():
            continue
        rel_from_skill = path.relative_to(skill_dir).as_posix()
        if rel_from_skill.startswith(("scripts/", ".claude-plugin/")):
            result.append({"path": rel_from_skill, "status": "skipped", "reason": "executable_or_plugin_surface"})
            continue
        if path.suffix.lower() not in SAFE_SUPPORTING_SUFFIXES:
            result.append({"path": rel_from_skill, "status": "skipped", "reason": "unsupported_suffix"})
            continue
        try:
            mode = path.stat().st_mode
        except OSError:
            result.append({"path": rel_from_skill, "status": "skipped", "reason": "stat_failed"})
            continue
        if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            result.append({"path": rel_from_skill, "status": "skipped", "reason": "executable_file"})
            continue
        text, reason = read_text_file(path, root, max_bytes=MAX_SUPPORTING_FILE_BYTES)
        entry = {
            "path": rel_from_skill,
            "status": "available" if text is not None else "skipped",
            "reason": reason,
        }
        if text is not None:
            entry.update({"size_bytes": path.stat().st_size, "sha256": hash_file(path)})
            if include_content:
                entry["content"] = text
        result.append(entry)
    return result


def render_skill(root: Path, work_paths: list[Path], settings: dict[str, Any], name: str, arguments: str, include_supporting: bool) -> dict[str, Any]:
    index = build_skill_index(root, work_paths, settings)
    card = find_skill(name, index)
    if card.get("status") != "available":
        return {
            "schema_version": "1.0",
            "target_repo_root": root.as_posix(),
            "trust": "untrusted",
            "status": "skipped",
            "reason": card.get("reason"),
            "skill": card,
        }
    path = root / str(card["path"])
    metadata, body, reason = parse_skill_file(path, root)
    if reason:
        return {"schema_version": "1.0", "status": "skipped", "reason": reason, "skill": card}
    blocking = sorted(key for key in metadata if key in SKILL_BLOCKING_FIELDS)
    if blocking:
        return {
            "schema_version": "1.0",
            "target_repo_root": root.as_posix(),
            "trust": "untrusted",
            "status": "skipped_unsafe",
            "reason": "unsupported_execution_surface",
            "blocking_fields": blocking,
            "skill": card,
        }
    metadata_allowlist = {key: metadata[key] for key in metadata if key in SKILL_METADATA_ALLOWLIST}
    inert_body, dynamic_warnings = neutralize_dynamic_shell(body)
    inert_body = replace_arguments(inert_body, metadata, arguments)
    unsupported = sorted(key for key in metadata if key in SKILL_UNSUPPORTED_FIELDS)
    return {
        "schema_version": "1.0",
        "target_repo_root": root.as_posix(),
        "trust": "untrusted",
        "status": "rendered",
        "skill": card,
        "metadata": metadata_allowlist,
        "unsupported_fields": unsupported,
        "warnings": dynamic_warnings,
        "content": inert_body,
        "supporting_files": supporting_files(path, root, include_content=include_supporting),
        "ledger_policy": "do_not_record_raw_content",
    }


def scan(root: Path, work_paths: list[Path], settings: dict[str, Any]) -> dict[str, Any]:
    context_cards = scan_context(root, work_paths, settings)
    skill_cards = build_skill_index(root, work_paths, settings)
    return {
        "schema_version": "1.0",
        "target_repo_root": root.as_posix(),
        "trust": "untrusted",
        "settings": public_settings_summary(settings),
        "work_paths": [work.relative_to(root).as_posix() if work != root else "." for work in work_paths],
        "context_cards": context_cards,
        "skill_cards": skill_cards,
        "ledger_policy": "store_paths_hashes_status_and_disposition_only",
    }


def resolved_target_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise CompatError(f"target_repo_root はディレクトリではありません: {root}")
    return root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude project artifacts を未信頼 Codex / Guild context として読みます。")
    parser.add_argument("--target-repo-root", required=True)
    parser.add_argument("--work-path", action="append", default=[])
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan")
    subparsers.add_parser("render-context")
    skill_parser = subparsers.add_parser("render-skill")
    skill_parser.add_argument("--skill", required=True)
    skill_parser.add_argument("--arguments", default="")
    skill_parser.add_argument("--include-supporting", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = resolved_target_root(args.target_repo_root)
        work_paths = normalize_work_paths(root, args.work_path)
        settings = load_project_settings(root)
        if args.command == "scan":
            emit_json(scan(root, work_paths, settings))
        elif args.command == "render-context":
            emit_json(render_context(root, work_paths, settings))
        elif args.command == "render-skill":
            emit_json(render_skill(root, work_paths, settings, args.skill, args.arguments, args.include_supporting))
        else:  # pragma: no cover
            raise CompatError(f"unknown command: {args.command}")
        return 0
    except CompatError as exc:
        emit_json({"schema_version": "1.0", "status": "error", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
