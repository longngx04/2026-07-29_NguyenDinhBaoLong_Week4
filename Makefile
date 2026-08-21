SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
PYTHON := $(shell command -v .venv/bin/python3 2>/dev/null || command -v python3)

.PHONY: target-up target-down scan scan-opengrep normalize search analyze validate-analysis agent-test llm-test probe run runs clean-runs eval gateway-build gateway-up gateway-reset gateway-down gateway-test gateway-live-test gateway-demo exercise-test guardrails-test guardrails-demo score-ground-truth

# Week 4 tests exercise the real Gateway and WebGoat.  The dependency starts
# both services and waits for the allowlisted health endpoint before pytest.
agent-test: gateway-up
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
	$(PYTHON) -m pytest -m "not llm and not live_gateway" -v tests; \
	$(MAKE) gateway-reset; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m pytest -m "live_gateway and not llm" -v tests/integration/test_demo_runner.py; \
	$(MAKE) gateway-reset; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m pytest -m "live_gateway and not llm" -v tests/integration/test_gateway_live.py; \
	$(MAKE) gateway-reset; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m pytest -m "live_gateway and not llm" -v \
		tests/unit/gateway/test_log_redaction.py tests/unit/probe/test_transport.py

# OpenRouter calls are rate-limited and non-deterministic. Sequential execution is
# the reliable grader/CI default at both the pytest and finding-group layers.
# Operators may explicitly opt into bounded concurrency for either layer.
LLM_TEST_WORKERS ?= 1
LLM_TEST_GROUP_CONCURRENCY ?= 1
LLM_TEST_TIMEOUT_SECONDS ?= 60
LLM_TEST_MAX_RETRIES ?= 0
LLM_TEST_VALIDATION_MAX_RETRIES ?= 1

llm-test:
	@KEY=$${LLM_API_KEY:-$$(sed -n 's/^LLM_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'LLM_API_KEY is required in the environment or .env' >&2; exit 2); \
	workers='$(LLM_TEST_WORKERS)'; \
	if ! [[ "$$workers" =~ ^[1-9][0-9]*$$ ]]; then \
		printf '%s\n' 'LLM_TEST_WORKERS must be a positive integer' >&2; \
		exit 2; \
	fi; \
	xdist_args=(); \
	if test "$$workers" -gt 1; then xdist_args=(-n "$$workers"); fi; \
	LLM_API_KEY="$$KEY" \
		LLM_CONCURRENCY='$(LLM_TEST_GROUP_CONCURRENCY)' \
		LLM_TIMEOUT_SECONDS='$(LLM_TEST_TIMEOUT_SECONDS)' \
		LLM_MAX_RETRIES='$(LLM_TEST_MAX_RETRIES)' \
		VALIDATION_MAX_RETRIES='$(LLM_TEST_VALIDATION_MAX_RETRIES)' \
		$(PYTHON) -m pytest -m llm -v "$${xdist_args[@]}"

target-up:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
		KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
		test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
		SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target up --detach gateway webgoat; \
		for attempt in $$(seq 1 30); do \
		code=$$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:9080/WebGoat/actuator/health || true); \
		if test "$$code" = 401; then \
			printf '%s\n' 'Gateway is ready and WebGoat is healthy on the internal network.'; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	docker compose --profile target logs --tail=100 webgoat; \
	printf '%s\n' 'WebGoat did not become healthy within 60 seconds.' >&2; \
	exit 1

target-down:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
		KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
		SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target down

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

validate-analysis:
	@$(PYTHON) -m project_sentinel.cli validate --input artifacts/analysis/security-analysis.jsonl

probe:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
	SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m project_sentinel.cli probe --method GET --path /WebGoat/actuator/health

run:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
	SENTINEL_GATEWAY_API_KEY="$$KEY" $(PYTHON) -m project_sentinel.cli run

runs:
	@$(PYTHON) -m project_sentinel.cli runs

eval:
	@KEY=$${LLM_API_KEY:-$$(sed -n 's/^LLM_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'LLM_API_KEY is required in the environment or .env' >&2; exit 2); \
	LLM_API_KEY="$$KEY" $(PYTHON) -m eval.run_eval $(if $(REPEAT),--repeat $(REPEAT),)

# Chấm Agent trên 23 finding WebGoat thật, đối chiếu nhãn người review đặt.
# Tách rõ scanner precision (thuộc tính của scanner) khỏi Agent triage precision.
#   make score-ground-truth ANALYSIS=artifacts/runs/<run-id>/analysis.jsonl
score-ground-truth:
	@test -n "$(ANALYSIS)" || (printf '%s\n' 'ANALYSIS=<duong dan analysis.jsonl> la bat buoc' >&2; exit 2)
	@$(PYTHON) eval/score_ground_truth.py --analysis "$(ANALYSIS)" $(if $(JSON_OUT),--json-out $(JSON_OUT),)

clean-runs:
	@KEEP=$${KEEP:-5}; \
	cd artifacts/runs 2>/dev/null || exit 0; \
	ls -1d */ 2>/dev/null | sort -r | tail -n +$$((KEEP+1)) | xargs -r rm -rf; \
	printf 'Giữ lại %s lần chạy mới nhất.\n' "$$KEEP"

gateway-build:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target build gateway

gateway-up: target-up

gateway-reset:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target restart gateway >/dev/null; \
	for attempt in $$(seq 1 30); do \
		code=$$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:9080/WebGoat/actuator/health || true); \
		if test "$$code" = 401; then exit 0; fi; \
		test "$$attempt" = 30 && (printf '%s\n' 'Gateway did not become ready after reset.' >&2; exit 1); \
		sleep 1; \
	done

gateway-down:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target down

gateway-test: gateway-up
	$(PYTHON) -m pytest -m "not llm" tests/unit/gateway tests/unit/probe -v

gateway-live-test:
	@KEY=$${SENTINEL_GATEWAY_API_KEY:-$$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}; \
	KEY=$${KEY:-$$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}; \
	test -n "$$KEY" || (printf '%s\n' 'SENTINEL_GATEWAY_API_KEY is required in the environment or .env' >&2; exit 2); \
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target up --detach --build gateway webgoat; \
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
	SENTINEL_GATEWAY_API_KEY="$$KEY" docker compose --profile target restart gateway >/dev/null 2>&1 || true; \
	exit $$status

gateway-demo: probe

exercise-test:
	@$(PYTHON) -m pytest exercises/week4-gateway/tests -v

guardrails-demo: gateway-up
	@$(PYTHON) -m project_sentinel.cli demo $(ARGS)

guardrails-test:
	@$(PYTHON) -m pytest tests/unit/guardrails tests/integration/test_guardrails_acceptance.py -v
