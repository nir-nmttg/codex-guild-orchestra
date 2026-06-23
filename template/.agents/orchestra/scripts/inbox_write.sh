#!/usr/bin/env bash
# SQLite inboxへメッセージを追記する軽量 wrapper。
# Usage: bash <orchestra-root>/scripts/inbox_write.sh <target_role> <content> <type> <from>

set -euo pipefail

STATIC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUILD_ROOT="$(cd "$STATIC_ROOT/../.." && pwd)"
RUNTIME_ROOT="${CODEX_GUILD_ORCHESTRA_RUNTIME_ROOT:-$GUILD_ROOT/.orchestra}"
PYTHON_BIN="${CODEX_GUILD_ORCHESTRA_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$PWD/.venv/bin/python" ]; then
    PYTHON_BIN="$PWD/.venv/bin/python"
  elif [ -x "$GUILD_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$GUILD_ROOT/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [ "$#" -ne 4 ]; then
  echo "使い方: inbox_write.sh <target_role> <content> <type> <from>" >&2
  exit 1
fi

TARGET="$1"
CONTENT="$2"
TYPE="$3"
FROM="$4"

if [ "$TARGET" = "$FROM" ]; then
  echo "inbox_write: 自分自身への送信は拒否します: $FROM" >&2
  exit 1
fi

MESSAGE_JSON="$("$PYTHON_BIN" - "$TARGET" "$CONTENT" "$TYPE" "$FROM" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import uuid


def fail(message: str) -> None:
    print(f'inbox_write: {message}', file=sys.stderr)
    raise SystemExit(1)


target, content, message_type, sender = sys.argv[1:5]
allowed_roles = {'receptionist', 'guildmaster', 'cartographer', 'courier', 'party_leader', 'inquisitor', 'adventurer', 'advisor'}
if target not in allowed_roles:
    fail(f'未知の送信先です: {target}')
if sender not in allowed_roles:
    fail(f'未知の送信元です: {sender}')

now = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
payload = {
    'id': f'msg_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}_{uuid.uuid4().hex[:12]}',
    'sender': sender,
    'recipient': target,
    'created_at': now,
    'type': message_type,
    'trusted': False,
    'payload': {'summary': content},
    'status': 'unread',
}
print(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
PY
)"

exec "$PYTHON_BIN" "$STATIC_ROOT/scripts/queue_db.py" \
  --runtime-root "$RUNTIME_ROOT" \
  add-inbox-message \
  "$MESSAGE_JSON"
