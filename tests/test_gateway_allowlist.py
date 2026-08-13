import pytest
from project_sentinel.gateway.allowlist import Allowlist, AllowlistRule


def test_allowlist_exact_match_success(tmp_path):
    config_file = tmp_path / "allowlist.yaml"
    config_file.write_text(
        "allowlist:\n"
        "  - method: GET\n"
        "    path: /WebGoat/actuator/health\n"
        "    match: exact\n",
        encoding="utf-8",
    )
    allowlist = Allowlist.from_yaml(str(config_file))
    assert allowlist.is_allowed("GET", "/WebGoat/actuator/health") is True


def test_allowlist_exact_match_failure(tmp_path):
    config_file = tmp_path / "allowlist.yaml"
    config_file.write_text(
        "allowlist:\n"
        "  - method: GET\n"
        "    path: /WebGoat/actuator/health\n"
        "    match: exact\n",
        encoding="utf-8",
    )
    allowlist = Allowlist.from_yaml(str(config_file))
    assert allowlist.is_allowed("GET", "/WebGoat/actuator/health/extra") is False


def test_allowlist_prefix_match_success(tmp_path):
    config_file = tmp_path / "allowlist.yaml"
    config_file.write_text(
        "allowlist:\n"
        "  - method: POST\n"
        "    path: /WebGoat/attack\n"
        "    match: prefix\n",
        encoding="utf-8",
    )
    allowlist = Allowlist.from_yaml(str(config_file))
    assert allowlist.is_allowed("POST", "/WebGoat/attack/lesson1") is True


def test_allowlist_method_mismatch(tmp_path):
    config_file = tmp_path / "allowlist.yaml"
    config_file.write_text(
        "allowlist:\n"
        "  - method: GET\n"
        "    path: /WebGoat/actuator/health\n"
        "    match: exact\n",
        encoding="utf-8",
    )
    allowlist = Allowlist.from_yaml(str(config_file))
    assert allowlist.is_allowed("POST", "/WebGoat/actuator/health") is False


def test_allowlist_empty_file_raises_error(tmp_path):
    config_file = tmp_path / "empty_allowlist.yaml"
    config_file.write_text("allowlist: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Allowlist.from_yaml(str(config_file))
