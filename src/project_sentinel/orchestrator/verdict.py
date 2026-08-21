"""Probe vừa gửi kết luận được gì về finding — nói bằng đúng ba từ.

Bối cảnh. Lần chạy `20260821T045519Z` gửi `GET /WebGoat/login`, nhận HTTP 200,
và báo cáo in kết quả đó ngay dưới danh sách 20 finding SQL Injection. Không
dòng nào nói rằng endpoint ấy chẳng liên quan gì tới các finding đó. Người đọc
nhanh sẽ hiểu là lỗ hổng đã được kiểm chứng.

Module này chặn cách hiểu đó bằng một phân loại xác định:

- `supports`   — response mang đúng dấu hiệu đã khai trước.
- `refutes`    — dấu hiệu đã khai trước không xuất hiện.
- `inconclusive` — mọi trường hợp còn lại. Đây là kết quả mặc định và, với cấu
  hình hiện tại, cũng là kết quả gần như duy nhất. Đó là câu trả lời trung thực.

Nguyên tắc: một request chỉ được coi là bằng chứng cho finding khi nó **gắn với
finding đó** và **endpoint được nhắc tới trong chính bằng chứng của finding**.
HTTP 200 tự nó không phải bằng chứng cho bất cứ điều gì.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VERDICTS: frozenset[str] = frozenset({"supports", "refutes", "inconclusive"})

# Vì sao chưa kết luận được. Mỗi giá trị ứng với đúng một nhánh bên dưới.
EVIDENCE_KINDS: frozenset[str] = frozenset(
    {
        "none",               # không có request nào được gửi
        "not_linked",         # request không gắn với finding nào
        "unrelated_endpoint", # endpoint không xuất hiện trong bằng chứng của finding
        "no_declared_signal", # có liên quan nhưng không khai trước dấu hiệu cần quan sát
        "declared_signal",    # đủ điều kiện để kết luận
    }
)

# `source_analysis_id` mang giá trị này khi người vận hành tự chỉ định request.
OPERATOR_OVERRIDE = "operator-override"


@dataclass(frozen=True)
class ProbeVerdict:
    verdict: str
    reason: str
    evidence_kind: str
    analysis_id: str | None = None
    source_finding_ids: tuple[str, ...] = ()
    probed_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "evidence_kind": self.evidence_kind,
            "analysis_id": self.analysis_id,
            "source_finding_ids": list(self.source_finding_ids),
            "probed_path": self.probed_path,
        }


def _inconclusive(reason: str, evidence_kind: str, **extra: Any) -> ProbeVerdict:
    return ProbeVerdict(
        verdict="inconclusive", reason=reason, evidence_kind=evidence_kind, **extra
    )


def _linked_record(
    analyses: Any, analysis_id: str | None
) -> dict[str, Any] | None:
    if not analysis_id or not isinstance(analyses, list):
        return None
    for entry in analyses:
        if isinstance(entry, dict) and entry.get("analysis_id") == analysis_id:
            return entry
    return None


def _evidence_text(record: dict[str, Any]) -> str:
    """Gom mọi văn bản bằng chứng của một finding thành một chuỗi để dò.

    Cố ý KHÔNG gom `objective.rationale`: đó là văn của Agent, không phải bằng
    chứng. Nếu tính cả nó thì Agent chỉ cần viết tên endpoint vào rationale là
    tự phong cho request của mình tư cách bằng chứng.
    """
    parts: list[str] = []
    evidence = record.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            for key in ("content", "path"):
                value = item.get(key)
                if isinstance(value, str):
                    parts.append(value)
    for key in ("explanation", "title"):
        value = record.get(key)
        if isinstance(value, str):
            parts.append(value)
    locations = record.get("locations")
    if isinstance(locations, list):
        for location in locations:
            if isinstance(location, dict) and isinstance(location.get("file"), str):
                parts.append(location["file"])
    return "\n".join(parts)


def _finding_ids(record: dict[str, Any]) -> tuple[str, ...]:
    ids = record.get("source_finding_ids")
    if not isinstance(ids, list):
        return ()
    return tuple(str(item) for item in ids if isinstance(item, str) and item)


def decide_verdict(
    *, proposal: Any, probe: Any, analyses: Any
) -> ProbeVerdict:
    """Phân loại kết quả probe so với finding mà nó được cho là kiểm chứng."""
    if not isinstance(proposal, dict) or not isinstance(probe, dict):
        return _inconclusive(
            "Không đọc được proposal hoặc probe-result của lần chạy này.", "none"
        )

    if not probe.get("sent"):
        reason = probe.get("denied_reason") or "không có request nào được gửi"
        return _inconclusive(
            f"Không có bằng chứng từ ứng dụng: {reason}.", "none"
        )

    probe_spec = proposal.get("probe")
    probed_path = (
        probe_spec.get("path") if isinstance(probe_spec, dict) else None
    )

    analysis_id = proposal.get("source_analysis_id")
    if proposal.get("operator_override") or analysis_id == OPERATOR_OVERRIDE:
        return _inconclusive(
            "Request do người vận hành chỉ định, không gắn với finding nào, "
            "nên không khẳng định hay bác bỏ được lỗ hổng nào.",
            "not_linked",
            probed_path=probed_path,
        )

    record = _linked_record(analyses, analysis_id)
    if record is None:
        return _inconclusive(
            "Đề xuất không trỏ tới một finding có thật trong analysis.jsonl.",
            "not_linked",
            probed_path=probed_path,
        )

    finding_ids = _finding_ids(record)

    if not probed_path or probed_path not in _evidence_text(record):
        return _inconclusive(
            f"Endpoint `{probed_path}` không nằm trong bằng chứng của finding "
            f"`{analysis_id}`, nên mã trạng thái trả về không nói gì về lỗ hổng đó.",
            "unrelated_endpoint",
            analysis_id=analysis_id,
            source_finding_ids=finding_ids,
            probed_path=probed_path,
        )

    objective = proposal.get("objective")
    signal = (
        objective.get("expected_signal") if isinstance(objective, dict) else None
    )
    if not isinstance(signal, str) or not signal.strip():
        return _inconclusive(
            "Đề xuất không khai trước dấu hiệu cần quan sát, nên response quan sát "
            "được không đủ để kết luận theo hướng nào.",
            "no_declared_signal",
            analysis_id=analysis_id,
            source_finding_ids=finding_ids,
            probed_path=probed_path,
        )

    body = probe.get("body_preview")
    body = body if isinstance(body, str) else ""
    if signal in body:
        return ProbeVerdict(
            verdict="supports",
            reason=f"Response chứa dấu hiệu đã khai trước: `{signal}`.",
            evidence_kind="declared_signal",
            analysis_id=analysis_id,
            source_finding_ids=finding_ids,
            probed_path=probed_path,
        )

    return ProbeVerdict(
        verdict="refutes",
        reason=(
            f"Dấu hiệu đã khai trước `{signal}` không xuất hiện trong response "
            "quan sát được."
        ),
        evidence_kind="declared_signal",
        analysis_id=analysis_id,
        source_finding_ids=finding_ids,
        probed_path=probed_path,
    )


__all__ = ["VERDICTS", "EVIDENCE_KINDS", "ProbeVerdict", "decide_verdict"]
