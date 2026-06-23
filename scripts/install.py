#!/usr/bin/env python3
"""ギルド規約ルートへ最小ランタイムを導入するスクリプト。"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Any, Iterable

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'template'
AGENTS_START = '<!-- codex-guild-orchestra:start -->'
AGENTS_END = '<!-- codex-guild-orchestra:end -->'
EXCLUDE_START = '# codex-guild-orchestra:start'
EXCLUDE_END = '# codex-guild-orchestra:end'
BACKUP_REL_PATHS = [
    'AGENTS.md',
    '.git/info/exclude',
    '.agents',
    '.codex',
    '.orchestra',
]
SQLITE_STATE_REL_PATH = Path('.orchestra/queue/state.sqlite')
RUNTIME_SCHEMA_VERSION = '3.0'
QUEST_RANKS = {'mapmaking', 'errand', 'solo_quest', 'party_quest', 'guild_quest'}
LEGACY_QUEST_RANKS = {'campaign'}
REQUIRED_RUNTIME_TABLES = {
    'queue_metadata',
    'events',
    'quests',
    'requests',
    'commands',
    'assignments',
    'reports',
    'trials',
    'inbox_messages',
}
REQUIRED_RUNTIME_COLUMNS = {
    'queue_metadata': {'key', 'value', 'updated_at'},
    'events': {
        'event_id',
        'timestamp',
        'actor',
        'event_type',
        'entity_type',
        'entity_id',
        'entity_json',
        'operation',
        'workflow_id',
        'structured_data_usage_json',
        'payload_json',
        'event_safety_json',
        'inserted_at',
    },
    'quests': {'quest_id', 'workflow_id', 'rank', 'status', 'payload_json', 'updated_at'},
    'requests': {'request_id', 'quest_id', 'workflow_id', 'status', 'payload_json', 'updated_at'},
    'commands': {'command_id', 'quest_id', 'workflow_id', 'status', 'payload_json', 'updated_at'},
    'assignments': {'assignment_id', 'parent_id', 'worker_id', 'kind', 'workflow_id', 'status', 'payload_json', 'updated_at'},
    'reports': {'report_id', 'worker_id', 'workflow_id', 'decision', 'status', 'payload_json', 'updated_at'},
    'trials': {'trial_id', 'quest_id', 'workflow_id', 'depth', 'status', 'payload_json', 'updated_at'},
    'inbox_messages': {'message_id', 'recipient', 'workflow_id', 'status', 'payload_json', 'created_at'},
}
LEGACY_RUNTIME_TABLES = {'tickets'}
LEGACY_RUNTIME_COLUMNS = {
    'assignments': {'task_id'},
}
RUNTIME_JSON_COLUMNS = {
    'events': ('entity_json', 'structured_data_usage_json', 'payload_json', 'event_safety_json'),
    'quests': ('payload_json',),
    'requests': ('payload_json',),
    'commands': ('payload_json',),
    'assignments': ('payload_json',),
    'reports': ('payload_json',),
    'trials': ('payload_json',),
    'inbox_messages': ('payload_json',),
}
LEGACY_RUNTIME_JSON_KEYS = {
    'safety_checks',
    'requires_human_confirmation',
    'target_path',
    'scale_selected',
    'risk_dimensions',
    'edit_scope',
    'read_scope',
    'quality_profile',
    'review_task',
    'review_assignment',
    'task_id',
    'scout_plan',
    'scout_usage',
    'scout_calls',
    'scout_policy',
    'spark_request',
}
RETIRED_AGENT_VALUES = {'spark', 'scout'}
REPOSITORIES_REL_PATH = Path('repositories')
ORCHESTRA_SKILL_OWNER = 'codex-guild-orchestra'
REMOVED_TEMPLATE_REL_PATHS = [
    Path('.codex/agents/spark.toml'),
    Path('.agents/orchestra/queue/templates/adventurer_task.yaml'),
    Path('.agents/orchestra/queue/templates/inquisitor_task.yaml'),
]
ADVISOR_DEVELOPER_INSTRUCTION_TOKENS = (
    'terminal worker',
    '追加 subagent',
    '実装',
    '採否',
    'Ledger',
    'confidence-based',
    'confidence delta',
    'owner が根拠確認',
)


class JapaneseArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return (
            super()
            .format_help()
            .replace('usage:', '使い方:')
            .replace('optional arguments:', 'オプション:')
            .replace('options:', 'オプション:')
        )

    def format_usage(self) -> str:
        return super().format_usage().replace('usage:', '使い方:')


def parse_args() -> argparse.Namespace:
    parser = JapaneseArgumentParser(
        description='ギルド規約ルートへ最小ランタイムを導入し、直下に repositories/ を用意します。',
        add_help=False,
    )
    parser.add_argument('-h', '--help', action='help', help='このヘルプを表示して終了します。')
    parser.add_argument('--target', required=True, help='導入先のギルド規約ルート。子リポジトリではなく、repositories/ の親を指定します。')
    parser.add_argument('--source', default=str(DEFAULT_SOURCE), help='コピー元の template ディレクトリ。')
    parser.add_argument('--mode', default='copy', choices=['copy'], help='導入モード。現在は copy のみ。')
    parser.add_argument('--dry-run', action='store_true', help='変更を加えず、予定だけ表示します。')
    parser.add_argument('--clean-install', action='store_true', help='ギルド規約ルートの導入済みランタイムを片付けてから再導入します。repositories/ 配下の repo は移動も削除もしません。')
    parser.add_argument('--backup', action='store_true', help='導入前に既存導入物を退避します。')
    parser.add_argument('--allow-reset-runtime-without-backup', action='store_true', help='非推奨の逃げ道です。動的状態をバックアップなしで初期化する時だけ指定します。')
    parser.add_argument('--reset-runtime', action='store_true', help='Ledger と dashboard の状態も初期値へ戻します。')
    parser.add_argument('--no-git-exclude', action='store_true', help='`.git/info/exclude` を更新しません。')
    return parser.parse_args()


def log(message: str) -> None:
    print(message)


def ensure_directory(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def map_template_path(rel_path: Path) -> Path:
    posix = rel_path.as_posix()
    if posix == '.agents/orchestra/dashboard.md':
        return Path('.orchestra/dashboard.md')
    return rel_path


def is_runtime_state_file(rel_path: Path) -> bool:
    posix = map_template_path(rel_path).as_posix()
    return posix == '.orchestra/dashboard.md'


def copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    log(f'copy {src} -> {dst}')
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(path: Path, content: str, dry_run: bool) -> None:
    log(f'write {path}')
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def remove_path(path: Path, dry_run: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    log(f'remove {path}')
    if dry_run:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def read_skill_owner(skill_path: Path) -> str | None:
    if not skill_path.exists() or not skill_path.is_file():
        return None
    try:
        text = skill_path.read_text(encoding='utf-8')
    except OSError:
        return None
    if not text.startswith('---\n'):
        return None
    end_marker = text.find('\n---\n', 4)
    if end_marker == -1:
        return None
    frontmatter = text[4:end_marker]
    if yaml is not None:
        try:
            metadata = yaml.safe_load(frontmatter)
        except yaml.YAMLError:
            metadata = None
        if isinstance(metadata, dict):
            owner = metadata.get('owner')
            return owner if isinstance(owner, str) else None
    for line in frontmatter.splitlines():
        key, separator, value = line.partition(':')
        if separator and key.strip() == 'owner':
            return value.strip().strip('"\'')
    return None


def clean_owner_scoped_skills(target_root: Path, dry_run: bool) -> None:
    skills_root = target_root / '.agents' / 'skills'
    if not skills_root.exists() or not skills_root.is_dir():
        return
    for child in sorted(skills_root.iterdir()):
        skill_path = child / 'SKILL.md' if child.is_dir() else child
        owner = read_skill_owner(skill_path)
        if owner == ORCHESTRA_SKILL_OWNER:
            remove_path(child, dry_run)


def replace_or_append_block(text: str, block: str, start_marker: str, end_marker: str) -> str:
    if start_marker in text and end_marker in text:
        before, rest = text.split(start_marker, 1)
        _middle, after = rest.split(end_marker, 1)
        before = before.rstrip('\n')
        after = after.lstrip('\n')
        parts = []
        if before:
            parts.append(before)
        parts.append(block.rstrip('\n'))
        if after:
            parts.append(after)
        return '\n\n'.join(parts).rstrip() + '\n'

    stripped = text.rstrip()
    if stripped:
        return stripped + '\n\n' + block.rstrip('\n') + '\n'
    return block.rstrip('\n') + '\n'


def remove_block(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    before, rest = text.split(start_marker, 1)
    _middle, after = rest.split(end_marker, 1)
    before = before.rstrip('\n')
    after = after.lstrip('\n')
    if before and after:
        return before + '\n\n' + after.rstrip() + '\n'
    if before:
        return before.rstrip() + '\n'
    if after:
        return after.rstrip() + '\n'
    return ''


def upsert_text_block(path: Path, block: str, start_marker: str, end_marker: str, dry_run: bool) -> None:
    current = path.read_text(encoding='utf-8') if path.exists() else ''
    updated = replace_or_append_block(current, block, start_marker, end_marker)
    if updated != current:
        write_text(path, updated, dry_run)


def prune_text_block(path: Path, start_marker: str, end_marker: str, dry_run: bool) -> None:
    if not path.exists():
        return
    current = path.read_text(encoding='utf-8')
    updated = remove_block(current, start_marker, end_marker)
    if updated != current:
        write_text(path, updated, dry_run)


def backup_existing(target_root: Path, dry_run: bool) -> None:
    candidates = [target_root / rel for rel in BACKUP_REL_PATHS if (target_root / rel).exists()]
    if not candidates:
        return

    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup_root = target_root / '.codex-guild-orchestra-backups' / stamp
    for path in candidates:
        destination = backup_root / path.relative_to(target_root)
        log(f'backup {path} -> {destination}')
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)


def clean_install_target(target_root: Path, prune_git_exclude: bool, dry_run: bool) -> None:
    remove_path(target_root / '.agents' / 'orchestra', dry_run)
    clean_owner_scoped_skills(target_root, dry_run)
    remove_path(target_root / '.codex', dry_run)
    remove_path(target_root / '.orchestra', dry_run)
    prune_text_block(target_root / 'AGENTS.md', AGENTS_START, AGENTS_END, dry_run)
    if prune_git_exclude:
        prune_text_block(target_root / '.git' / 'info' / 'exclude', EXCLUDE_START, EXCLUDE_END, dry_run)


def reset_runtime_state(target_root: Path, dry_run: bool) -> None:
    remove_path(target_root / '.orchestra' / 'queue', dry_run)
    remove_path(target_root / '.orchestra' / 'dashboard.md', dry_run)


def runtime_schema_incompatibility_message(database: Path, detail: str) -> str:
    return (
        f'既存 runtime DB を v{RUNTIME_SCHEMA_VERSION} の runtime contract と確認できません: {database} ({detail})\n'
        '2 系以前、v3 metadata だけで物理 schema が一致しない、または旧 runtime 値を含む `state.sqlite` は保持更新できません。'
        '既存状態を保全して初期化する場合は `--backup --reset-runtime`、'
        '導入物全体を入れ直す場合は `--clean-install` を使ってください。'
    )


def read_runtime_schema_version(database: Path) -> str | None:
    try:
        with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
            row = connection.execute(
                "SELECT value FROM queue_metadata WHERE key = 'schema_version'"
            ).fetchone()
    except (OSError, sqlite3.DatabaseError) as exc:
        raise SystemExit(runtime_schema_incompatibility_message(database, str(exc))) from exc
    if row is None or row[0] is None:
        return None
    return str(row[0])


def collect_runtime_schema_errors(connection: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    legacy_tables = sorted(LEGACY_RUNTIME_TABLES & tables)
    if legacy_tables:
        errors.append('旧 table が残っています: ' + ', '.join(legacy_tables))
    missing_tables = sorted(REQUIRED_RUNTIME_TABLES - tables)
    if missing_tables:
        errors.append('不足 table: ' + ', '.join(missing_tables))
    for table, required_columns in REQUIRED_RUNTIME_COLUMNS.items():
        if table not in tables:
            continue
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            errors.append(f'{table} の不足 column: ' + ', '.join(missing_columns))
        legacy_columns = sorted(LEGACY_RUNTIME_COLUMNS.get(table, set()) & columns)
        if legacy_columns:
            errors.append(f'{table} の旧 column: ' + ', '.join(legacy_columns))
    return errors


def iter_runtime_json_keys(value: Any, path: str = '$') -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f'{path}.{key}'
            findings.append((child_path, key))
            findings.extend(iter_runtime_json_keys(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_runtime_json_keys(item, f'{path}[{index}]'))
    return findings


def iter_runtime_json_values(value: Any, path: str = '$') -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, dict):
        for key, item in value.items():
            findings.extend(iter_runtime_json_values(item, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(iter_runtime_json_values(item, f'{path}[{index}]'))
    return findings


def collect_runtime_json_value_errors(parsed: Any, label: str) -> list[str]:
    errors: list[str] = []
    for json_path, key in iter_runtime_json_keys(parsed):
        if key in LEGACY_RUNTIME_JSON_KEYS or key in RETIRED_AGENT_VALUES:
            errors.append(f'{label}{json_path[1:]}: 廃止済み key `{key}` が残っています')
    for json_path, item in iter_runtime_json_values(parsed):
        if isinstance(item, str) and item in RETIRED_AGENT_VALUES:
            errors.append(f'{label}{json_path[1:]}: 廃止済み agent 値 `{item}` が残っています')
    return errors


def collect_runtime_value_errors(connection: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    rows = connection.execute("SELECT DISTINCT rank FROM quests WHERE rank IS NOT NULL").fetchall()
    for row in rows:
        rank = row[0]
        if rank in QUEST_RANKS:
            continue
        if rank in LEGACY_QUEST_RANKS:
            errors.append(f'旧 Quest Rank が残っています: {rank} -> guild_quest')
        else:
            errors.append(f'未定義 Quest Rank が残っています: {rank}')
    for table, columns in RUNTIME_JSON_COLUMNS.items():
        rows = connection.execute(f'SELECT rowid, {", ".join(columns)} FROM {table}').fetchall()
        for row in rows:
            rowid = row[0]
            for index, column in enumerate(columns, start=1):
                raw = row[index]
                try:
                    parsed = json.loads(raw)
                except (TypeError, json.JSONDecodeError) as exc:
                    errors.append(f'{table}[rowid={rowid}].{column}: JSON を読めません: {exc}')
                    continue
                errors.extend(collect_runtime_json_value_errors(parsed, f'{table}[rowid={rowid}].{column}'))
    retired_agent_column_checks = (
        ('events', 'event_id', 'actor'),
        ('assignments', 'assignment_id', 'worker_id'),
        ('reports', 'report_id', 'worker_id'),
        ('inbox_messages', 'message_id', 'recipient'),
    )
    for table, id_column, value_column in retired_agent_column_checks:
        rows = connection.execute(f'SELECT {id_column}, {value_column} FROM {table}').fetchall()
        for row in rows:
            value = row[1]
            if isinstance(value, str) and value in RETIRED_AGENT_VALUES:
                errors.append(f'{table}[{row[0]}].{value_column}: 廃止済み agent 値 `{value}` が残っています')
    return errors


def validate_runtime_physical_schema(database: Path) -> None:
    try:
        with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
            errors = collect_runtime_schema_errors(connection)
            if not errors:
                errors.extend(collect_runtime_value_errors(connection))
    except (OSError, sqlite3.DatabaseError) as exc:
        raise SystemExit(runtime_schema_incompatibility_message(database, str(exc))) from exc
    if errors:
        raise SystemExit(runtime_schema_incompatibility_message(database, '; '.join(errors)))


def validate_existing_runtime_schema(target_root: Path, reset_runtime: bool, clean_install: bool) -> None:
    if reset_runtime or clean_install:
        return
    database = target_root / SQLITE_STATE_REL_PATH
    if not database.exists():
        return
    schema_version = read_runtime_schema_version(database)
    if schema_version != RUNTIME_SCHEMA_VERSION:
        detail = 'schema_version is missing' if schema_version is None else f'schema_version={schema_version!r}'
        raise SystemExit(runtime_schema_incompatibility_message(database, detail))
    validate_runtime_physical_schema(database)


def initialize_sqlite_runtime(source_root: Path, target_root: Path, reset_runtime: bool, dry_run: bool) -> None:
    destination = target_root / SQLITE_STATE_REL_PATH
    if destination.exists() and not reset_runtime:
        log(f'既存状態を保持 {destination}')
        return

    log(f'init sqlite {destination}')
    if dry_run:
        return

    schema_path = source_root / '.agents' / 'orchestra' / 'scripts' / 'queue_schema.sql'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(destination) as connection:
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA journal_mode = WAL')
        connection.executescript(schema_path.read_text(encoding='utf-8'))
        errors = collect_runtime_schema_errors(connection)
        if errors:
            raise SystemExit(runtime_schema_incompatibility_message(destination, '; '.join(errors)))
        connection.execute(
            '''
            INSERT INTO queue_metadata(key, value)
            VALUES('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            ''',
            (RUNTIME_SCHEMA_VERSION,),
        )


def iter_template_files(source_root: Path) -> Iterable[Path]:
    for path in sorted(source_root.rglob('*')):
        if path.is_file():
            yield path


def copy_template_files(source_root: Path, target_root: Path, reset_runtime: bool, dry_run: bool) -> None:
    for src in iter_template_files(source_root):
        rel = src.relative_to(source_root)
        if rel.as_posix() == 'AGENTS.md':
            continue
        dst = target_root / map_template_path(rel)
        if dst.exists() and is_runtime_state_file(rel) and not reset_runtime:
            log(f'既存状態を保持 {dst}')
            continue
        copy_file(src, dst, dry_run)


def prune_removed_template_files(source_root: Path, target_root: Path, dry_run: bool) -> None:
    for rel in REMOVED_TEMPLATE_REL_PATHS:
        if (source_root / rel).exists():
            continue
        remove_path(target_root / rel, dry_run)


def strip_limited_toml_comment(value: str) -> str:
    in_quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == '\\' and in_quote == '"':
            escaped = True
            continue
        if char in ("'", '"'):
            if in_quote == char:
                in_quote = None
            elif in_quote is None:
                in_quote = char
            continue
        if char == '#' and in_quote is None:
            return value[:index].strip()
    return value.strip()


def parse_limited_toml_scalar(raw_value: str) -> object:
    value = strip_limited_toml_comment(raw_value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    normalized = value.replace('_', '')
    if normalized.isdecimal():
        return int(normalized)
    if value == 'true':
        return True
    if value == 'false':
        return False
    return value


def parse_limited_toml(toml_path: Path) -> dict[str, object]:
    document: dict[str, object] = {}
    current: dict[str, object] = document
    lines = toml_path.read_text(encoding='utf-8').splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        index += 1
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith('[') and stripped.endswith(']') and stripped.count('[') == 1:
            section = stripped[1:-1].strip()
            current = document
            for part in section.split('.'):
                nested = current.setdefault(part, {})
                if not isinstance(nested, dict):
                    raise SystemExit(f'{toml_path} の [{section}] は mapping にしてください。')
                current = nested
            continue
        key, separator, rest = stripped.partition('=')
        if not separator:
            continue
        key = key.strip()
        value = rest.strip()
        if value.startswith('"""'):
            value = value[3:]
            collected: list[str] = []
            if '"""' in value:
                before, _marker, _after = value.partition('"""')
                collected.append(before)
            else:
                collected.append(value)
                while index < len(lines):
                    next_line = lines[index]
                    index += 1
                    if '"""' in next_line:
                        before, _marker, _after = next_line.partition('"""')
                        collected.append(before)
                        break
                    collected.append(next_line)
            current[key] = '\n'.join(collected)
        else:
            current[key] = parse_limited_toml_scalar(value)
    return document


def read_toml_document(toml_path: Path) -> dict[str, object]:
    if not toml_path.exists() or not toml_path.is_file():
        raise SystemExit(f'TOML template が見つかりません: {toml_path}')
    if tomllib is not None:
        try:
            return tomllib.loads(toml_path.read_text(encoding='utf-8'))
        except tomllib.TOMLDecodeError as exc:  # type: ignore[union-attr]
            raise SystemExit(f'{toml_path} の TOML parse に失敗しました: {exc}') from exc
    return parse_limited_toml(toml_path)


def parse_limited_settings_scalar(raw_value: str) -> object:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    if value.isdecimal():
        return int(value)
    return value


def read_settings_install_subset(settings_path: Path) -> dict[str, object]:
    workers: dict[str, dict[str, object]] = {}
    section: str | None = None
    worker_key: str | None = None

    for line in settings_path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip(' '))
        stripped = line.strip()

        if indent == 0:
            key, separator, rest = stripped.partition(':')
            section = key if separator and not rest.strip() and key == 'workers' else None
            worker_key = None
            continue

        if section == 'workers':
            if indent == 2:
                key, separator, rest = stripped.partition(':')
                worker_key = key if separator and not rest.strip() else None
                if worker_key:
                    workers.setdefault(worker_key, {})
                continue
            if indent == 4 and worker_key:
                key, separator, rest = stripped.partition(':')
                if separator:
                    workers[worker_key][key] = parse_limited_settings_scalar(rest)
            continue

    return {
        'workers': workers,
    }


def read_settings(source_root: Path) -> dict[str, object]:
    settings_path = source_root / '.agents' / 'orchestra' / 'config' / 'settings.yaml'
    if yaml is None:
        return read_settings_install_subset(settings_path)
    try:
        document = yaml.safe_load(settings_path.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        raise SystemExit(f'settings.yaml の YAML parse に失敗しました: {exc}') from exc
    if not isinstance(document, dict):
        raise SystemExit('settings.yaml は mapping にしてください。')
    return document


def load_worker_roles(source_root: Path) -> dict[str, dict[str, int]]:
    settings = read_settings(source_root)
    workers = settings.get('workers')
    if not isinstance(workers, dict):
        raise SystemExit('settings.yaml workers は mapping にしてください。')
    expected_roles = {
        'adventurer': 1,
        'party_leader': 1,
        'inquisitor': 1,
        'advisor': 1,
    }

    result: dict[str, dict[str, int]] = {}
    for role, default_max_parallel in expected_roles.items():
        value = workers.get(role)
        if not isinstance(value, dict):
            raise SystemExit(f'settings.yaml workers.{role} は mapping にしてください。')
        max_parallel = value.get('max_parallel', default_max_parallel)
        if isinstance(max_parallel, bool) or not isinstance(max_parallel, int) or max_parallel < 1:
            raise SystemExit(f'settings.yaml workers.{role}.max_parallel は 1 以上の整数にしてください。')
        result[role] = {'max_parallel': max_parallel}
    return result


def validate_codex_agent_preflight(source_root: Path) -> None:
    config_path = source_root / '.codex' / 'config.toml'
    config = read_toml_document(config_path)
    agents_config = config.get('agents')
    if not isinstance(agents_config, dict):
        raise SystemExit('template/.codex/config.toml の [agents] が必要です。')
    if agents_config.get('max_depth') != 4:
        raise SystemExit('template/.codex/config.toml の agents.max_depth は 4 にしてください。')

    advisor_path = source_root / '.codex' / 'agents' / 'advisor.toml'
    advisor = read_toml_document(advisor_path)
    if advisor.get('sandbox_mode') != 'read-only':
        raise SystemExit('template/.codex/agents/advisor.toml の sandbox_mode は read-only にしてください。')
    if advisor.get('model_reasoning_effort') != 'xhigh':
        raise SystemExit('template/.codex/agents/advisor.toml の model_reasoning_effort は xhigh にしてください。')
    developer_instructions = advisor.get('developer_instructions')
    if not isinstance(developer_instructions, str):
        raise SystemExit('template/.codex/agents/advisor.toml の developer_instructions が必要です。')
    missing_tokens = [token for token in ADVISOR_DEVELOPER_INSTRUCTION_TOKENS if token not in developer_instructions]
    if missing_tokens:
        raise SystemExit(
            'template/.codex/agents/advisor.toml の developer_instructions に advisor 契約が不足しています: '
            + ', '.join(missing_tokens)
        )


def preflight_source_template(source_root: Path) -> None:
    load_worker_roles(source_root)
    validate_codex_agent_preflight(source_root)


def ensure_repositories_root(target_root: Path, dry_run: bool) -> None:
    ensure_directory(target_root / REPOSITORIES_REL_PATH, dry_run)


def update_git_exclude(target_root: Path, enabled: bool, dry_run: bool) -> None:
    exclude_path = target_root / '.git' / 'info' / 'exclude'
    if not enabled:
        return
    if not exclude_path.parent.exists():
        return

    lines = [EXCLUDE_START, '.agents/orchestra/', '.codex/', '.orchestra/', '.codex-guild-orchestra-backups/']
    lines.append(EXCLUDE_END)
    block = '\n'.join(lines) + '\n'
    upsert_text_block(exclude_path, block, EXCLUDE_START, EXCLUDE_END, dry_run)


def update_agents_md(target_root: Path, source_root: Path, dry_run: bool) -> None:
    body = (source_root / 'AGENTS.md').read_text(encoding='utf-8').rstrip()
    block = f'{AGENTS_START}\n{body}\n{AGENTS_END}\n'
    upsert_text_block(target_root / 'AGENTS.md', block, AGENTS_START, AGENTS_END, dry_run)


def validate_target(target_root: Path) -> None:
    if target_root == ROOT:
        raise SystemExit('この配布元リポジトリ自身をギルド規約ルートにはできません。動作確認は一時ディレクトリか別のギルド規約ルートを指定してください。')
    if target_root == Path(target_root.anchor).resolve() or target_root == Path.home().resolve():
        raise SystemExit('導入先が広すぎます。専用のギルド規約ルートを指定してください。')
    if any(part == REPOSITORIES_REL_PATH.name for part in target_root.parts):
        raise SystemExit('導入先は子リポジトリや repositories/ ではなく、その親のギルド規約ルートを指定してください。')


def main() -> int:
    args = parse_args()
    if args.mode != 'copy':
        raise SystemExit('copy モードのみ対応しています。')

    source_root = Path(args.source).expanduser().resolve()
    target_root = Path(args.target).expanduser().resolve()

    if not source_root.exists() or not source_root.is_dir():
        raise SystemExit(f'コピー元が見つかりません: {source_root}')

    validate_target(target_root)
    preflight_source_template(source_root)
    validate_existing_runtime_schema(target_root, args.reset_runtime, args.clean_install)
    if args.reset_runtime and not args.clean_install and not args.backup and not args.dry_run and not args.allow_reset_runtime_without_backup:
        raise SystemExit('`--reset-runtime` は既存の Ledger/dashboard 状態を削除します。通常は `--backup` を併用してください。バックアップなしで進める場合だけ `--allow-reset-runtime-without-backup` を明示してください。')
    ensure_directory(target_root, args.dry_run)
    ensure_repositories_root(target_root, args.dry_run)

    if source_root != DEFAULT_SOURCE.resolve():
        log('注意: 既定以外の `--source` を使っています。信頼済み template だけを指定してください。')

    log('注意: この導入はギルド規約ルートの `.agents/orchestra/`、`.codex/`、`.orchestra/` を作成または更新し、`repositories/` を用意します。Codex の protected path 上で実行する場合は承認が必要になることがあります。')
    if not args.no_git_exclude:
        log('注意: Git ルートでは `.git/info/exclude` も更新します。避ける場合は `--no-git-exclude` を指定してください。')

    if args.backup:
        backup_existing(target_root, args.dry_run)

    if args.clean_install:
        clean_install_target(target_root, not args.no_git_exclude, args.dry_run)
    elif args.reset_runtime:
        reset_runtime_state(target_root, args.dry_run)

    copy_template_files(source_root, target_root, args.reset_runtime, args.dry_run)
    prune_removed_template_files(source_root, target_root, args.dry_run)
    update_agents_md(target_root, source_root, args.dry_run)
    initialize_sqlite_runtime(source_root, target_root, args.reset_runtime, args.dry_run)

    update_git_exclude(target_root, not args.no_git_exclude, args.dry_run)

    if args.dry_run:
        log('dry-run: 変更は書き込んでいません。')
    else:
        log('完了: ギルド規約ルートへの最小ランタイム導入が終わりました。子リポジトリは repositories/<repo> に配置してください。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
