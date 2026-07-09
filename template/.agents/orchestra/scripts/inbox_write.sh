#!/usr/bin/env bash
# SQLite inboxへメッセージを追記する軽量 wrapper。
# Usage: bash <orchestra-root>/scripts/inbox_write.sh <target_role> <content> <type> <from>

set -euo pipefail

STATIC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUILD_ROOT="$(cd "$STATIC_ROOT/../.." && pwd)"
RUNTIME_ROOT="${CODEX_GUILD_ORCHESTRA_RUNTIME_ROOT:-$GUILD_ROOT/.orchestra}"
DOCKER_PYTHON="$STATIC_ROOT/scripts/docker_python.sh"

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

MESSAGE_JSON="$("$DOCKER_PYTHON" - "$TARGET" "$CONTENT" "$TYPE" "$FROM" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import uuid


def fail(message: str) -> None:
    print(f'inbox_write: {message}', file=sys.stderr)
    raise SystemExit(1)


target, content, message_type, sender = sys.argv[1:5]
allowed_roles = {'receptionist', 'guildmaster', 'cartographer', 'courier', 'captain', 'inquisitor', 'adventurer', 'artificer', 'sage', 'warden'}
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

exec "$DOCKER_PYTHON" "$STATIC_ROOT/scripts/queue_db.py" \
  --runtime-root "$RUNTIME_ROOT" \
  add-inbox-message \
  "$MESSAGE_JSON"
