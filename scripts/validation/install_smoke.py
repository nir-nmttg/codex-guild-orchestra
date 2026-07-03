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
        require(not target.exists(), "install.py --dry-run は target に書き込まないでください。")

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "template"
        target = Path(tmp) / "guild"
        shutil.copytree(ROOT / "template", source)
        non_default = _run_install("--target", target, "--source", source, "--mode", "copy", "--dry-run")
        require(non_default.returncode != 0 and "--allow-non-default-source" in (non_default.stdout + non_default.stderr), "install.py は非 default source を明示許可なしで拒否してください。")

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
            result = _run_install("--target", target, "--source", source, "--allow-non-default-source", "--mode", "copy", "--dry-run")
            require(result.returncode != 0, f"install.py は不正な source template を拒否してください: {mutation}")
            return result

    missing_advisor = run_with_mutated_source("missing advisor.toml", lambda source: (source / ".codex/agents/advisor.toml").unlink())
    require("advisor.toml" in (missing_advisor.stdout + missing_advisor.stderr), "install.py の advisor 不足拒否 message は advisor.toml を示してください。")

    def make_advisor_writable(source: Path) -> None:
        path = source / ".codex/agents/advisor.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'), encoding="utf-8")

    writable_advisor = run_with_mutated_source("advisor not read-only", make_advisor_writable)
    require("sandbox_mode" in (writable_advisor.stdout + writable_advisor.stderr), "install.py の advisor sandbox 拒否 message は sandbox_mode を示してください。")

    def add_source_symlink(source: Path) -> None:
        (source / ".codex" / "secrets").symlink_to(source / ".codex" / "config.toml")

    source_symlink = run_with_mutated_source("source symlink", add_source_symlink)
    require("symlink" in (source_symlink.stdout + source_symlink.stderr), "install.py は source symlink を拒否してください。")

    def add_mcp_path(source: Path) -> None:
        path = source / ".mcp" / "server.json"
        path.parent.mkdir()
        path.write_text("{}", encoding="utf-8")

    mcp_path = run_with_mutated_source("unexpected mcp path", add_mcp_path)
    require(".mcp" in (mcp_path.stdout + mcp_path.stderr), "install.py は source 内の MCP path を拒否してください。")

    def add_git_path(source: Path) -> None:
        path = source / ".git" / "config"
        path.parent.mkdir()
        path.write_text("[core]\n", encoding="utf-8")

    git_path = run_with_mutated_source("unexpected git path", add_git_path)
    require(".git" in (git_path.stdout + git_path.stderr), "install.py は source 内の .git path を拒否してください。")

    def add_runtime_state(source: Path) -> None:
        path = source / ".orchestra" / "queue" / "state.sqlite"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"sqlite")

    runtime_state = run_with_mutated_source("unexpected runtime state", add_runtime_state)
    require(".orchestra" in (runtime_state.stdout + runtime_state.stderr), "install.py は source 内の runtime state を拒否してください。")

    def add_repositories_path(source: Path) -> None:
        path = source / "repositories" / "demo" / "README.md"
        path.parent.mkdir(parents=True)
        path.write_text("# demo\n", encoding="utf-8")

    repositories_path = run_with_mutated_source("unexpected repositories path", add_repositories_path)
    require("repositories" in (repositories_path.stdout + repositories_path.stderr), "install.py は source 内の repositories/ を拒否してください。")

    def enable_source_network(source: Path) -> None:
        path = source / ".codex" / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("network_access = false", "network_access = true"), encoding="utf-8")

    source_network = run_with_mutated_source("source network enabled", enable_source_network)
    require("network_access" in (source_network.stdout + source_network.stderr), "install.py は source config の network_access=true を拒否してください。")

    def add_mcp_server_config(source: Path) -> None:
        path = source / ".codex" / "config.toml"
        path.write_text(path.read_text(encoding="utf-8") + "\n[mcp_servers.example]\ncommand = \"example\"\n", encoding="utf-8")

    mcp_server_config = run_with_mutated_source("source mcp server config", add_mcp_server_config)
    require("MCP" in (mcp_server_config.stdout + mcp_server_config.stderr), "install.py は source config の MCP server を拒否してください。")

    def add_api_key_path(source: Path) -> None:
        path = source / ".codex" / "api_key.txt"
        path.write_text("redacted\n", encoding="utf-8")

    api_key_path = run_with_mutated_source("unexpected api key path", add_api_key_path)
    require("key" in (api_key_path.stdout + api_key_path.stderr), "install.py は source 内の key path を拒否してください。")

    def add_auth_path(source: Path) -> None:
        path = source / ".codex" / "auth.json"
        path.write_text("{}", encoding="utf-8")

    auth_path = run_with_mutated_source("unexpected auth path", add_auth_path)
    require("auth" in (auth_path.stdout + auth_path.stderr), "install.py は source 内の auth path を拒否してください。")

    def add_ssh_key_path(source: Path) -> None:
        path = source / ".codex" / ".ssh" / "id_ed25519"
        path.parent.mkdir()
        path.write_text("redacted\n", encoding="utf-8")

    ssh_key_path = run_with_mutated_source("unexpected ssh key path", add_ssh_key_path)
    require(".ssh" in (ssh_key_path.stdout + ssh_key_path.stderr), "install.py は source 内の SSH key path を拒否してください。")

    def add_pem_path(source: Path) -> None:
        path = source / ".codex" / "private.pem"
        path.write_text("redacted\n", encoding="utf-8")

    pem_path = run_with_mutated_source("unexpected pem path", add_pem_path)
    require("pem" in (pem_path.stdout + pem_path.stderr), "install.py は source 内の pem path を拒否してください。")
