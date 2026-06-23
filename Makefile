.PHONY: validate audit-ja install-dry-run

# PYTHON は実行ファイル path として扱う。
PYTHON ?= python3

ifneq (,$(wildcard .venv/bin/python))
PYTHON := .venv/bin/python
endif

validate:
	"$(PYTHON)" scripts/validate.py
	"$(PYTHON)" scripts/audit_english.py

audit-ja:
	"$(PYTHON)" scripts/audit_english.py

install-dry-run:
	tmp="$$(mktemp -d)"; \
	trap 'rm -rf "$$tmp"' EXIT; \
	"$(PYTHON)" scripts/install.py --target "$$tmp" --mode copy --dry-run
