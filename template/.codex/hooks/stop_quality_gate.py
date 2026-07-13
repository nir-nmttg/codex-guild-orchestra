#!/usr/bin/env python3
"""終了前に Guild-native summary の不足を促す軽量フック。"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


REQUIRED_SECTION_LABELS = (
    ("Quest", "クエスト", "目的"),
    ("Changes", "変更", "changed"),
    ("Verification", "検証", "validation", "tests"),
    ("Trial", "trial", "レビュー", "審問"),
    ("Risks", "リスク", "risk"),
)

NO_CHANGE_MARKERS = (
    "変更なし",
    "変更はありません",
    "編集なし",
    "未変更",
    "no" + " changes",
    "nothing" + " changed",
)


def _load_payload() -> dict[str, Any]:
    raw = os.environ.get("CODEX_HOOK_PAYLOAD", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _extract_text(payload: dict[str, Any]) -> str:
    for key in ("last_assistant_message", "response", "assistant_response", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _missing_sections(text: str) -> list[str]:
    folded = text.casefold()
    missing: list[str] = []
    for labels in REQUIRED_SECTION_LABELS:
        if not any(label.casefold() in folded for label in labels):
            missing.append(labels[0])
    return missing


def _is_low_pressure_report(text: str, *, strict: bool) -> bool:
    if strict:
        return False
    folded = text.casefold()
    return any(marker.casefold() in folded for marker in NO_CHANGE_MARKERS)


def main() -> int:
    payload = _load_payload()
    strict = os.environ.get("AGENT_GUILD_ORCHESTRA_STOP_QUALITY_STRICT", "0") == "1"
    if payload.get("stop_hook_active"):
        return 0

    text = _extract_text(payload)
    if not text or _is_low_pressure_report(text, strict=strict):
        return 0

    missing = _missing_sections(text)
    if not missing:
        return 0

    message = "最終要約に Quest / Changes / Verification / Trial / Risks を含めてください。変更がない場合は『変更なし』または `No changes` と明示してください。"
    response = {
        "continue": not strict,
        "systemMessage": message,
    }
    if strict:
        response["decision"] = "block"
        response["reason"] = message
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
