"""In ra cách Python Tool ánh xạ một HTTP 429 của Gateway.

Trước đây phần này gọi `project_sentinel.verification.gateway_client` — package đã
bị xoá khi kiến trúc chuyển sang `probe/`. Nay dùng đúng `send_probe`, tức chính
đường mà mọi request thật đi qua, chứ không phải một đường riêng cho demo.

In một trong hai dòng: `RATE_LIMITED:429` hoặc `SENT:<mã>`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from project_sentinel.gateway.allowlist import Allowlist  # noqa: E402
from project_sentinel.probe.proposal import SafeProbe  # noqa: E402
from project_sentinel.probe.rate_limit import ToolRateLimiter  # noqa: E402
from project_sentinel.probe.tool import send_probe  # noqa: E402


def main() -> int:
    api_key = os.environ.get("SENTINEL_GATEWAY_API_KEY", "")
    if not api_key:
        print("MISSING_KEY:0")
        return 1

    allowlist = Allowlist.from_json(REPO_ROOT / "configs/gateway/endpoint-allowlist.json")
    probe = SafeProbe("GET", "/WebGoat/actuator/health", None)

    # Tat rate limiter phia client de request that su cham toi Gateway va bi
    # Gateway tu choi — day la bai kiem ve gioi han o TANG HA TANG, khong phai ve
    # bo dem trong Python.
    unlimited = ToolRateLimiter(requests_per_minute=100_000, burst=1_000)

    outcome = None
    for _ in range(12):
        outcome = send_probe(
            probe,
            allowlist,
            api_key,
            rate_limiter=unlimited,
            log_path=None,
            events_path=None,
        )
        if outcome.status_code == 429:
            print("RATE_LIMITED:429")
            return 0

    code = outcome.status_code if outcome else "none"
    print(f"SENT:{code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
