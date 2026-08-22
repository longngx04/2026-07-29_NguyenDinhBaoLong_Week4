"""Plan requestor chỉ được gửi đúng những gì allowlist đã duyệt."""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = REPO_ROOT / "infra/docker/zap/requestor-plan.yaml"
ALLOWLIST = REPO_ROOT / "configs/gateway/dast-allowlist.json"


def _plan() -> dict:
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))


def _requests() -> list[dict]:
    for job in _plan()["jobs"]:
        if job.get("type") == "requestor":
            return job["requests"]
    raise AssertionError("Plan không có job requestor nào")


def _allowlist() -> list[dict]:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))["endpoints"]


def test_every_request_targets_the_dast_gateway_not_webgoat():
    for request in _requests():
        assert request["url"].startswith("http://gateway-dast:8081/"), request["url"]
    assert "webgoat:8080" not in PLAN.read_text(encoding="utf-8"), (
        "ZAP không bao giờ được biết địa chỉ trực tiếp của WebGoat"
    )


def test_requests_match_the_allowlist_exactly():
    """Không thừa, không thiếu. Thừa là gửi thứ chưa duyệt; thiếu là bỏ sót."""
    planned = {
        (r["method"].upper(), r["url"].removeprefix("http://gateway-dast:8081"))
        for r in _requests()
    }
    allowed = {(e["method"], e["path"]) for e in _allowlist()}
    assert planned == allowed, (
        f"Chỉ trong plan: {sorted(planned - allowed)} · "
        f"Chỉ trong allowlist: {sorted(allowed - planned)}"
    )


def test_the_plan_runs_no_scanner_job():
    """Plan này chỉ để chạm endpoint, không quét. Active scan bị cấm hẳn."""
    types = {job.get("type") for job in _plan()["jobs"]}
    assert "activeScan" not in types
    assert "spider" not in types
    assert "spiderAjax" not in types
