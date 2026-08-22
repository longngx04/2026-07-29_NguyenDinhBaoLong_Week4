import json
from pathlib import Path
import pytest
from project_sentinel.analysis.packet_builder import load_allowed_endpoints
from project_sentinel.analysis.prompt_builder import PromptBuilder
from project_sentinel.llm.base import AnalysisPacket

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"
SYSTEM_PROMPT_PATH = REPO_ROOT / "configs" / "prompts" / "security-analysis-system.md"


def test_packet_has_allowed_endpoints_field():
    packet = AnalysisPacket(group_key="g")
    assert packet.allowed_endpoints == []


def test_prompt_payload_carries_allowed_endpoints():
    packet = AnalysisPacket(
        group_key="g",
        allowed_endpoints=[{"method": "GET", "path": "/WebGoat/attack"}],
    )
    payload = PromptBuilder(system_prompt_path=SYSTEM_PROMPT_PATH).build(packet)
    assert payload.packet_dict["allowed_endpoints"] == [
        {"method": "GET", "path": "/WebGoat/attack"}
    ]


def test_prompt_hash_changes_when_allowlist_changes():
    builder = PromptBuilder(system_prompt_path=SYSTEM_PROMPT_PATH)
    one = builder.build(AnalysisPacket(group_key="g", allowed_endpoints=[]))
    two = builder.build(
        AnalysisPacket(
            group_key="g",
            allowed_endpoints=[{"method": "GET", "path": "/WebGoat/attack"}],
        )
    )
    assert one.prompt_sha256 != two.prompt_sha256


def test_system_prompt_forbids_inventing_endpoints():
    text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    assert "allowed_endpoints" in text
    assert "verification_objective" in text
    assert "null" in text, "Prompt phải nói rõ khi nào trả null"


def test_every_allowlist_entry_flattens_to_method_path_pairs():
    pairs = load_allowed_endpoints(ALLOWLIST_PATH)
    assert {
        "method": "GET",
        "path": "/WebGoat/actuator/health",
        "allowed_payload_kinds": [],
    } in pairs
    assert {
        "method": "GET",
        "path": "/WebGoat/login",
        "allowed_payload_kinds": [],
    } in pairs
    assert {
        "method": "GET",
        "path": "/WebGoat/attack",
        "allowed_payload_kinds": [],
    } in pairs
    assert {
        "method": "POST",
        "path": "/WebGoat/attack",
        "allowed_payload_kinds": ["empty_value", "long_string"],
    } in pairs
    assert len(pairs) == 4


def test_template_with_different_method_is_excluded(tmp_path):
    allowlist_file = tmp_path / "mismatched_allowlist.json"
    payload = {
        "endpoints": [
            {
                "path": "/WebGoat/test",
                "allowed_methods": ["GET"],
                "allowed_template_ids": ["tmpl_post_only"],
            }
        ],
        "templates": [
            {
                "template_id": "tmpl_post_only",
                "method": "POST",
                "payload_kind": "long_string",
            }
        ],
    }
    allowlist_file.write_text(json.dumps(payload), encoding="utf-8")
    pairs = load_allowed_endpoints(allowlist_file)
    assert pairs == [
        {"method": "GET", "path": "/WebGoat/test", "allowed_payload_kinds": []}
    ]


def test_load_allowed_endpoints_missing_file_returns_empty(tmp_path):
    missing_file = tmp_path / "non_existent_allowlist.json"
    pairs = load_allowed_endpoints(missing_file)
    assert pairs == []


def test_load_allowed_endpoints_corrupted_json_raises(tmp_path):
    corrupted_file = tmp_path / "corrupted.json"
    corrupted_file.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_allowed_endpoints(corrupted_file)


def test_load_allowed_endpoints_skips_none_or_empty_paths(tmp_path):
    allowlist_file = tmp_path / "allowlist_with_none.json"
    payload = {
        "endpoints": [
            {"path": None, "allowed_methods": ["GET"]},
            {"path": "", "allowed_methods": ["POST"]},
            {"path": "/WebGoat/valid", "allowed_methods": ["GET", None, ""]},
        ]
    }
    allowlist_file.write_text(json.dumps(payload), encoding="utf-8")
    pairs = load_allowed_endpoints(allowlist_file)
    assert pairs == [
        {"method": "GET", "path": "/WebGoat/valid", "allowed_payload_kinds": []}
    ]
    assert not any(p["path"] == "None" for p in pairs)


