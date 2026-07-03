#!/usr/bin/env python3
"""Guild-native runtime contract validator."""

from __future__ import annotations

import sys

from validation.basic import (
    validate_active_prose_vocabulary,
    validate_dependencies,
    validate_required_paths,
    validate_version,
)
from validation.claude_compat_smoke import validate_claude_compat_smoke
from validation.core import ValidationError
from validation.docs import validate_agents, validate_docs_and_instructions, validate_skills, validate_stop_hook
from validation.golden_quests import validate_golden_quests
from validation.install_smoke import validate_install_upgrade_smoke
from validation.queue_templates import validate_queue_templates
from validation.runtime_smoke import validate_queue_db_smoke, validate_sqlite_schema
from validation.settings import validate_settings


def main() -> int:
    checks = [
        validate_dependencies,
        validate_required_paths,
        validate_version,
        validate_settings,
        validate_queue_templates,
        validate_sqlite_schema,
        validate_queue_db_smoke,
        validate_golden_quests,
        validate_install_upgrade_smoke,
        validate_claude_compat_smoke,
        validate_agents,
        validate_active_prose_vocabulary,
        validate_docs_and_instructions,
        validate_skills,
        validate_stop_hook,
    ]
    for check in checks:
        check()
    print("validate: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"validate: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
