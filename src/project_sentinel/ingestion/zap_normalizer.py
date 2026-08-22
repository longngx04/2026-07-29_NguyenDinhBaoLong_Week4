"""Normalize OWASP ZAP JSON into Project Sentinel's shared finding shape."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_INPUT = Path("artifacts/raw/zap.json")
DEFAULT_OUTPUT = Path("artifacts/normalized/zap-findings.json")

RISK = {
    "0": "info",
    "1": "low",
    "2": "medium",
    "3": "high",
    "4": "critical",
}
CONFIDENCE = {
    "0": "low",
    "1": "low",
    "2": "medium",
    "3": "high",
    "4": "high",
}
TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
MAX_MESSAGE_CHARS = 4000
DAST_HOST = "gateway-dast"
DAST_PORT = 8081


def _plain_text(value: Any) -> str:
    text = html.unescape(TAG.sub(" ", str(value or "")))
    return SPACE.sub(" ", text).strip()[:MAX_MESSAGE_CHARS]


def _cwe(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw or raw in {"0", "-1"}:
        return []
    return [f"CWE-{raw}"]


def _fingerprint(plugin_id: str, method: str, uri: str, parameter: str) -> str:
    value = "\0".join((plugin_id, method, uri, parameter)).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _was_forwarded_by_dast_gateway(method: str, uri: str) -> bool:
    """Exclude alerts raised on requests the Gateway itself rejected or generated."""
    if method not in {"GET", "HEAD"}:
        return False
    try:
        parsed = urlsplit(uri)
        return (
            parsed.scheme == "http"
            and parsed.hostname == DAST_HOST
            and parsed.port == DAST_PORT
            and parsed.path.startswith("/WebGoat/")
        )
    except ValueError:
        return False


def normalize_zap_report(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError("ZAP report must be a JSON object")
    sites = raw.get("site")
    if not isinstance(sites, list):
        raise ValueError("ZAP report missing site array")

    version = str(raw.get("@version") or raw.get("version") or "unknown")
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()

    for site in sites:
        if not isinstance(site, dict):
            continue
        alerts = site.get("alerts")
        if not isinstance(alerts, list):
            raise ValueError("ZAP site entry missing alerts array")
        site_url = str(site.get("@name") or "")

        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            plugin_id = str(
                alert.get("pluginid") or alert.get("alertRef") or "unknown"
            )
            title = _plain_text(alert.get("alert") or alert.get("name") or plugin_id)
            description = _plain_text(alert.get("desc") or alert.get("description"))
            solution = _plain_text(alert.get("solution"))
            message = description
            if solution:
                message = f"{description} Recommended fix: {solution}".strip()

            instances = alert.get("instances")
            if not isinstance(instances, list) or not instances:
                instances = [{"uri": site_url, "method": "GET", "param": ""}]

            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                uri = str(instance.get("uri") or site_url)
                method = str(instance.get("method") or "GET").upper()
                if not _was_forwarded_by_dast_gateway(method, uri):
                    continue
                parameter = str(instance.get("param") or "")
                fingerprint = _fingerprint(plugin_id, method, uri, parameter)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                findings.append(
                    {
                        "id": f"zap-{plugin_id}-{fingerprint[:10]}",
                        "tool": "zap",
                        "tool_version": version,
                        "severity": RISK.get(str(alert.get("riskcode")), "low"),
                        "file_or_url": uri,
                        "line": 0,
                        "title": title or f"ZAP alert {plugin_id}",
                        "rule_id": plugin_id,
                        "cwe": _cwe(alert.get("cweid")),
                        "owasp": [],
                        "message": message or title,
                        "confidence": CONFIDENCE.get(
                            str(alert.get("confidence")), "medium"
                        ),
                        "fingerprint": fingerprint,
                        "raw_check_id": plugin_id,
                        "http_method": method,
                        "parameter": parameter,
                    }
                )

    return findings


def run_normalize(
    input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT
) -> list[dict[str, Any]]:
    if not input_path.is_file():
        raise FileNotFoundError(f"Raw ZAP report not found: {input_path}")
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    findings = normalize_zap_report(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": "zap", "count": len(findings), "findings": findings}
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Normalized {len(findings)} ZAP findings -> {output_path}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize OWASP ZAP JSON findings")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        run_normalize(args.input, args.output)
        return 0
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
