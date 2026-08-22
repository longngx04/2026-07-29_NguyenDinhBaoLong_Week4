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


def test_every_advertised_payload_kind_is_accepted_by_validate_objective():
    """Bất biến: Mọi payload_kind được quảng bá trong allowed_endpoints đều PHẢI được validator chấp nhận."""
    from project_sentinel.gateway.allowlist import Allowlist
    from project_sentinel.probe.proposal import validate_objective

    allowlist = Allowlist.from_json(ALLOWLIST_PATH)
    entries = load_allowed_endpoints(ALLOWLIST_PATH)

    for entry in entries:
        method = entry["method"]
        path = entry["path"]
        for kind in entry["allowed_payload_kinds"]:
            objective = {
                "description": "test probe",
                "endpoint_hint": f"{method} {path}",
                "payload_kind": kind,
                "rationale": "test invariant",
            }
            decision = validate_objective(objective, allowlist)
            assert decision.accepted is True, (
                f"Advertised combination '{method} {path}' with kind '{kind}' was rejected: {decision.reason}"
            )


def test_get_entries_have_no_allowed_payload_kinds():
    """Tất cả các endpoint GET trong packet đều phải có allowed_payload_kinds là danh sách rỗng."""
    entries = load_allowed_endpoints(ALLOWLIST_PATH)
    get_entries = [e for e in entries if e["method"] == "GET"]
    assert get_entries, "Phải có ít nhất một GET entry"
    for entry in get_entries:
        assert entry["allowed_payload_kinds"] == [], (
            f"GET {entry['path']} không được phép có allowed_payload_kinds: {entry['allowed_payload_kinds']}"
        )


def test_unadvertised_payload_kind_is_rejected_by_validate_objective():
    """Một kind không nằm trong allowed_payload_kinds phải bị validate_objective từ chối."""
    from project_sentinel.gateway.allowlist import Allowlist
    from project_sentinel.probe.proposal import validate_objective

    allowlist = Allowlist.from_json(ALLOWLIST_PATH)
    # POST /WebGoat/attack only allows empty_value and long_string
    objective = {
        "description": "test probe",
        "endpoint_hint": "POST /WebGoat/attack",
        "payload_kind": "special_chars",
        "rationale": "test rejection",
    }
    decision = validate_objective(objective, allowlist)
    assert decision.accepted is False
    assert "chưa được review" in decision.reason


def test_system_prompt_never_instructs_null_payload_kind():
    """Prompt không được chứa bất kỳ câu nào bảo đặt payload_kind là null."""
    import re

    text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    assert not re.search(r"payload_kind.{0,40}null", text, re.IGNORECASE), (
        "Prompt contains instruction suggesting payload_kind can be null"
    )



def test_template_with_different_method_is_excluded(tmp_path):
    allowlist_file = tmp_path / "mismatched_allowlist.json"
    payload = {
        "schema_version": "1.0",
        "endpoints": [
            {
                "endpoint_id": "ep_post_test",
                "path": "/WebGoat/test",
                "allowed_methods": ["POST"],
                "allowed_template_ids": ["tmpl_get_only", "tmpl_post_empty"],
            }
        ],
        "templates": [
            {
                "template_id": "tmpl_get_only",
                "method": "GET",
                "payload_kind": None,
            },
            {
                "template_id": "tmpl_post_empty",
                "method": "POST",
                "payload_kind": "empty_value",
            },
        ],
    }
    allowlist_file.write_text(json.dumps(payload), encoding="utf-8")
    pairs = load_allowed_endpoints(allowlist_file)
    assert pairs == [
        {
            "method": "POST",
            "path": "/WebGoat/test",
            "allowed_payload_kinds": ["empty_value"],
        }
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


def test_load_allowed_endpoints_invalid_schema_raises(tmp_path):
    allowlist_file = tmp_path / "allowlist_with_none.json"
    payload = {
        "schema_version": "1.0",
        "endpoints": [
            {"endpoint_id": "ep_1", "path": None, "allowed_methods": ["GET"]},
        ],
    }
    allowlist_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_allowed_endpoints(allowlist_file)



