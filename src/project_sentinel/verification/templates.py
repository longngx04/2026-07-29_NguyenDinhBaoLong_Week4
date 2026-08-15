"""Reviewed verification probe template registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from project_sentinel.gateway.models import SafePayloadType


@dataclass(frozen=True)
class ProbeTemplate:
    template_id: str
    endpoint_id: str
    method: str
    target_field: str | None
    payload_type: str | None
    expected_statuses: tuple[int, ...]


class ProbeTemplateRegistry:
    def __init__(self, templates: list[ProbeTemplate]):
        if not templates:
            raise ValueError("Probe template registry must not be empty")
        self._templates = {template.template_id: template for template in templates}
        if len(self._templates) != len(templates):
            raise ValueError("Duplicate probe template_id")

    @classmethod
    def from_json(cls, path: str | Path) -> "ProbeTemplateRegistry":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        raw_templates = data.get("templates")
        if not isinstance(raw_templates, list) or not raw_templates:
            raise ValueError(f"Probe template registry is empty or invalid: {source}")
        templates: list[ProbeTemplate] = []
        for raw in raw_templates:
            template_id = raw.get("template_id")
            endpoint_id = raw.get("endpoint_id")
            method = str(raw.get("method", "")).upper()
            target_field = raw.get("target_field")
            payload_type = raw.get("payload_type")
            expected_statuses = raw.get("expected_statuses")
            if (
                not isinstance(template_id, str)
                or not template_id
                or not isinstance(endpoint_id, str)
                or not endpoint_id
                or method not in {"GET", "POST"}
                or not isinstance(expected_statuses, list)
                or not expected_statuses
                or any(not isinstance(code, int) or code < 100 or code > 599 for code in expected_statuses)
            ):
                raise ValueError(f"Invalid probe template in {source}: {raw!r}")
            if method == "GET" and (target_field is not None or payload_type is not None):
                raise ValueError(f"GET template cannot contain a request body: {template_id}")
            if method == "POST" and (
                not isinstance(target_field, str)
                or not target_field
                or payload_type not in {item.value for item in SafePayloadType}
            ):
                raise ValueError(f"POST template requires a reviewed field and payload type: {template_id}")
            templates.append(
                ProbeTemplate(
                    template_id=template_id,
                    endpoint_id=endpoint_id,
                    method=method,
                    target_field=target_field,
                    payload_type=payload_type,
                    expected_statuses=tuple(expected_statuses),
                )
            )
        return cls(templates)

    def get(self, template_id: str) -> ProbeTemplate | None:
        return self._templates.get(template_id)
