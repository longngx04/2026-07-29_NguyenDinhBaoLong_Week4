from __future__ import annotations
import time
import httpx
from .allowlist import Allowlist
from .models import GatewayResult, GatewayErrorType, SafePayloadType
from .payloads import SAFE_PAYLOADS
from .request_log import log_request


class GatewayClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        allowlist: Allowlist,
        log_path: str,
        timeout_s: float = 5.0,
        max_response_bytes: int = 65_536,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._allowlist = allowlist
        self._log_path = log_path
        self._timeout = timeout_s
        self._max_bytes = max_response_bytes

    def request(
        self,
        method: str,
        path: str,
        payload_type: SafePayloadType | None = None,
        target_field: str | None = None,
    ) -> GatewayResult:
        if not self._allowlist.is_allowed(method, path):
            log_request(
                self._log_path,
                method,
                path,
                payload_type.value if payload_type else None,
                None,
                GatewayErrorType.FORBIDDEN_BY_ALLOWLIST,
                0.0,
            )
            return GatewayResult(
                False, None, None, GatewayErrorType.FORBIDDEN_BY_ALLOWLIST, 0.0
            )

        body = None
        if payload_type is not None and target_field is not None:
            body = {target_field: SAFE_PAYLOADS[payload_type]}

        headers = {"X-Sentinel-Key": self._api_key}
        start = time.monotonic()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                with client.stream(
                    method, f"{self._base_url}{path}", headers=headers, json=body
                ) as resp:
                    chunks, total = [], 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > self._max_bytes:
                            chunks.append(
                                chunk[: max(0, self._max_bytes - (total - len(chunk)))]
                            )
                            break
                        chunks.append(chunk)
                    preview = b"".join(chunks).decode("utf-8", errors="replace")
                    elapsed = (time.monotonic() - start) * 1000
                    log_request(
                        self._log_path,
                        method,
                        path,
                        payload_type.value if payload_type else None,
                        resp.status_code,
                        None,
                        elapsed,
                    )
                    return GatewayResult(
                        resp.status_code < 400,
                        resp.status_code,
                        preview,
                        None,
                        elapsed,
                    )
        except httpx.TimeoutException:
            elapsed = (time.monotonic() - start) * 1000
            log_request(
                self._log_path,
                method,
                path,
                payload_type.value if payload_type else None,
                None,
                GatewayErrorType.TIMEOUT,
                elapsed,
            )
            return GatewayResult(False, None, None, GatewayErrorType.TIMEOUT, elapsed)
        except (httpx.ConnectError, httpx.NetworkError):
            elapsed = (time.monotonic() - start) * 1000
            log_request(
                self._log_path,
                method,
                path,
                payload_type.value if payload_type else None,
                None,
                GatewayErrorType.CONNECTION,
                elapsed,
            )
            return GatewayResult(False, None, None, GatewayErrorType.CONNECTION, elapsed)
