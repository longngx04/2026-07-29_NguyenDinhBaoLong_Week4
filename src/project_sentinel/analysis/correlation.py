"""Noi finding tinh voi endpoint runtime ma ZAP that su cham toi.

Vi sao can. Finding SAST la `SqlInjectionLesson5a.java:47`; endpoint DAST la
`/WebGoat/SqlInjection/attack5a`. Khong co gi noi hai thu do mot cach hien
nhien. Cau noi la annotation route trong chinh file chua finding — trich ra
duoc bang cach doc file, tat dinh, khong hoi LLM.

Ban do endpoint doc tu Nginx access log chu khong tu ZAP. Do la bang chung o
tang ha tang, cung nguyen tac ma scripts/scan-zap.sh dang dung de chung minh
traffic da di qua Gateway.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

STRENGTHS: tuple[str, ...] = (
    "no_route",
    "route_known_not_reached",
    "reachable",
    "reachable_and_alerted",
)

_LOG_LINE = re.compile(
    r"channel=dast\s+method=(?P<method>\S+)\s+path=(?P<path>\S+)\s+"
    r"query=(?P<query>\S*)\s+status=(?P<status>\d+)"
)
_CLASS_MAPPING = re.compile(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]+)"')
_METHOD_MAPPING = re.compile(
    r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?"([^"]+)"'
)
_MAX_BYTES = 512 * 1024


def parse_gateway_access_log(path: str | Path) -> dict[str, Any]:
    """Doc ban do endpoint tu access log cua lane DAST.

    Chi tinh request Gateway that su chuyen tiep: status 4xx/5xx nghia la
    Gateway chan hoac upstream tu choi, khong phai mot endpoint cham toi duoc.
    """
    source = Path(path)
    if not source.is_file():
        return {"endpoints": []}

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _LOG_LINE.search(line)
        if not match:
            continue
        status = int(match.group("status"))
        if status >= 400:
            continue
        method = match.group("method").upper()
        route = match.group("path")
        query = match.group("query")
        params = (
            sorted(urllib.parse.parse_qs(query).keys())
            if query and query != "-"
            else []
        )
        key = (method, route)
        if key in seen:
            merged = sorted(set(seen[key]["params"]) | set(params))
            seen[key]["params"] = merged
            continue
        seen[key] = {"method": method, "path": route, "params": params}

    return {"endpoints": [seen[key] for key in sorted(seen)]}


def _join(prefix: str | None, suffix: str) -> str:
    if not prefix:
        return "/" + suffix.lstrip("/")
    return "/" + prefix.strip("/") + "/" + suffix.lstrip("/")


def extract_route(source_path: str | Path) -> str | None:
    """Tra route Spring khai trong file, hoac None neu khong co.

    Doc co gioi han kich thuoc: mot file khong lo khong duoc lam treo buoc
    normalize. Khong doc duoc thi tra None — thieu bang chung, khong phai loi.
    """
    path = Path(source_path)
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    class_match = _CLASS_MAPPING.search(text)
    class_prefix = class_match.group(1) if class_match else None

    for match in _METHOD_MAPPING.finditer(text):
        if class_match and match.start() == class_match.start():
            continue
        return _join(class_prefix, match.group(1))

    return _join(None, class_prefix) if class_prefix else None


def _route_matches(route: str, observed: set[str]) -> str | None:
    """Route khai trong code la tuong doi voi context path (/WebGoat)."""
    suffix = "/" + route.strip("/")
    for path in observed:
        if path == suffix or path.endswith(suffix):
            return path
    return None


def correlate(
    findings: list[dict[str, Any]],
    endpoints: dict[str, Any],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    """Gan khoi `runtime_evidence` vao moi finding TINH. Khong sua input."""
    observed = {
        str(item.get("path") or "")
        for item in endpoints.get("endpoints") or []
        if item.get("path")
    }

    alerts_by_path: dict[str, list[str]] = {}
    for finding in findings:
        if str(finding.get("tool")) != "zap":
            continue
        for instance in finding.get("instances") or []:
            inst_route = urllib.parse.urlsplit(str(instance.get("url") or "")).path
            if inst_route:
                alerts_by_path.setdefault(inst_route, []).append(str(finding["id"]))


    result: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        if str(finding.get("tool")) == "zap":
            # Finding dong DA LA bang chung runtime.
            result.append(item)
            continue

        relative = str(finding.get("file_or_url") or "")
        route = extract_route(project_root / relative) if relative else None

        if not route:
            item["runtime_evidence"] = {
                "route": None,
                "route_source": None,
                "observed": None,
                "strength": "no_route",
                "dast_alerts": [],
            }
            result.append(item)
            continue

        matched = _route_matches(route, observed)
        alerts = sorted(set(alerts_by_path.get(matched, []))) if matched else []
        if matched and alerts:
            strength = "reachable_and_alerted"
        elif matched:
            strength = "reachable"
        else:
            strength = "route_known_not_reached"

        item["runtime_evidence"] = {
            "route": route,
            "route_source": relative,
            "observed": matched,
            "strength": strength,
            "dast_alerts": alerts,
        }
        result.append(item)
    return result


__all__ = ["STRENGTHS", "correlate", "extract_route", "parse_gateway_access_log"]
