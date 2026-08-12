"""
Abstract base prober interface and HTTP probe execution engine.
"""

from abc import ABC, abstractmethod
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from project_sentinel.verification.models import (
    VerificationPlan,
    VerificationProbe,
    VerificationResult,
    VerificationStatus,
)


class BaseProber(ABC):
    """
    Abstract interface for verification probe execution engines.
    """

    @abstractmethod
    def execute_plan(self, plan: VerificationPlan) -> VerificationResult:
        """
        Execute a verification plan and return a VerificationResult.
        """
        pass


class HTTPProber(BaseProber):
    """
    Safely executes non-destructive HTTP probes strictly within 127.0.0.1:8080 / localhost:8080 target boundary.
    """

    ALLOWED_PREFIXES = (
        "http://127.0.0.1:8080/",
        "http://localhost:8080/",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    )

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def _is_within_boundary(self, url: str) -> bool:
        if not url:
            return False
        url_str = url.strip()
        if not any(url_str.startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
            return False
        parsed = urllib.parse.urlparse(url_str)
        if parsed.scheme != "http" or parsed.netloc not in ("127.0.0.1:8080", "localhost:8080"):
            return False
        return True

    def execute_plan(self, plan: VerificationPlan) -> VerificationResult:
        start_time = time.perf_counter()

        if not self._is_within_boundary(plan.target_url):
            return VerificationResult(
                result_id=f"res-{plan.plan_id}",
                plan_id=plan.plan_id,
                group_id=plan.group_id,
                status=VerificationStatus.FAILED,
                status_code=None,
                evidence=f"Target URL '{plan.target_url}' violates boundary restriction (must start with http://127.0.0.1:8080/ or http://localhost:8080/). Probe aborted.",
                execution_time_ms=0.0,
            )

        probe = plan.probes[0] if plan.probes else VerificationProbe(probe_id="default", method="GET")

        target_url = plan.target_url
        if probe.params:
            parsed = urllib.parse.urlparse(target_url)
            query_dict = urllib.parse.parse_qs(parsed.query)
            for k, v in probe.params.items():
                query_dict[k] = [v]
            new_query = urllib.parse.urlencode(query_dict, doseq=True)
            target_url = urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
            )

        headers = dict(probe.headers) if probe.headers else {}
        if "User-Agent" not in headers:
            headers["User-Agent"] = "ProjectSentinel-HTTPProber/1.0"

        method = (probe.method or "GET").upper()
        req = urllib.request.Request(
            target_url,
            headers=headers,
            method=method,
        )

        status_code: Optional[int] = None
        body_text: str = ""

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_status = getattr(resp, "status", getattr(resp, "code", 200))
                status_code = int(raw_status) if raw_status is not None else 200
                body_bytes = resp.read()
                body_text = body_bytes.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            status_code = int(e.code) if e.code is not None else 500
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionRefusedError, OSError) as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return VerificationResult(
                result_id=f"res-{plan.plan_id}",
                plan_id=plan.plan_id,
                group_id=plan.group_id,
                status=VerificationStatus.UNREACHABLE,
                status_code=None,
                evidence=f"Target endpoint unreachable: {e}",
                execution_time_ms=round(elapsed_ms, 2),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return VerificationResult(
                result_id=f"res-{plan.plan_id}",
                plan_id=plan.plan_id,
                group_id=plan.group_id,
                status=VerificationStatus.FAILED,
                status_code=None,
                evidence=f"Probe execution error: {e}",
                execution_time_ms=round(elapsed_ms, 2),
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if probe.expected_indicator:
            if probe.expected_indicator in body_text:
                status = VerificationStatus.VERIFIED_REACHABLE
                evidence = f"HTTP {status_code} OK; matched expected indicator '{probe.expected_indicator}' in response body."
            elif status_code and 200 <= status_code < 400:
                status = VerificationStatus.VERIFIED_REACHABLE
                evidence = f"HTTP {status_code} received from target endpoint."
            else:
                status = VerificationStatus.INCONCLUSIVE
                evidence = f"HTTP {status_code} received (expected {probe.expected_status}), expected indicator '{probe.expected_indicator}' not found."
        else:
            if status_code and (status_code == probe.expected_status or 200 <= status_code < 400):
                status = VerificationStatus.VERIFIED_REACHABLE
                evidence = f"HTTP {status_code} received from target endpoint."
            else:
                status = VerificationStatus.UNREACHABLE
                evidence = f"HTTP {status_code} received (expected {probe.expected_status})."

        return VerificationResult(
            result_id=f"res-{plan.plan_id}",
            plan_id=plan.plan_id,
            group_id=plan.group_id,
            status=status,
            status_code=status_code,
            evidence=evidence,
            execution_time_ms=round(elapsed_ms, 2),
        )
