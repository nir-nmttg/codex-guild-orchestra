#!/usr/bin/env python3
"""Git subject snapshot を canonical JSON と SHA-256 digest にする。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import Any


DIGEST_VERSION = "cgo-snapshot-v1"
KINDS = {"revision_only", "working_tree_content", "commit_range"}
SECRET_COMPONENTS = {
    ".env",
    ".envrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credential",
    "secrets",
    "secret",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
PII_PATTERN = re.compile(r"(?:^|[-_.])(pii|personal[-_]?data|customer[-_]?export)(?:$|[-_.])", re.IGNORECASE)
PSEUDO_REFS = {
    "AUTO_MERGE",
    "BISECT_HEAD",
    "CHERRY_PICK_HEAD",
    "FETCH_HEAD",
    "MERGE_HEAD",
    "ORIG_HEAD",
    "REVERT_HEAD",
}


class SnapshotError(RuntimeError):
    """snapshot の入力または対象状態が安全に処理できない。"""


def _git_safe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    denied_exact = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_EXTERNAL_DIFF",
        "GIT_DIFF_OPTS",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
        "GIT_SSH",
        "GIT_SSH_COMMAND",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
    }
    for key in list(environment):
        if key in denied_exact or key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_"):
            environment.pop(key, None)
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
        }
    )
    return environment


def _run(repo: Path, args: list[str], *, check: bool = True) -> bytes:
    try:
        result = subprocess.run(
            [
                "git",
                "--no-pager",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "diff.orderFile=/dev/null",
                "-c",
                "core.attributesFile=/dev/null",
                "-c",
                "core.excludesFile=/dev/null",
                *args,
            ],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=_git_safe_environment(),
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise SnapshotError(f"git {' '.join(args)} timed out") from exc
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise SnapshotError(f"git {' '.join(args)} failed ({result.returncode}): {detail}")
    return result.stdout


def _assert_regular_if_present(path: Path, *, label: str, required: bool = False) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if required:
            raise SnapshotError(f"Git metadata がありません: {label}")
        return
    except OSError as exc:
        raise SnapshotError(f"Git metadata を安全に検証できません: {label}: {exc}") from exc
    if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
        raise SnapshotError(f"Git metadata は通常fileにしてください: {label}")


def _assert_internal_git_tree(git_directory: Path) -> None:
    for entry in os.scandir(git_directory):
        if entry.is_symlink() or not (entry.is_file(follow_symlinks=False) or entry.is_dir(follow_symlinks=False)):
            raise SnapshotError(f".git直下にsymlink / special entryがあります: {entry.name}")
    for relative in ("commondir", "objects/info/alternates", "objects/info/http-alternates", "config.worktree"):
        path = git_directory / relative
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SnapshotError(f"Git metadata indirectionを検証できません: .git/{relative}: {exc}") from exc
        raise SnapshotError(f"external Git object/config indirection は対応しません: .git/{relative}")
    for relative, required in (("HEAD", True), ("index", False), ("packed-refs", False), ("shallow", False)):
        _assert_regular_if_present(git_directory / relative, label=f".git/{relative}", required=required)
    entry_count = 0
    for relative, required in (
        ("objects", True),
        ("refs", True),
        ("info", False),
        ("logs", False),
        ("rebase-apply", False),
        ("rebase-merge", False),
        ("sequencer", False),
    ):
        root = git_directory / relative
        try:
            root_mode = root.lstat().st_mode
        except FileNotFoundError:
            if required:
                raise SnapshotError(f"Git metadata directory がありません: .git/{relative}")
            continue
        except OSError as exc:
            raise SnapshotError(f"Git metadata directory を検証できません: .git/{relative}: {exc}") from exc
        if not stat.S_ISDIR(root_mode) or stat.S_ISLNK(root_mode):
            raise SnapshotError(f"Git metadata directory はrepo内の実directoryにしてください: .git/{relative}")
        for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            directory_path = Path(directory)
            for name in dirnames:
                entry_count += 1
                mode = (directory_path / name).lstat().st_mode
                if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                    raise SnapshotError(f"Git metadata tree にsymlink / special directoryがあります: {directory_path / name}")
            for name in filenames:
                entry_count += 1
                mode = (directory_path / name).lstat().st_mode
                if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                    raise SnapshotError(f"Git metadata tree にsymlink / special fileがあります: {directory_path / name}")
            if entry_count > 1_000_000:
                raise SnapshotError("Git metadata tree が大きすぎるため安全に検証できません。")


def _repo_root(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    if not candidate.is_dir():
        raise SnapshotError(f"repo が directory ではありません: {candidate}")
    git_directory = candidate / ".git"
    try:
        git_mode = git_directory.lstat().st_mode
    except OSError as exc:
        raise SnapshotError(f"standard .git directory を確認できません: {exc}") from exc
    if not stat.S_ISDIR(git_mode) or stat.S_ISLNK(git_mode):
        raise SnapshotError("linked worktree / symlink .git はtarget root外を読めるため対応しません。")
    _assert_internal_git_tree(git_directory)
    config_path = git_directory / "config"
    try:
        config_mode = config_path.lstat().st_mode
        if not stat.S_ISREG(config_mode) or stat.S_ISLNK(config_mode) or config_path.stat().st_size > 1_000_000:
            raise SnapshotError(".git/config は1MB以下の通常fileにしてください。")
        config_text = config_path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise SnapshotError(f".git/config を安全に検証できません: {exc}") from exc
    if re.search(r"(?im)^\s*\[\s*include(?:if)?\b", config_text):
        raise SnapshotError("repo-local Git config include はtarget root外を読めるため対応しません。")
    if re.search(r"(?im)^\s*worktree\s*=", config_text):
        raise SnapshotError("repo-local core.worktree override は対応しません。")
    if re.search(r"(?im)^\s*worktreeconfig\s*=\s*true\s*$", config_text):
        raise SnapshotError("repo-local extensions.worktreeConfig は対応しません。")
    actual = Path(_run(candidate, ["rev-parse", "--show-toplevel"]).decode().strip()).resolve()
    if candidate != actual:
        raise SnapshotError(f"--repo は Git root と一致させてください: expected={candidate} actual={actual}")
    return actual


def _resolve_commit(repo: Path, value: str, *, label: str) -> str:
    if not value or value.startswith("-") or "\0" in value or "\n" in value or "\r" in value:
        raise SnapshotError(f"{label} は単一のcommit refにしてください。")
    match = re.fullmatch(r"(.+?)(?:([~^][0-9]*)*)", value)
    base = match.group(1) if match is not None else ""
    ancestry = value[len(base):]
    oid = re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", base) is not None
    head = base == "HEAD"
    named_ref = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", base) is not None
    invalid_named_ref = (
        base in PSEUDO_REFS
        or (base.isupper() and "_" in base)
        or ".." in base
        or "//" in base
        or base.endswith(".")
        or base.endswith("/")
        or "/." in base
    )
    if ancestry and re.fullmatch(r"(?:[~^][0-9]*)+", ancestry) is None:
        raise SnapshotError(f"{label} のancestry表現が不正です。")
    if not (oid or head or (named_ref and not invalid_named_ref)):
        raise SnapshotError(f"{label} はOID、HEAD、または通常のheads/tags/remotes refに限定してください。")
    raw = _run(repo, ["rev-parse", "--verify", "--end-of-options", f"{value}^{{commit}}"])
    resolved = raw.decode("ascii", errors="strict").strip()
    if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", resolved) is None:
        raise SnapshotError(f"{label} を単一のcommit OIDへ解決できません。")
    return resolved


def _safe_relative(value: str, *, label: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise SnapshotError(f"{label} が安全な repo-relative path ではありません: {value}")
    normalized = path.as_posix()
    for part in path.parts:
        folded = part.casefold()
        stem = PurePosixPath(part).stem.casefold()
        if (
            folded in SECRET_COMPONENTS
            or stem in SECRET_COMPONENTS
            or folded.startswith(".env.")
            or PurePosixPath(part).suffix.casefold() in SECRET_SUFFIXES
            or PII_PATTERN.search(folded)
        ):
            raise SnapshotError(f"{label} は secret-like / PII-like path のため読み取りません: {normalized}")
    return normalized


def _nul_paths(raw: bytes, *, label: str) -> list[str]:
    values: list[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        values.append(_safe_relative(item.decode("utf-8", errors="strict"), label=label))
    return values


def _path_is_within_scope(path: str, scopes: list[str]) -> bool:
    path_parts = PurePosixPath(path).parts
    return any(path_parts[: len(PurePosixPath(scope).parts)] == PurePosixPath(scope).parts for scope in scopes)


def _assert_no_symlink(repo: Path, paths: list[str]) -> None:
    for rel in paths:
        current = repo
        for part in PurePosixPath(rel).parts:
            current = current / part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                break
            if stat.S_ISLNK(mode):
                raise SnapshotError(f"symlink path または ancestor は snapshot 対象にできません: {rel}")


def _read_untracked_beneath(repo: Path, rel: str) -> tuple[bytes, int]:
    parts = PurePosixPath(rel).parts
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(repo, directory_flags)
    try:
        for part in parts[:-1]:
            try:
                next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            except OSError as exc:
                raise SnapshotError(f"untracked path の ancestor を安全に辿れません: {rel}: {exc}") from exc
            os.close(directory_fd)
            directory_fd = next_fd
            try:
                os.stat(".git", dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise SnapshotError(f"nested repository 配下は snapshot 対象にできません: {rel}")
        try:
            descriptor = os.open(parts[-1], file_flags, dir_fd=directory_fd)
        except OSError as exc:
            raise SnapshotError(f"untracked path を安全に開けません: {rel}: {exc}") from exc
        with os.fdopen(descriptor, "rb") as stream:
            opened_mode = os.fstat(stream.fileno()).st_mode
            if not stat.S_ISREG(opened_mode):
                raise SnapshotError(f"untracked path は通常 file にしてください: {rel}")
            return stream.read(), opened_mode
    finally:
        os.close(directory_fd)


def _assert_no_tracked_special_path(
    repo: Path,
    paths: list[str],
    *,
    kind: str,
    base_ref: str | None,
    head_ref: str | None,
) -> None:
    if not paths:
        return
    commands: list[list[str]]
    if kind == "commit_range":
        assert base_ref is not None and head_ref is not None
        commands = [["ls-tree", "-r", "-z", ref, "--", *paths] for ref in (base_ref, head_ref)]
    elif kind == "working_tree_content":
        assert base_ref is not None
        commands = [
            ["ls-tree", "-r", "-z", base_ref, "--", *paths],
            ["ls-files", "-s", "-z", "--", *paths],
        ]
    else:
        commands = [["ls-files", "-s", "-z", "--", *paths]]
    for command in commands:
        raw = _run(repo, command)
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            prefix, _, path_bytes = entry.partition(b"\t")
            if prefix.startswith(b"120000 "):
                rel = path_bytes.decode("utf-8", errors="replace")
                raise SnapshotError(f"tracked symlink は snapshot 対象にできません: {rel}")
            if prefix.startswith(b"160000 "):
                rel = path_bytes.decode("utf-8", errors="replace")
                raise SnapshotError(f"submodule / nested repository は snapshot 対象にできません: {rel}")


def _changed_paths(repo: Path, *, kind: str, base_ref: str | None, head_ref: str | None, scopes: list[str]) -> list[str]:
    args = ["diff", "--name-only", "-z", "--no-ext-diff", "--no-textconv"]
    if kind == "working_tree_content":
        args.append(base_ref or "HEAD")
    elif kind == "commit_range":
        if not base_ref or not head_ref:
            raise SnapshotError("commit_range には --base-ref と --head-ref が必要です。")
        args.extend([base_ref, head_ref])
    if scopes:
        args.extend(["--", *scopes])
    return _nul_paths(_run(repo, args), label="changed path")


def _patch_bytes(repo: Path, *, kind: str, base_ref: str | None, head_ref: str | None, scopes: list[str]) -> bytes:
    args = ["diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv"]
    if kind == "working_tree_content":
        args.append(base_ref or "HEAD")
    elif kind == "commit_range":
        assert base_ref is not None and head_ref is not None
        args.extend([base_ref, head_ref])
    if scopes:
        args.extend(["--", *scopes])
    return _run(repo, args)


def _record(hasher: Any, label: str, payload: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


def _untracked_records(repo: Path, paths: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for rel in sorted(paths, key=lambda value: value.encode("utf-8")):
        safe = _safe_relative(rel, label="untracked path")
        tracked = _run(repo, ["ls-files", "-z", "--", safe])
        if tracked:
            raise SnapshotError(f"--untracked に tracked path を指定しないでください: {safe}")
        content, opened_mode = _read_untracked_beneath(repo, safe)
        content_hash = hashlib.sha256(content).hexdigest()
        records.append(
            {
                "path": safe,
                "mode": stat.S_IMODE(opened_mode),
                "size": len(content),
                "sha256": content_hash,
            }
        )
    return records


def build_snapshot(args: argparse.Namespace) -> dict[str, object]:
    repo = _repo_root(args.repo)
    scopes = sorted({_safe_relative(value, label="scope path") for value in args.scope}, key=lambda value: value.encode("utf-8"))
    untracked = sorted({_safe_relative(value, label="untracked path") for value in args.untracked}, key=lambda value: value.encode("utf-8"))
    if args.kind == "revision_only" and untracked:
        raise SnapshotError("revision_only は --untracked を受け付けません。")
    if args.kind == "commit_range" and untracked:
        raise SnapshotError("commit_range は --untracked を受け付けません。")
    if args.kind != "revision_only" and not scopes:
        raise SnapshotError("content digest には1件以上の --scope が必要です。")
    if any(not _path_is_within_scope(path, scopes) for path in untracked):
        raise SnapshotError("--untracked は明示した --scope 内だけにしてください。")
    if args.kind == "working_tree_content":
        actual_untracked = _nul_paths(
            _run(repo, ["ls-files", "--others", "--exclude-standard", "-z", "--", *scopes]),
            label="actual untracked path",
        )
        if set(actual_untracked) != set(untracked):
            raise SnapshotError("subject scope 内の実 untracked path 集合をすべて --untracked で明示してください。")

    current_head = _resolve_commit(repo, "HEAD", label="HEAD")
    resolved_base_ref: str | None = None
    resolved_head_ref: str | None = None
    revision_id = current_head
    if args.kind == "working_tree_content":
        resolved_base_ref = _resolve_commit(repo, args.base_ref or "HEAD", label="base ref")
    elif args.kind == "commit_range":
        if not args.base_ref or not args.head_ref:
            raise SnapshotError("commit_range には --base-ref と --head-ref が必要です。")
        resolved_base_ref = _resolve_commit(repo, args.base_ref, label="base ref")
        resolved_head_ref = _resolve_commit(repo, args.head_ref, label="head ref")
        revision_id = resolved_head_ref
    status_args = ["status", "--porcelain=v1", "-z", "--untracked-files=normal"]
    if scopes:
        status_args.extend(["--", *scopes])
    status_raw = _run(repo, status_args)
    dirty_state = "dirty" if status_raw else "clean"
    snapshot: dict[str, object] = {
        "digest_version": DIGEST_VERSION,
        "kind": args.kind,
        "revision_id": revision_id,
        "base_ref": resolved_base_ref,
        "head_ref": resolved_head_ref,
        "scope_paths": scopes,
        "untracked_paths": untracked,
        "dirty_state": dirty_state,
        "diff_hash": None,
    }
    if args.kind == "revision_only":
        if dirty_state != "clean":
            raise SnapshotError("revision_only の subject scope は clean にしてください。dirty 内容は working_tree_content を使います。")
        identity = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        snapshot["snapshot_id"] = "sha256:" + hashlib.sha256(identity).hexdigest()
        return snapshot

    changed = _changed_paths(
        repo,
        kind=args.kind,
        base_ref=resolved_base_ref,
        head_ref=resolved_head_ref,
        scopes=scopes,
    )
    for path in changed:
        _safe_relative(path, label="changed path")
    _assert_no_symlink(repo, changed)
    _assert_no_tracked_special_path(
        repo,
        changed,
        kind=args.kind,
        base_ref=resolved_base_ref,
        head_ref=resolved_head_ref,
    )
    records = _untracked_records(repo, untracked)
    patch = _patch_bytes(
        repo,
        kind=args.kind,
        base_ref=resolved_base_ref,
        head_ref=resolved_head_ref,
        scopes=scopes,
    )
    hasher = hashlib.sha256()
    _record(hasher, "digest_version", DIGEST_VERSION.encode())
    _record(hasher, "kind", args.kind.encode())
    _record(hasher, "revision_id", revision_id.encode())
    _record(hasher, "base_ref", (resolved_base_ref or "").encode())
    _record(hasher, "head_ref", (resolved_head_ref or "").encode())
    _record(hasher, "scope_paths", json.dumps(scopes, ensure_ascii=False, separators=(",", ":")).encode())
    _record(hasher, "tracked_patch", patch)
    _record(hasher, "untracked_records", json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    digest = "sha256:" + hasher.hexdigest()
    snapshot["diff_hash"] = digest
    snapshot["snapshot_id"] = digest
    return snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--kind", choices=sorted(KINDS), required=True)
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref")
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--untracked", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    snapshot = build_snapshot(args)
    print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SnapshotError, UnicodeError, OSError) as exc:
        print(f"snapshot-digest: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
