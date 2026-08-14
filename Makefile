SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
PYTHON := $(shell command -v .venv/bin/python3 2>/dev/null || command -v python3)

.PHONY: target-up target-down scan scan-opengrep normalize search analyze analyze-mock analyze-offline-full validate-analysis agent-test gateway-build gateway-up gateway-down gateway-test gateway-live-test gateway-demo

agent-test:
	@LLM_PROVIDER=fake pytest -q tests 2>/dev/null || LLM_PROVIDER=fake .venv/bin/pytest -q tests

target-up:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
		KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
		test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
		SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose up --detach gateway webgoat; \
		for attempt in $$(seq 1 30); do \
		if curl --fail --silent --show-error --header "X-Sentinel-API-Key: $$KEY" http://127.0.0.1:9080/WebGoat/actuator/health >/dev/null; then \
			printf '%s\n' 'WebGoat is ready through Gateway: http://127.0.0.1:9080/WebGoat/'; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	docker compose logs --tail=100 webgoat; \
	printf '%s\n' 'WebGoat did not become healthy within 60 seconds.' >&2; \
	exit 1

target-down:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
		KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
		SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose down

scan: scan-opengrep

scan-opengrep:
	@./scripts/scan-opengrep.sh

normalize:
	@$(PYTHON) -m project_sentinel.ingestion.normalizer \
		--input artifacts/raw/opengrep.json \
		--output artifacts/normalized/findings.json

search:
	@test -n "$(Q)" || (printf '%s\n' 'Usage: make search Q='\''SQL Injection'\''' >&2; exit 1)
	@$(PYTHON) -m project_sentinel.retrieval.keyword_search $(Q)

analyze:
	$(PYTHON) -m project_sentinel.cli analyze \
	  --input artifacts/normalized/findings.json \
	  --output artifacts/analysis/security-analysis.jsonl \
	  --summary artifacts/analysis/run-summary.json

analyze-mock:
	$(PYTHON) -m project_sentinel.cli analyze \
	  --input tests/fixtures/findings/valid.json \
	  --provider fake \
	  --output artifacts/analysis/security-analysis.jsonl \
	  --summary artifacts/analysis/run-summary.json

analyze-offline-full:
	$(PYTHON) -m project_sentinel.cli analyze \
	  --input artifacts/normalized/findings.json \
	  --provider fake \
	  --output artifacts/analysis/security-analysis.jsonl \
	  --summary artifacts/analysis/run-summary.json

validate-analysis:
	@$(PYTHON) -m project_sentinel.cli validate --input artifacts/analysis/security-analysis.jsonl

gateway-build:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose build gateway

gateway-up:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose up -d gateway webgoat

gateway-down:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose down

gateway-test:
	$(PYTHON) -m pytest tests/unit/gateway tests/unit/verification -v

gateway-live-test:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose up --detach --build gateway webgoat; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose up --detach --force-recreate --no-deps gateway; \
	for attempt in $$(seq 1 30); do \
		code=$$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:9080/WebGoat/actuator/health || true); \
		test "$$code" = 401 && break; \
		test "$$attempt" = 30 && (printf '%s\n' 'Gateway did not become ready.' >&2; exit 1); \
		sleep 1; \
	done; \
	set +e; \
	RUN_LIVE_GATEWAY_TESTS=1 SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m pytest tests/integration/test_gateway_live.py -v; \
	status=$$?; \
	set -e; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose up --detach --force-recreate --no-deps gateway >/dev/null; \
	exit $$status

gateway-demo:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m project_sentinel.gateway.cli request --template-id tmpl_health_get
