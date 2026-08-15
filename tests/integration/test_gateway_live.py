"""Opt-in acceptance test against the real local Docker Gateway and WebGoat."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.gateway_client import API_KEY_HEADER, GATEWAY_ORIGIN, execute_candidate
from project_sentinel.verification.models import HttpRequest, VerificationCandidate, VerificationDecision, VerificationStatus
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import RealTransport


def _send(method: str, path: str, api_key: str | None = None):
    headers = {API_KEY_HEADER: api_key} if api_key is not None else {}
    return RealTransport().send_request(
        HttpRequest(method=method, url=f"{GATEWAY_ORIGIN}{path}", headers=headers)
    )


@pytest.mark.integration
@pytest.mark.live_gateway
def test_real_agent_to_gateway_to_webgoat_flow(tmp_path):
    if os.environ.get("RUN_LIVE_GATEWAY_TESTS") != "1":
        pytest.fail(
            "Live Gateway test requires running Gateway and setting RUN_LIVE_GATEWAY_TESTS=1 and SENTINEL_GATEWAY_API_KEY. "
            "Start containers with `make gateway-up` and run `make gateway-live-test`."
        )
    api_key = os.environ.get("SENTINEL_GATEWAY_API_KEY")
    if not api_key:
        pytest.fail("SENTINEL_GATEWAY_API_KEY is required for live integration")

    # Gateway independently rejects missing/wrong credentials, paths and methods.
    assert _send("GET", "/WebGoat/actuator/health").status_code == 401
    assert _send("GET", "/WebGoat/actuator/health", "wrong-live-key").status_code == 401
    assert _send("GET", "/WebGoat/login", api_key).status_code == 403
    assert _send("DELETE", "/WebGoat/actuator/health", api_key).status_code == 405

    allowlist = Allowlist.from_json("configs/gateway/endpoint-allowlist.json")
    templates = ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")
    audit_path = tmp_path / "live-audit.jsonl"

    # Two reviewed candidates exercise real GET and benign POST requests.
    cand_health = VerificationCandidate(
        candidate_id="cand-health-1",
        objective_id="obj-health",
        proposal_id="prop-health",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )
    cand_post = VerificationCandidate(
        candidate_id="cand-attack-1",
        objective_id="obj-attack",
        proposal_id="prop-attack",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_attack",
        template_id="tmpl_attack_post_empty",
        method="POST",
        path="/WebGoat/attack",
        target_field="input",
        payload_type="empty_value",
    )

    res_health = execute_candidate(cand_health, RealTransport(), allowlist, templates, api_key, log_path=str(audit_path))
    res_post = execute_candidate(cand_post, RealTransport(), allowlist, templates, api_key, log_path=str(audit_path))

    assert res_health.status_code == 200
    assert res_health.status is VerificationStatus.OBSERVED
    assert res_post.status_code in {200, 302}
    assert res_post.status is VerificationStatus.OBSERVED

    # Saturate the server-side bucket, then prove the tool maps the response.
    rate_codes = [
        _send("GET", "/WebGoat/actuator/health", api_key).status_code
        for _ in range(10)
    ]
    assert 429 in rate_codes
    limited = execute_candidate(
        cand_health,
        RealTransport(),
        allowlist,
        templates,
        api_key,
        log_path=str(audit_path),
    )
    assert limited.status is VerificationStatus.RATE_LIMITED
    assert limited.status_code == 429

    # WebGoat must not have a directly published host port.
    with pytest.raises(OSError):
        with socket.create_connection(("127.0.0.1", 8080), timeout=0.25):
            pass

    combined_outputs = audit_path.read_text(encoding="utf-8")
    assert api_key not in combined_outputs
