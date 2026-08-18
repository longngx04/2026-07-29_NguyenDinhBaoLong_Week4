import json
from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist


def test_versioned_allowlist_uses_exact_method_and_path():
    allowlist = Allowlist.from_json("configs/gateway/endpoint-allowlist.json")
    assert allowlist.is_allowed("GET", "/WebGoat/actuator/health", endpoint_id="ep_health", template_id="tmpl_health_get")
    assert not allowlist.is_allowed("POST", "/WebGoat/actuator/health")
    assert not allowlist.is_allowed("GET", "/WebGoat/attack/lesson1")


def test_empty_allowlist_fails_closed(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"endpoints": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        Allowlist.from_json(path)

