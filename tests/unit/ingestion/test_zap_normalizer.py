import json

import pytest

from project_sentinel.ingestion.zap_normalizer import normalize_zap_report, run_normalize


def _report():
    return {
        "@version": "2.17.0",
        "site": [
            {
                "@name": "http://gateway-dast:8081/WebGoat/login",
                "alerts": [
                    {
                        "pluginid": "10021",
                        "alert": "X-Content-Type-Options Header Missing",
                        "riskcode": "1",
                        "confidence": "2",
                        "desc": "<p>The response is missing a header.</p>",
                        "solution": "<p>Set nosniff.</p>",
                        "cweid": "693",
                        "instances": [
                            {
                                "uri": "http://gateway-dast:8081/WebGoat/login",
                                "method": "GET",
                                "param": "",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_zap_alert_is_mapped_to_the_shared_finding_shape():
    findings = normalize_zap_report(_report())
    assert len(findings) == 1
    finding = findings[0]
    assert finding["id"].startswith("zap-10021-")
    assert finding["tool"] == "zap"
    assert finding["tool_version"] == "2.17.0"
    assert finding["severity"] == "low"
    assert finding["confidence"] == "medium"
    assert finding["cwe"] == ["CWE-693"]
    assert finding["line"] == 0
    assert finding["file_or_url"].startswith("http://gateway-dast:8081/")
    assert "<p>" not in finding["message"]


def test_duplicate_instances_are_deduplicated_by_fingerprint():
    report = _report()
    instance = report["site"][0]["alerts"][0]["instances"][0]
    report["site"][0]["alerts"][0]["instances"].append(dict(instance))
    assert len(normalize_zap_report(report)) == 1


def test_alerts_from_requests_blocked_or_generated_by_gateway_are_not_findings():
    report = _report()
    instances = report["site"][0]["alerts"][0]["instances"]
    instances.extend(
        [
            {
                "uri": "http://gateway-dast:8081/WebGoat/login",
                "method": "POST",
                "param": "username",
            },
            {
                "uri": "http://gateway-dast:8081/",
                "method": "GET",
                "param": "",
            },
            {
                "uri": "http://webgoat:8080/WebGoat/login",
                "method": "GET",
                "param": "",
            },
        ]
    )
    findings = normalize_zap_report(report)
    assert len(findings) == 1
    assert findings[0]["http_method"] == "GET"


def test_report_without_site_array_fails_closed():
    with pytest.raises(ValueError, match="site array"):
        normalize_zap_report({})


def test_run_normalize_writes_a_loadable_artifact(tmp_path):
    raw = tmp_path / "zap.json"
    output = tmp_path / "findings.json"
    raw.write_text(json.dumps(_report()), encoding="utf-8")
    findings = run_normalize(raw, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"] == "zap"
    assert payload["count"] == len(findings) == 1
