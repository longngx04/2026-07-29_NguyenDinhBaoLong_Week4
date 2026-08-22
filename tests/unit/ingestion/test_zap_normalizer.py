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


def _report_many_urls(count: int) -> dict:
    """Mot alert cau hinh trai tren nhieu URL — dung canh WebGoat that.

    WebSecurityConfig.java:62 goi headers.disable(), nen alert thieu security
    header ban tren MOI URL. Mot-finding-mot-URL se lam no findings.json.
    """
    return {
        "@version": "2.17.0",
        "site": [
            {
                "@name": "http://gateway-dast:8081",
                "alerts": [
                    {
                        "pluginid": "10021",
                        "alert": "X-Content-Type-Options Header Missing",
                        "riskcode": "1",
                        "confidence": "2",
                        "desc": "<p>Missing header.</p>",
                        "solution": "<p>Set nosniff.</p>",
                        "cweid": "693",
                        "instances": [
                            {
                                "uri": f"http://gateway-dast:8081/WebGoat/lesson{i}",
                                "method": "GET",
                                "param": "",
                            }
                            for i in range(count)
                        ],
                    }
                ],
            }
        ],
    }


def test_one_alert_type_yields_one_finding_regardless_of_url_count():
    findings = normalize_zap_report(_report_many_urls(300))
    assert len(findings) == 1, (
        "Gop theo pluginid: 300 URL khong duoc thanh 300 finding"
    )


def test_instances_are_capped_but_the_true_total_is_kept():
    findings = normalize_zap_report(_report_many_urls(300))
    assert len(findings[0]["instances"]) == 20
    assert findings[0]["instances_total"] == 300


def test_the_cap_is_configurable():
    findings = normalize_zap_report(_report_many_urls(300), max_instances=5)
    assert len(findings[0]["instances"]) == 5
    assert findings[0]["instances_total"] == 300


def test_each_instance_keeps_url_method_and_param():
    findings = normalize_zap_report(_report_many_urls(3))
    instance = findings[0]["instances"][0]
    assert instance["url"].startswith("http://gateway-dast:8081/WebGoat/")
    assert instance["method"] == "GET"
    assert "param" in instance


def test_gateway_filter_still_runs_per_instance_before_grouping():
    report = _report_many_urls(2)
    report["site"][0]["alerts"][0]["instances"].append(
        {"uri": "http://webgoat:8080/WebGoat/direct", "method": "GET", "param": ""}
    )
    findings = normalize_zap_report(report)
    urls = [item["url"] for item in findings[0]["instances"]]
    assert all("gateway-dast" in url for url in urls)
    assert findings[0]["instances_total"] == 2


def test_two_alert_types_stay_two_findings():
    report = _report_many_urls(2)
    second = dict(report["site"][0]["alerts"][0])
    second["pluginid"] = "10038"
    second["alert"] = "CSP Header Not Set"
    report["site"][0]["alerts"].append(second)
    assert len(normalize_zap_report(report)) == 2

