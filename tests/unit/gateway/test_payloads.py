from project_sentinel.gateway.models import SafePayloadType
from project_sentinel.gateway.payloads import SAFE_PAYLOADS


def test_safe_payloads_are_bounded_and_non_exploitative():
    assert set(SAFE_PAYLOADS) == set(SafePayloadType)
    assert len(SAFE_PAYLOADS[SafePayloadType.LONG_STRING].encode("utf-8")) <= 1024
    serialized = repr(SAFE_PAYLOADS.values())
    for pattern in ("DROP TABLE", "../../", "<script>", "; rm"):
        assert pattern not in serialized
