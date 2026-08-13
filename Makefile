SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
PYTHON := $(shell command -v .venv/bin/python3 2>/dev/null || command -v python3)

.PHONY: target-up target-down scan scan-opengrep normalize search analyze analyze-mock analyze-offline-full validate-analysis verify verify-mock agent-test

agent-test:
	@LLM_PROVIDER=fake pytest -q tests 2>/dev/null || LLM_PROVIDER=fake .venv/bin/pytest -q tests

target-up:
	@docker compose up --detach webgoat
	@for attempt in $$(seq 1 30); do \
		if curl --fail --silent --show-error http://127.0.0.1:8080/WebGoat/actuator/health >/dev/null; then \
			printf '%s\n' 'WebGoat is ready: http://127.0.0.1:8080/WebGoat/'; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	docker compose logs --tail=100 webgoat; \
	printf '%s\n' 'WebGoat did not become healthy within 60 seconds.' >&2; \
	exit 1

target-down:
	@docker compose down

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

verify:
	$(PYTHON) -m project_sentinel.cli verify

verify-mock:
	$(PYTHON) -m project_sentinel.cli verify-mock

gateway-build:
	docker compose build gateway

gateway-up:
	docker compose up -d gateway webgoat

gateway-down:
	docker compose down

gateway-test:
	$(PYTHON) -m pytest tests/test_gateway_*.py -v

gateway-demo:
	@KEY=$$(grep '^SENTINEL_API_KEY=' .env 2>/dev/null | cut -d= -f2-); \
	SENTINEL_API_KEY=$$KEY $(PYTHON) -m project_sentinel.gateway.cli request --method GET --path /WebGoat/actuator/health
