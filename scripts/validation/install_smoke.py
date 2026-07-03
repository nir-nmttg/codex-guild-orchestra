"""installer の upgrade / compatibility smoke 検証。"""

from __future__ import annotations

import importlib.util
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import ROOT, require
from .rules import LEDGER_TABLES

AGENTS_START = "<!-- codex-guild-orchestra:start -->"
AGENTS_END = "<!-- codex-guild-orchestra:end -->"
EXCLUDE_START = "# codex-guild-orchestra:start"
EXCLUDE_END = "# codex-guild-orchestra:end"
RUNTIME_SCHEMA_VERSION = "3.0"

READ_ONLY_AGENT_ROLES = (
    "advisor",
    "cartographer",
    "guildmaster",
    "inquisitor",
    "quest_sentinel",
    "party_leader",
)
EXPECTED_AGENT_FILES = {
    "adventurer.toml",
    "advisor.toml",
    "cartographer.toml",
    "courier.toml",
    "guildmaster.toml",
    "inquisitor.toml",
    "party_leader.toml",
    "quest_sentinel.toml",
}
EXPECTED_SKILL_DIRS = {
    "branch-implementation-final-review",
    "browser-research-readonly",
    "git-branch-from-session",
    "git-rename-unpushed-branch-from-diff",
    "git-split-commits-from-diff",
    "github-pull-request-from-branch",
    "github-safe-push-from-branch",
    "implementation-behavior-verification",
    "open-subrepo-in-vscode",
    "orchestra-instruction-contract-review",
    "orchestra-runtime-security-audit",
    "orchestra-validation-review",
    "pull-request-description-from-branch",
    "quest-awareness-loop",
    "repository-design-mapmaking",
    "use-guild-workflow",
}
INSTALLED_OLD_TERM_TOKENS = (
    "fa" "ble",
    "meta" "cognitive",
    "meta-" "recognition",
    "meta " "recognition",
    "meta_" "recognition",
    "メタ認" "知",
    "メタ認" "識",
    "cognitive_" "failure_memory",
)


def _load_installer_module() -> object:
    spec = importlib.util.spec_from_file_location("codex_guild_orchestra_installer", ROOT / "scripts/install.py")
    require(spec is not None and spec.loader is not None, "install.py helper を読み込めません。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLER = _load_installer_module()


def _run_install(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/install.py"), *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _installed_text_paths(target: Path) -> list[Path]:
    text_suffixes = {".json", ".md", ".py", ".sh", ".sql", ".toml", ".txt", ".yaml", ".yml"}
    return sorted(
        path
        for path in target.rglob("*")
        if path.is_file() and (path.name == "AGENTS.md" or path.suffix in text_suffixes)
    )


def _assert_installed_surface(target: Path) -> None:
    require((target / "AGENTS.md").exists(), "install.py は AGENTS.md を生成してください。")
    require((target / ".codex/config.toml").exists(), "install.py は .codex/config.toml を導入してください。")
    agent_dir = target / ".codex/agents"
    actual_agents = {path.name for path in agent_dir.glob("*.toml")}
    require(actual_agents == EXPECTED_AGENT_FILES, ".codex/agents の導入 file set が期待値と一致しません: " + ", ".join(sorted(actual_agents)))
    skill_dir = target / ".agents/skills"
    actual_skills = {path.name for path in skill_dir.iterdir() if path.is_dir()}
    require(actual_skills == EXPECTED_SKILL_DIRS, ".agents/skills の導入 directory set が期待値と一致しません: " + ", ".join(sorted(actual_skills)))
    require((skill_dir / "quest-awareness-loop/SKILL.md").exists(), "install.py は quest-awareness-loop skill を導入してください。")
    require((target / ".agents/orchestra/docs/agent-memory.md").exists(), "install.py は agent-memory runtime artifact を導入してください。")
    require((target / ".orchestra/dashboard.md").exists(), "install.py は dashboard runtime artifact を .orchestra/dashboard.md に導入してください。")
    require(not (target / ".agents/orchestra/dashboard.md").exists(), "install.py は dashboard を static .agents/orchestra へ導入しないでください。")
    database = target / ".orchestra/queue/state.sqlite"
    require(database.exists(), "install.py は .orchestra/queue/state.sqlite を初期化してください。")
    with sqlite3.connect(database) as connection:
        schema_version = connection.execute("SELECT value FROM queue_metadata WHERE key = 'schema_version'").fetchone()
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    require(schema_version is not None and schema_version[0] == RUNTIME_SCHEMA_VERSION, "install.py は runtime DB schema_version を 3.0 にしてください。")
    missing_tables = sorted(LEDGER_TABLES - tables)
    require(not missing_tables, "install.py が初期化した runtime DB に不足 table があります: " + ", ".join(missing_tables))
    for path in _installed_text_paths(target):
        text = path.read_text(encoding="utf-8").casefold()
        for token in INSTALLED_OLD_TERM_TOKENS:
            require(token not in text, f"install.py の導入結果に旧語彙 `{token}` が残っています: {path.relative_to(target)}")


def _assert_agents_block_idempotent(target: Path, expect_update_position: bool = True) -> None:
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    require(agents.count(AGENTS_START) == 1 and agents.count(AGENTS_END) == 1, "install.py は AGENTS.md 管理 marker を各 1 個だけにしてください。")
    require("既存ユーザー規約" in agents, "install.py は AGENTS.md の管理ブロック外の既存内容を保持してください。")
    require("中間の既存内容" in agents, "install.py は重複管理ブロック間の AGENTS.md 既存内容を保持してください。")
    require("末尾の既存内容" in agents, "install.py は AGENTS.md 管理ブロック後の既存内容を保持してください。")
    require(
        agents.index("既存ユーザー規約") < agents.index("中間の既存内容") < agents.index("末尾の既存内容"),
        "install.py は AGENTS.md の管理ブロック外の既存内容順序を保持してください。",
    )
    if expect_update_position:
        require(
            agents.index("既存ユーザー規約") < agents.index(AGENTS_START) < agents.index("中間の既存内容"),
            "install.py は AGENTS.md の最初の complete 管理ブロック位置で更新してください。",
        )
    else:
        require(
            agents.index("末尾の既存内容") < agents.index(AGENTS_START),
            "install.py --clean-install は pruning 後の既存内容を保持してから AGENTS.md 管理ブロックを再導入してください。",
        )


def _assert_git_exclude_block_idempotent(target: Path, expect_update_position: bool = True) -> None:
    exclude = (target / ".git/info/exclude").read_text(encoding="utf-8")
    require(exclude.count(EXCLUDE_START) == 1 and exclude.count(EXCLUDE_END) == 1, "install.py は .git/info/exclude 管理 marker を各 1 個だけにしてください。")
    require("existing-before" in exclude, "install.py は .git/info/exclude の管理ブロック前の既存内容を保持してください。")
    require("existing-between" in exclude, "install.py は .git/info/exclude の重複管理ブロック間の既存内容を保持してください。")
    require("existing-after" in exclude, "install.py は .git/info/exclude の管理ブロック後の既存内容を保持してください。")
    require(
        exclude.index("existing-before") < exclude.index("existing-between") < exclude.index("existing-after"),
        "install.py は .git/info/exclude の管理ブロック外の既存内容順序を保持してください。",
    )
    if expect_update_position:
        require(
            exclude.index("existing-before") < exclude.index(EXCLUDE_START) < exclude.index("existing-between"),
            "install.py は .git/info/exclude の最初の complete 管理ブロック位置で更新してください。",
        )
    else:
        require(
            exclude.index("existing-after") < exclude.index(EXCLUDE_START),
            "install.py --clean-install は pruning 後の既存内容を保持してから .git/info/exclude 管理ブロックを再導入してください。",
        )


def _assert_token_order(text: str, tokens: tuple[str, ...], label: str) -> None:
    cursor = -1
    for token in tokens:
        index = text.find(token, cursor + 1)
        require(index != -1, f"{label} に `{token}` が見つかりません。")
        require(index > cursor, f"{label} の `{token}` の順序が不正です。")
        cursor = index


def _assert_managed_block_helper_matrix() -> None:
    block = f"{AGENTS_START}\n新しい管理ブロック\n{AGENTS_END}\n"
    cases = (
        (
            "空ファイル",
            "",
            ("新しい管理ブロック",),
            (),
        ),
        (
            "通常テキストのみ",
            "before\n",
            ("before", "新しい管理ブロック"),
            ("before",),
        ),
        (
            "孤立 start のみ",
            f"before\n{AGENTS_START}\norphan body\n",
            ("before", "orphan body", "新しい管理ブロック"),
            ("before", "orphan body"),
        ),
        (
            "孤立 end のみ",
            f"{AGENTS_END}\nbefore\nafter\n",
            ("before", "after", "新しい管理ブロック"),
            ("before", "after"),
        ),
        (
            "単一 complete block",
            f"before\n{AGENTS_START}\nold managed\n{AGENTS_END}\nafter\n",
            ("before", "新しい管理ブロック", "after"),
            ("before", "after"),
        ),
        (
            "中間テキスト付き重複 complete block",
            f"before\n{AGENTS_START}\nold managed 1\n{AGENTS_END}\nbetween\n{AGENTS_START}\nold managed 2\n{AGENTS_END}\nafter\n",
            ("before", "新しい管理ブロック", "between", "after"),
            ("before", "between", "after"),
        ),
        (
            "隣接 complete block",
            f"before\n{AGENTS_START}\nold managed 1\n{AGENTS_END}\n{AGENTS_START}\nold managed 2\n{AGENTS_END}\nafter\n",
            ("before", "新しい管理ブロック", "after"),
            ("before", "after"),
        ),
        (
            "入れ子 duplicate marker",
            f"before\n{AGENTS_START}\n{AGENTS_START}\nold nested\n{AGENTS_END}\n{AGENTS_END}\nafter\n",
            ("before", "新しい管理ブロック", "after"),
            ("before", "after"),
        ),
        (
            "先頭孤立 end と末尾孤立 start",
            f"{AGENTS_END}\nbefore\n{AGENTS_START}\nold managed\n{AGENTS_END}\nafter\n{AGENTS_START}\n",
            ("before", "新しい管理ブロック", "after"),
            ("before", "after"),
        ),
    )
    for label, text, replace_tokens, prune_tokens in cases:
        replaced = INSTALLER.replace_or_append_block(text, block, AGENTS_START, AGENTS_END)
        require(replaced.count(AGENTS_START) == 1 and replaced.count(AGENTS_END) == 1, f"{label}: replace は marker を 1 組にしてください。")
        require("old managed" not in replaced and "old nested" not in replaced, f"{label}: replace は古い管理ブロック本文を残さないでください。")
        _assert_token_order(replaced, replace_tokens, f"{label}: replace")

        pruned = INSTALLER.remove_block(text, AGENTS_START, AGENTS_END)
        require(AGENTS_START not in pruned and AGENTS_END not in pruned, f"{label}: prune は marker を残さないでください。")
        require("old managed" not in pruned and "old nested" not in pruned, f"{label}: prune は古い管理ブロック本文を残さないでください。")
        if prune_tokens:
            _assert_token_order(pruned, prune_tokens, f"{label}: prune")
        else:
            require(pruned == "", f"{label}: prune 後は空にしてください。")


def _write_duplicate_agents(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "AGENTS.md").write_text(
        f"{AGENTS_END}\n"
        "既存ユーザー規約\n\n"
        f"{AGENTS_START}\n"
        "古い complete block 1\n"
        f"{AGENTS_END}\n"
        "中間の既存内容\n"
        f"{AGENTS_START}\n"
        f"{AGENTS_START}\n"
        "古い二重化ブロック\n"
        f"{AGENTS_END}\n"
        f"{AGENTS_END}\n"
        "末尾の既存内容\n"
        f"{AGENTS_START}\n",
        encoding="utf-8",
    )


def _write_duplicate_git_exclude(target: Path) -> None:
    exclude = target / ".git/info/exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(
        f"{EXCLUDE_END}\n"
        "existing-before\n"
        f"{EXCLUDE_START}\n"
        "old exclude block 1\n"
        f"{EXCLUDE_END}\n"
        "existing-between\n"
        f"{EXCLUDE_START}\n"
        f"{EXCLUDE_START}\n"
        "old exclude block 2\n"
        f"{EXCLUDE_END}\n"
        f"{EXCLUDE_END}\n"
        "existing-after\n"
        f"{EXCLUDE_START}\n",
        encoding="utf-8",
    )


def validate_install_upgrade_smoke() -> None:
    _assert_managed_block_helper_matrix()

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
        _write_duplicate_agents(target)
        _write_duplicate_git_exclude(target)
        legacy_paths = [
            target / ".codex/agents/spark.toml",
            target / ".codex/agents/" / ("meta" "cognitive_controller.toml"),
            target / ".agents/orchestra/queue/templates/adventurer_task.yaml",
            target / ".agents/orchestra/queue/templates/inquisitor_task.yaml",
            target / ".agents/skills" / ("meta" "cognitive-task-loop") / "SKILL.md",
        ]
        for path in legacy_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("legacy: true\n", encoding="utf-8")

        installed = _run_install("--target", target, "--mode", "copy")
        require(installed.returncode == 0, "install.py の通常 install smoke が失敗しました: " + installed.stderr)
        _assert_installed_surface(target)
        _assert_agents_block_idempotent(target)
        _assert_git_exclude_block_idempotent(target)
        reinstalled = _run_install("--target", target, "--mode", "copy")
        require(reinstalled.returncode == 0, "install.py の再 install smoke が失敗しました: " + reinstalled.stderr)
        _assert_installed_surface(target)
        _assert_agents_block_idempotent(target)
        _assert_git_exclude_block_idempotent(target)
        remaining = [str(path.relative_to(target)) for path in legacy_paths if path.exists()]
        require(not remaining, "install.py は削除済み旧 template を prune してください: " + ", ".join(remaining))

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "guild"
        _write_duplicate_agents(target)
        _write_duplicate_git_exclude(target)
        existing_database = target / ".orchestra/queue/state.sqlite"
        existing_database.parent.mkdir(parents=True, exist_ok=True)
        existing_database.write_bytes(b"legacy runtime state")
        (target / ".orchestra/dashboard.md").write_text("legacy dashboard\n", encoding="utf-8")

        clean_dry_run = _run_install("--target", target, "--mode", "copy", "--clean-install", "--dry-run")
        clean_dry_run_output = clean_dry_run.stdout + clean_dry_run.stderr
        require(clean_dry_run.returncode == 0, "install.py --clean-install --dry-run が失敗しました: " + clean_dry_run.stderr)
        require("remove" in clean_dry_run_output and ".orchestra" in clean_dry_run_output, "install.py --clean-install --dry-run は runtime state の削除計画を表示してください。")
        require("init sqlite" in clean_dry_run_output and "state.sqlite" in clean_dry_run_output, "install.py --clean-install --dry-run は runtime DB 再初期化計画を表示してください。")
        require("既存状態を保持" not in clean_dry_run_output, "install.py --clean-install --dry-run は既存 runtime state を保持すると表示しないでください。")

        clean_installed = _run_install("--target", target, "--mode", "copy", "--clean-install")
        require(clean_installed.returncode == 0, "install.py --clean-install smoke が失敗しました: " + clean_installed.stderr)
        _assert_installed_surface(target)
        _assert_agents_block_idempotent(target, expect_update_position=False)
        _assert_git_exclude_block_idempotent(target, expect_update_position=False)

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "guild"
        installed = _run_install("--target", target, "--mode", "copy")
        require(installed.returncode == 0, "install.py の reset-runtime 事前 install が失敗しました: " + installed.stderr)
        stale_queue_file = target / ".orchestra/queue/stale.txt"
        stale_queue_file.write_text("stale runtime state\n", encoding="utf-8")
        dashboard = target / ".orchestra/dashboard.md"
        dashboard.write_text("edited dashboard\n", encoding="utf-8")

        reset_dry_run = _run_install("--target", target, "--mode", "copy", "--reset-runtime", "--dry-run")
        reset_dry_run_output = reset_dry_run.stdout + reset_dry_run.stderr
        require(reset_dry_run.returncode == 0, "install.py --reset-runtime --dry-run が失敗しました: " + reset_dry_run.stderr)
        require("remove" in reset_dry_run_output and ".orchestra/queue" in reset_dry_run_output, "install.py --reset-runtime --dry-run は runtime queue の削除計画を表示してください。")
        require("remove" in reset_dry_run_output and "dashboard.md" in reset_dry_run_output, "install.py --reset-runtime --dry-run は dashboard の削除計画を表示してください。")
        require("init sqlite" in reset_dry_run_output and "state.sqlite" in reset_dry_run_output, "install.py --reset-runtime --dry-run は runtime DB 再初期化計画を表示してください。")
        require(stale_queue_file.exists(), "install.py --reset-runtime --dry-run は runtime queue を削除しないでください。")
        require(dashboard.read_text(encoding="utf-8") == "edited dashboard\n", "install.py --reset-runtime --dry-run は dashboard を変更しないでください。")

        reset_without_backup = _run_install("--target", target, "--mode", "copy", "--reset-runtime")
        reset_without_backup_output = reset_without_backup.stdout + reset_without_backup.stderr
        require(reset_without_backup.returncode != 0, "install.py --reset-runtime は backup なしの非 dry-run を拒否してください。")
        require("--backup" in reset_without_backup_output and "--allow-reset-runtime-without-backup" in reset_without_backup_output, "install.py --reset-runtime の拒否 message は backup と escape flag を示してください。")
        require(stale_queue_file.exists(), "install.py --reset-runtime の拒否時は runtime queue を削除しないでください。")

        reset_with_backup = _run_install("--target", target, "--mode", "copy", "--reset-runtime", "--backup")
        require(reset_with_backup.returncode == 0, "install.py --reset-runtime --backup smoke が失敗しました: " + reset_with_backup.stderr)
        _assert_installed_surface(target)
        require(not stale_queue_file.exists(), "install.py --reset-runtime --backup は古い runtime queue 内容を削除してください。")
        backup_root = target / ".codex-guild-orchestra-backups"
        backups = sorted(path for path in backup_root.iterdir() if path.is_dir())
        require(backups and any((backup / ".orchestra/queue/stale.txt").exists() for backup in backups), "install.py --reset-runtime --backup は既存 runtime state を退避してください。")

        stale_queue_file = target / ".orchestra/queue/stale.txt"
        stale_queue_file.write_text("stale runtime state again\n", encoding="utf-8")
        reset_with_escape = _run_install("--target", target, "--mode", "copy", "--reset-runtime", "--allow-reset-runtime-without-backup")
        require(reset_with_escape.returncode == 0, "install.py --reset-runtime --allow-reset-runtime-without-backup smoke が失敗しました: " + reset_with_escape.stderr)
        _assert_installed_surface(target)
        require(not stale_queue_file.exists(), "install.py --reset-runtime --allow-reset-runtime-without-backup は古い runtime queue 内容を削除してください。")

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

    missing_controller = run_with_mutated_source("missing quest_sentinel.toml", lambda source: (source / ".codex/agents/quest_sentinel.toml").unlink())
    require("quest_sentinel.toml" in (missing_controller.stdout + missing_controller.stderr), "install.py の quest_sentinel 不足拒否 message は quest_sentinel.toml を示してください。")

    missing_quest_awareness_skill = run_with_mutated_source("missing quest-awareness-loop skill", lambda source: shutil.rmtree(source / ".agents/skills/quest-awareness-loop"))
    require("quest-awareness-loop" in (missing_quest_awareness_skill.stdout + missing_quest_awareness_skill.stderr), "install.py の quest-awareness-loop 不足拒否 message は skill 名を示してください。")

    missing_runtime_doc = run_with_mutated_source("missing runtime memory doc", lambda source: (source / ".agents/orchestra/docs/agent-memory.md").unlink())
    require("agent-memory.md" in (missing_runtime_doc.stdout + missing_runtime_doc.stderr), "install.py の runtime docs 不足拒否 message は agent-memory.md を示してください。")

    missing_dashboard = run_with_mutated_source("missing dashboard", lambda source: (source / ".agents/orchestra/dashboard.md").unlink())
    require("dashboard.md" in (missing_dashboard.stdout + missing_dashboard.stderr), "install.py の dashboard 不足拒否 message は dashboard.md を示してください。")

    missing_queue_schema = run_with_mutated_source("missing queue schema", lambda source: (source / ".agents/orchestra/scripts/queue_schema.sql").unlink())
    require("queue_schema.sql" in (missing_queue_schema.stdout + missing_queue_schema.stderr), "install.py の queue schema 不足拒否 message は queue_schema.sql を示してください。")

    missing_stop_hook = run_with_mutated_source("missing stop hook", lambda source: (source / ".codex/hooks/stop_quality_gate.sh").unlink())
    require("stop_quality_gate.sh" in (missing_stop_hook.stdout + missing_stop_hook.stderr), "install.py の hook 不足拒否 message は stop_quality_gate.sh を示してください。")

    missing_queue_template = run_with_mutated_source("missing queue template", lambda source: (source / ".agents/orchestra/queue/templates/inquisitor_trial.yaml").unlink())
    require("inquisitor_trial.yaml" in (missing_queue_template.stdout + missing_queue_template.stderr), "install.py の queue template 不足拒否 message は inquisitor_trial.yaml を示してください。")

    missing_sentinel_assignment = run_with_mutated_source("missing quest_sentinel assignment template", lambda source: (source / ".agents/orchestra/queue/templates/quest_sentinel_assignment.yaml").unlink())
    require("quest_sentinel_assignment.yaml" in (missing_sentinel_assignment.stdout + missing_sentinel_assignment.stderr), "install.py の quest_sentinel assignment template 不足拒否 message は quest_sentinel_assignment.yaml を示してください。")

    missing_inbox_script = run_with_mutated_source("missing inbox helper", lambda source: (source / ".agents/orchestra/scripts/inbox_write.sh").unlink())
    require("inbox_write.sh" in (missing_inbox_script.stdout + missing_inbox_script.stderr), "install.py の inbox helper 不足拒否 message は inbox_write.sh を示してください。")

    for role in READ_ONLY_AGENT_ROLES:
        def make_role_writable(source: Path, role: str = role) -> None:
            path = source / ".codex" / "agents" / f"{role}.toml"
            path.write_text(path.read_text(encoding="utf-8").replace('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'), encoding="utf-8")

        writable_role = run_with_mutated_source(f"{role} not read-only", make_role_writable)
        output = writable_role.stdout + writable_role.stderr
        require("sandbox_mode" in output and f"{role}.toml" in output, f"install.py の {role} sandbox 拒否 message は sandbox_mode と role file を示してください。")

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
