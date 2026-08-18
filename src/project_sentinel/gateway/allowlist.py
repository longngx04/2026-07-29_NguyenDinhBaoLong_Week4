"""Version-controlled, deny-by-default endpoint inventory."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AllowlistRule:
    method: str
    path: str
    match: str = "exact"
    endpoint_id: str = ""
    allowed_template_ids: tuple[str, ...] = ()
    allowed_request_headers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    max_response_bytes: int = 65_536


class Allowlist:
    def __init__(self, rules: list[AllowlistRule]):
        if not rules:
            raise ValueError("Endpoint allowlist must not be empty")
        if any(rule.match != "exact" for rule in rules):
            raise ValueError("Endpoint rules must use exact path matching")
        self._rules = rules

    @classmethod
    def from_json(cls, path: str | Path) -> "Allowlist":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        endpoints = data.get("endpoints")
        if not isinstance(endpoints, list) or not endpoints:
            raise ValueError(f"Endpoint allowlist is empty or invalid: {source}")

        rules: list[AllowlistRule] = []
        seen_ids: set[str] = set()
        for endpoint in endpoints:
            endpoint_id = endpoint.get("endpoint_id")
            path_value = endpoint.get("path")
            methods = endpoint.get("allowed_methods")
            template_ids = endpoint.get("allowed_template_ids")
            headers_policy = endpoint.get("allowed_request_headers") or {}
            if (
                not isinstance(endpoint_id, str)
                or not endpoint_id
                or endpoint_id in seen_ids
                or not isinstance(path_value, str)
                or not path_value.startswith("/")
                or "?" in path_value
                or not isinstance(methods, list)
                or not methods
                or not isinstance(template_ids, list)
                or not template_ids
            ):
                raise ValueError(f"Invalid endpoint entry in {source}: {endpoint!r}")
            seen_ids.add(endpoint_id)
            max_response_bytes = endpoint.get("max_response_bytes", 65_536)
            if (
                not isinstance(max_response_bytes, int)
                or max_response_bytes <= 0
                or max_response_bytes > 65_536
                or any(not isinstance(item, str) or not item for item in template_ids)
            ):
                raise ValueError(f"Invalid endpoint resource limits/templates: {endpoint!r}")

            parsed_headers: dict[str, tuple[str, ...]] = {}
            if isinstance(headers_policy, dict):
                for h_name, h_vals in headers_policy.items():
                    if isinstance(h_name, str) and isinstance(h_vals, list):
                        parsed_headers[h_name.casefold()] = tuple(str(v) for v in h_vals if isinstance(v, str))

            for method in methods:
                normalized_method = str(method).upper()
                if normalized_method not in {"GET", "POST"}:
                    raise ValueError(f"Unsupported method: {method}")
                rules.append(
                    AllowlistRule(
                        endpoint_id=endpoint_id,
                        method=normalized_method,
                        path=path_value,
                        allowed_template_ids=tuple(str(item) for item in template_ids),
                        allowed_request_headers=parsed_headers,
                        max_response_bytes=max_response_bytes,
                    )
                )
        return cls(rules)

    def get_rule(self, endpoint_id: str, method: str) -> AllowlistRule | None:
        normalized_method = method.upper()
        return next(
            (
                rule
                for rule in self._rules
                if rule.endpoint_id == endpoint_id and rule.method == normalized_method
            ),
            None,
        )

    def is_allowed(
        self,
        method: str,
        path: str,
        *,
        endpoint_id: str | None = None,
        template_id: str | None = None,
    ) -> bool:
        normalized_method = method.upper()
        for rule in self._rules:
            if rule.method != normalized_method or rule.path != path:
                continue
            if endpoint_id is not None and rule.endpoint_id != endpoint_id:
                continue
            if template_id is not None and template_id not in rule.allowed_template_ids:
                continue
            return True
        return False
