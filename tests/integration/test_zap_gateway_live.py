"""Evidence from one real ZAP Baseline run through the internal DAST Gateway."""

import json
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live_gateway]

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "artifacts/raw/zap.json"
GATEWAY_LOG = REPO_ROOT / "artifacts/dast/gateway-access.log"


def test_zap_report_came_from_the_gateway_target():
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    assert data["site"], "ZAP report không có site nào"
    names = [str(site.get("@name", "")) for site in data["site"]]
    assert all(name == "http://gateway-dast:8081" for name in names), names
    instances = [
        instance
        for site in data["site"]
        for alert in site.get("alerts", [])
        for instance in alert.get("instances", [])
    ]
    assert any("/WebGoat/login" in str(item.get("uri", "")) for item in instances)
    assert "webgoat:8080" not in REPORT.read_text(encoding="utf-8")


def test_gateway_log_proves_zap_requests_crossed_the_boundary():
    text = GATEWAY_LOG.read_text(encoding="utf-8")
    entries = [line for line in text.splitlines() if "channel=dast method=" in line]
    assert entries, "Không có request DAST nào trong access log của Gateway"
    assert any(
        "method=GET" in line and "path=/WebGoat/login" in line and "status=200" in line
        for line in entries
    ), (
        "Access log chỉ có healthcheck, không có target request của ZAP"
    )

    for line in entries:
        method = re.search(r"method=([^ ]+) ", line)
        path = re.search(r"path=([^ ]+) ", line)
        status = re.search(r"status=([0-9]+) ", line)
        assert method and path and status, line
        if method.group(1) not in {"GET", "HEAD", "POST"}:
            assert status.group(1) == "405", line
        if method.group(1) == "POST":
            # POST chi hop le voi path co trong dast-allowlist.json. Moi POST
            # khac phai bi 405 ngay tai Gateway.
            assert status.group(1) in {"200", "204", "405"}, line
        if not path.group(1).startswith("/WebGoat/") and path.group(1) not in {
            "/",
            "/WebGoat",
        }:
            assert status.group(1) == "403", line


def test_dast_artifacts_do_not_contain_a_key_header_or_value():
    combined = REPORT.read_text(encoding="utf-8") + GATEWAY_LOG.read_text(
        encoding="utf-8"
    )
    assert "X-Sentinel-DAST-Key" not in combined


def _request_from_inside_gateway(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "dast",
            "exec",
            "-T",
            "gateway-dast",
            "sh",
            "-c",
            command,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def test_dast_gateway_rejects_a_request_without_its_key():
    result = _request_from_inside_gateway(
        "wget -S -O /dev/null http://127.0.0.1:8081/WebGoat/login"
    )
    assert result.returncode != 0
    assert "401" in result.stderr


def test_zap_cannot_influence_the_body_webgoat_receives():
    """ZAP POST một canary; WebGoat phải nhận body chính tắc của lane.

    Đây là bản sao của test_a_reviewed_template_does_not_licence_an_unreviewed_body
    ở lane probe — test đó đã bắt được một bypass thật ở vòng review 82/100.
    """
    import json as _json

    allowlist = _json.loads(
        (REPO_ROOT / "configs/gateway/dast-allowlist.json").read_text(
            encoding="utf-8"
        )
    )["endpoints"]
    assert allowlist, "Không có mục nào để kiểm"
    path = allowlist[0]["path"]
    canary = "sentinel-canary-do-not-forward-9f3a2b"

    result = _request_from_inside_gateway(
        f'wget -S -O /tmp/resp --post-data="{canary}=1" '
        '--header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" '
        f'http://127.0.0.1:8081{path} 2>&1; cat /tmp/resp'
    )
    assert canary not in result.stdout, (
        "Canary của ZAP vọng lại trong response — body của caller đã tới WebGoat"
    )
    assert canary not in result.stderr


def test_post_to_an_unlisted_path_is_refused_at_the_gateway():
    result = _request_from_inside_gateway(
        'wget -S -O /dev/null --post-data="x=1" '
        '--header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" '
        "http://127.0.0.1:8081/WebGoat/login"
    )
    assert result.returncode != 0
    assert "405" in result.stderr


def test_no_dast_artifact_contains_the_canonical_body_of_an_unlisted_path():
    """Report và log không được lộ thứ chưa duyệt."""
    combined = REPORT.read_text(encoding="utf-8") + GATEWAY_LOG.read_text(
        encoding="utf-8"
    )
    assert "sentinel-canary" not in combined
