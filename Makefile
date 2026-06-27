.PHONY: validate audit-ja install-dry-run docker-build

DOCKER_PYTHON := ./scripts/docker_python.sh
DOCKER_IMAGE ?= codex-guild-orchestra-tools:local

docker-build:
	docker build -t "$(DOCKER_IMAGE)" .

validate:
	"$(DOCKER_PYTHON)" scripts/validate.py
	"$(DOCKER_PYTHON)" scripts/audit_english.py

audit-ja:
	"$(DOCKER_PYTHON)" scripts/audit_english.py

install-dry-run:
	tmp="$$(mktemp -d)"; \
	trap 'rm -rf "$$tmp"' EXIT; \
	"$(DOCKER_PYTHON)" scripts/install.py --target "$$tmp" --mode copy --dry-run
