from project_sentinel.gateway.models import SafePayloadType
from project_sentinel.gateway.payloads import SAFE_PAYLOADS


def test_safe_payloads_keys():
    assert len(SAFE_PAYLOADS) == 4
    for payload_type in SafePayloadType:
        assert payload_type in SAFE_PAYLOADS


def test_safe_payloads_contain_no_dangerous_strings():
    dangerous_patterns = ["; rm", "DROP TABLE", "../../", "<script>"]
    for val in SAFE_PAYLOADS.values():
        if isinstance(val, str):
            for pattern in dangerous_patterns:
                assert pattern not in val
