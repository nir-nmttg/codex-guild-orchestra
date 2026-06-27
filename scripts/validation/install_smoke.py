"""installer の upgrade / compatibility smoke 検証。"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import ROOT, require


def _run_install(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/install.py"), *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def validate_install_upgrade_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "guild"
        dry_run = _run_install("--target", target, "--mode", "copy", "--dry-run")
        require(dry_run.returncode == 0, "install.py --dry-run が失敗しました: " + dry_run.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "guild"
        legacy_paths = [
            target / ".codex/agents/spark.toml",
            target / ".agents/orchestra/queue/templates/adventurer_task.yaml",
            target / ".agents/orchestra/queue/templates/inquisitor_task.yaml",
        ]
        for path in legacy_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("legacy: true\n", encoding="utf-8")

        installed = _run_install("--target", target, "--mode", "copy")
        require(installed.returncode == 0, "install.py の通常 install smoke が失敗しました: " + installed.stderr)
        remaining = [str(path.relative_to(target)) for path in legacy_paths if path.exists()]
        require(not remaining, "install.py は削除済み旧 template を prune してください: " + ", ".join(remaining))

    def run_with_mutated_source(mutation: str, mutate: object) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "template"
            target = Path(tmp) / "guild"
            shutil.copytree(ROOT / "template", source)
            mutate(source)
            result = _run_install("--target", target, "--source", source, "--mode", "copy", "--dry-run")
            require(result.returncode != 0, f"install.py は不正な source template を拒否してください: {mutation}")
            return result

    missing_advisor = run_with_mutated_source("missing advisor.toml", lambda source: (source / ".codex/agents/advisor.toml").unlink())
    require("advisor.toml" in (missing_advisor.stdout + missing_advisor.stderr), "install.py の advisor 不足拒否 message は advisor.toml を示してください。")

    def make_advisor_writable(source: Path) -> None:
        path = source / ".codex/agents/advisor.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'), encoding="utf-8")

    writable_advisor = run_with_mutated_source("advisor not read-only", make_advisor_writable)
    require("sandbox_mode" in (writable_advisor.stdout + writable_advisor.stderr), "install.py の advisor sandbox 拒否 message は sandbox_mode を示してください。")
