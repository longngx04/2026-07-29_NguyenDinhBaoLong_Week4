"""
HTTP transport abstraction for Project Sentinel verification pipeline.
Provides BaseTransport interface and RealTransport (urllib with 64 KiB response cap and no auto-redirects).
"""

from abc import ABC, abstractmethod
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional

from .models import HttpRequest, HttpResponse

MAX_RESPONSE_BYTES = 65_536  # 64 KiB cap
MAX_TIMEOUT_SECONDS = 10.0


def _read_bounded(stream, max_response_bytes: int) -> bytearray:
    """Read no more than cap + one byte so truncation is detectable."""
    raw_bytes = bytearray()
    read_limit = max_response_bytes + 1
    while len(raw_bytes) < read_limit:
        chunk = stream.read(min(4096, read_limit - len(raw_bytes)))
        if not chunk:
            break
        raw_bytes.extend(chunk)
    return raw_bytes


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom HTTP redirect handler that disables auto-redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BaseTransport(ABC):
    """Abstract base transport interface."""

    @abstractmethod
    def send_request(self, request: HttpRequest) -> HttpResponse:
        """Send an HttpRequest and return a structured HttpResponse."""
        pass


class RealTransport(BaseTransport):
    """Real HTTP transport using standard library urllib.request."""

    def __init__(self, timeout_s: float = 5.0, max_response_bytes: int = MAX_RESPONSE_BYTES):
        if timeout_s <= 0 or timeout_s > MAX_TIMEOUT_SECONDS:
            raise ValueError(f"timeout_s must be between 0 and {MAX_TIMEOUT_SECONDS}")
        if max_response_bytes <= 0 or max_response_bytes > MAX_RESPONSE_BYTES:
            raise ValueError(f"max_response_bytes must be between 1 and {MAX_RESPONSE_BYTES}")
        self.timeout_s = timeout_s
        self.max_response_bytes = max_response_bytes
        self.opener = urllib.request.build_opener(NoRedirectHandler())

    def send_request(self, request: HttpRequest) -> HttpResponse:
        url = request.url
        if request.params:
            query = urllib.parse.urlencode(request.params)
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

        body_bytes: Optional[bytes] = None
        headers = dict(request.headers)
        if request.body is not None:
            body_bytes = request.body.encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers=headers,
            method=request.method.upper(),
        )

        timeout = min(self.timeout_s, MAX_TIMEOUT_SECONDS)

        start_time = time.monotonic()
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                status_code = resp.status
                resp_headers = dict(resp.headers)
                
                # Stream response body up to max_response_bytes + 1 to detect truncation
                raw_bytes = _read_bounded(resp, self.max_response_bytes)

                elapsed_ms = (time.monotonic() - start_time) * 1000.0
                total_observed = len(raw_bytes)
                truncated = total_observed > self.max_response_bytes
                
                if truncated:
                    body_preview = raw_bytes[: self.max_response_bytes].decode("utf-8", errors="replace")
                else:
                    body_preview = raw_bytes.decode("utf-8", errors="replace")

                return HttpResponse(
                    status_code=status_code,
                    headers=resp_headers,
                    body=body_preview,
                    response_bytes_observed=total_observed,
                    truncated=truncated,
                    elapsed_ms=round(elapsed_ms, 2),
                )
        except urllib.error.HTTPError as err:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            resp_headers = dict(err.headers) if err.headers else {}
            
            raw_bytes = _read_bounded(err.fp, self.max_response_bytes) if err.fp else bytearray()

            total_observed = len(raw_bytes)
            truncated = total_observed > self.max_response_bytes
            body_preview = (
                raw_bytes[: self.max_response_bytes].decode("utf-8", errors="replace")
                if truncated
                else raw_bytes.decode("utf-8", errors="replace")
            )

            return HttpResponse(
                status_code=err.code,
                headers=resp_headers,
                body=body_preview,
                response_bytes_observed=total_observed,
                truncated=truncated,
                elapsed_ms=round(elapsed_ms, 2),
                error_class="HTTPError",
                error_reason=f"HTTP {err.code}: {err.reason}",
            )
        except (TimeoutError, socket.timeout) as err:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            return HttpResponse(
                status_code=None,
                headers={},
                body="",
                response_bytes_observed=0,
                truncated=False,
                elapsed_ms=round(elapsed_ms, 2),
                error_class="TimeoutException",
                error_reason=str(err) or "Request timed out",
            )
        except urllib.error.URLError as err:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            reason_str = str(err.reason)
            timed_out = isinstance(err.reason, (TimeoutError, socket.timeout)) or "timed out" in reason_str.lower()
            return HttpResponse(
                status_code=None,
                headers={},
                body="",
                response_bytes_observed=0,
                truncated=False,
                elapsed_ms=round(elapsed_ms, 2),
                error_class="TimeoutException" if timed_out else "ConnectionError",
                error_reason=reason_str,
            )
        except Exception as err:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            is_timeout = isinstance(err, (TimeoutError, socket.timeout)) or "timeout" in err.__class__.__name__.lower()
            return HttpResponse(
                status_code=None,
                headers={},
                body="",
                response_bytes_observed=0,
                truncated=False,
                elapsed_ms=round(elapsed_ms, 2),
                error_class="TimeoutException" if is_timeout else err.__class__.__name__,
                error_reason="Request execution error",
            )
