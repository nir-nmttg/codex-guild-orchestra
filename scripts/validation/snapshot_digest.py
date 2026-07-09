"""canonical snapshot digest の functional contract 検証。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .core import ROOT, require


SCRIPT = ROOT / "template/.agents/orchestra/scripts/snapshot_digest.py"


def _run(args: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False, env=env)


def _git(repo: Path, *args: str) -> None:
    result = _run(["git", *args], repo)
    require(result.returncode == 0, f"snapshot fixture の git {' '.join(args)} が失敗しました: {result.stderr}")


def _snapshot(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, str(SCRIPT), "--repo", str(repo), *args], repo, env=env)


def validate_snapshot_digest() -> None:
    require(SCRIPT.exists(), "template/.agents/orchestra/scripts/snapshot_digest.py が必要です。")
    script_text = SCRIPT.read_text(encoding="utf-8")
    for token in ("cgo-snapshot-v1", "--binary", "--full-index", "secret-like / PII-like path", "tracked symlink", "submodule / nested repository"):
        require(token in script_text, f"snapshot digest helper に `{token}` が必要です。")
    if shutil.which("git") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        _git(repo, "init", "--quiet")
        _git(repo, "config", "user.name", "Snapshot Test")
        _git(repo, "config", "user.email", "snapshot@example.invalid")
        (repo / "src").mkdir()
        (repo / "src/owned.txt").write_text("before\n", encoding="utf-8")
        (repo / ".gitattributes").write_text("src/owned.txt diff=unsafe\n", encoding="utf-8")
        _git(repo, "add", "src/owned.txt", ".gitattributes")
        _git(repo, "commit", "--quiet", "-m", "baseline")
        _git(repo, "config", "diff.unsafe.textconv", "command-that-must-not-run")
        _git(repo, "config", "core.fsmonitor", "command-that-must-not-run")
        _git(repo, "config", "diff.orderFile", str(Path(tmp) / "outside-order-file"))
        _git(repo, "config", "core.attributesFile", str(Path(tmp) / "outside-attributes-file"))
        _git(repo, "config", "core.excludesFile", str(Path(tmp) / "outside-excludes-file"))

        (repo / "src/owned.txt").write_text("after\n", encoding="utf-8")
        before_stage = _snapshot(repo, "--kind", "working_tree_content", "--scope", "src")
        require(before_stage.returncode == 0, f"working tree snapshot が失敗しました: {before_stage.stderr}")
        before = json.loads(before_stage.stdout)
        outside_object_env = Path(tmp) / "environment-object-store"
        outside_object_env.mkdir()
        injected_environment = dict(os.environ)
        injected_environment.update(
            {
                "GIT_OBJECT_DIRECTORY": str(outside_object_env),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(outside_object_env),
                "GIT_EXTERNAL_DIFF": "command-that-must-not-run",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.fsmonitor",
                "GIT_CONFIG_VALUE_0": "command-that-must-not-run",
                "GIT_CONFIG": str(Path(tmp) / "outside-git-config"),
                "GIT_COMMON_DIR": str(Path(tmp) / "outside-common-dir"),
                "GIT_GRAFT_FILE": str(Path(tmp) / "outside-grafts"),
                "GIT_SHALLOW_FILE": str(Path(tmp) / "outside-shallow"),
                "GIT_TRACE": str(Path(tmp) / "outside-git-trace"),
            }
        )
        fake_bin = Path(tmp) / "fake-bin"
        fake_bin.mkdir()
        fake_marker = Path(tmp) / "fake-git-executed"
        fake_git = fake_bin / "git"
        fake_git.write_text(f"#!/bin/sh\ntouch '{fake_marker}'\nexit 99\n", encoding="utf-8")
        fake_git.chmod(0o755)
        injected_environment["PATH"] = str(fake_bin) + os.pathsep + injected_environment.get("PATH", "")
        injected_env_snapshot = _snapshot(
            repo,
            "--kind",
            "working_tree_content",
            "--scope",
            "src",
            env=injected_environment,
        )
        require(injected_env_snapshot.returncode == 0, "snapshot digest はhost Git environment注入を無視してください。")
        require(not (Path(tmp) / "outside-git-trace").exists(), "snapshot digest はGIT_TRACEでrepo外へ書き込まないでください。")
        require(not fake_marker.exists(), "snapshot digest はhost PATH上の偽gitを実行しないでください。")
        _git(repo, "config", "--unset", "core.fsmonitor")
        _git(repo, "add", "src/owned.txt")
        after_stage = _snapshot(repo, "--kind", "working_tree_content", "--scope", "src")
        require(after_stage.returncode == 0, f"staged snapshot が失敗しました: {after_stage.stderr}")
        after = json.loads(after_stage.stdout)
        require(before["diff_hash"] == after["diff_hash"], "snapshot digest は stage 前後で変化させないでください。")
        _git(repo, "config", "--unset", "diff.orderFile")
        _git(repo, "config", "--unset", "core.attributesFile")
        _git(repo, "config", "--unset", "core.excludesFile")

        injected_output = Path(tmp) / "git-option-injection-output"
        option_like_ref = _snapshot(
            repo,
            "--kind",
            "working_tree_content",
            f"--base-ref=--output={injected_output}",
            "--scope",
            "src",
        )
        require(option_like_ref.returncode != 0, "snapshot digest は option-like ref を拒否してください。")
        require(not injected_output.exists(), "snapshot digest の ref を git option として実行しないでください。")

        (repo / "src/new.txt").write_text("new\n", encoding="utf-8")
        undeclared = _snapshot(repo, "--kind", "working_tree_content", "--scope", "src")
        require(undeclared.returncode != 0, "snapshot digest は scope 内の未宣言 untracked path を拒否してください。")
        (repo / "src/new.txt").unlink()

        (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
        denied = _snapshot(
            repo,
            "--kind",
            "working_tree_content",
            "--scope",
            "src",
            "--untracked",
            ".env",
        )
        require(denied.returncode != 0, "snapshot digest は secret-like untracked path を読む前に拒否してください。")

        outside = Path(tmp) / "outside"
        outside.mkdir()
        (outside / "public.txt").write_text("outside\n", encoding="utf-8")
        (repo / "link").symlink_to(outside, target_is_directory=True)
        escaped = _snapshot(
            repo,
            "--kind",
            "working_tree_content",
            "--scope",
            "src",
            "--untracked",
            "link/public.txt",
        )
        require(escaped.returncode != 0, "snapshot digest は ancestor symlink 経由の repo escape を読む前に拒否してください。")

        (repo / ".env").unlink()
        (repo / "link").unlink()
        _git(repo, "commit", "--quiet", "-m", "updated")
        revision_only = _snapshot(repo, "--kind", "revision_only")
        require(revision_only.returncode == 0, f"revision-only snapshot が失敗しました: {revision_only.stderr}")
        revision = json.loads(revision_only.stdout)
        require(revision["diff_hash"] is None and revision["snapshot_id"].startswith("sha256:"), "revision-only snapshot の identity が不正です。")

        linked = Path(tmp) / "linked-worktree"
        _git(repo, "worktree", "add", "--quiet", "--detach", str(linked), "HEAD")
        linked_snapshot = _snapshot(linked, "--kind", "revision_only")
        require(linked_snapshot.returncode == 0, f"検証可能なlinked worktree snapshotが失敗しました: {linked_snapshot.stderr}")
        linked_revision = json.loads(linked_snapshot.stdout)
        require(linked_revision["revision_id"] == revision["revision_id"], "linked worktree snapshotは同じrevisionを参照してください。")
        _git(repo, "worktree", "remove", "--force", str(linked))

        (repo / "src/link.txt").symlink_to("owned.txt")
        _git(repo, "add", "src/link.txt")
        _git(repo, "commit", "--quiet", "-m", "tracked symlink")
        (repo / "src/link.txt").unlink()
        _git(repo, "add", "-u", "src/link.txt")
        _git(repo, "commit", "--quiet", "-m", "remove tracked symlink")
        historical_symlink = _snapshot(
            repo,
            "--kind",
            "commit_range",
            "--base-ref",
            "HEAD~2",
            "--head-ref",
            "HEAD~1",
            "--scope",
            "src",
        )
        require(historical_symlink.returncode != 0, "snapshot digest はcurrent indexにないhistorical symlinkもsubject refsから拒否してください。")

        (repo / "src/base-link.txt").symlink_to("owned.txt")
        _git(repo, "add", "src/base-link.txt")
        _git(repo, "commit", "--quiet", "-m", "working base symlink")
        (repo / "src/base-link.txt").unlink()
        _git(repo, "add", "-u", "src/base-link.txt")
        deleted_base_symlink = _snapshot(repo, "--kind", "working_tree_content", "--scope", "src")
        require(deleted_base_symlink.returncode != 0, "snapshot digest はworking baseにだけ残るstaged削除済みsymlinkも拒否してください。")

        outside_pseudo_ref = Path(tmp) / "outside-fetch-head"
        current_head = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        outside_pseudo_ref.write_text(current_head + "\n", encoding="utf-8")
        (repo / ".git/FETCH_HEAD").symlink_to(outside_pseudo_ref)
        pseudo_ref = _snapshot(
            repo,
            "--kind",
            "commit_range",
            "--base-ref",
            "FETCH_HEAD",
            "--head-ref",
            "HEAD",
            "--scope",
            "src",
        )
        require(pseudo_ref.returncode != 0, "snapshot digest はpseudo-ref symlink経由でrepo外refを読まないでください。")
        (repo / ".git/FETCH_HEAD").unlink()

        outside_objects = Path(tmp) / "outside-object-store"
        (repo / ".git/objects").rename(outside_objects)
        (repo / ".git/objects").symlink_to(outside_objects, target_is_directory=True)
        external_object_store = _snapshot(repo, "--kind", "working_tree_content", "--scope", "src")
        require(external_object_store.returncode != 0, "snapshot digest は.git/objects symlink経由でrepo外objectを読まないでください。")
        (repo / ".git/objects").unlink()
        outside_objects.rename(repo / ".git/objects")

        with (repo / ".git/config").open("a", encoding="utf-8") as stream:
            stream.write("\n[include]\n\tpath = /tmp/untrusted-snapshot-config\n")
        included_config = _snapshot(repo, "--kind", "working_tree_content", "--scope", "src")
        require(included_config.returncode != 0, "snapshot digest はrepo-local Git config includeをGit起動前に拒否してください。")
