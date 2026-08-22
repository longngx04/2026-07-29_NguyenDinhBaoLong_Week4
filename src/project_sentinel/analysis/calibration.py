"""Hiệu chỉnh kết luận của Agent theo bằng chứng, quyết định phía Python.

Vì sao cần tầng này. Trong lần chạy `20260821T045519Z`, Agent xuất 20/20 record
ở mức `high`, trong đó có những record mà chính phần giải thích của nó viết
"không có lỗ hổng SQL Injection rõ ràng tại vị trí này". Validator provenance
không bắt được: mọi ID, vị trí và CWE đều có thật, chỉ có *kết luận* là quá tay.

Tầng này áp luật lên chính output đó, không hỏi lại Agent. Nguyên tắc:

- **Chỉ hạ dựa trên văn xuôi của Agent.** Mọi luật đọc output của Agent chỉ
  được hạ cấp; một luật sai chỉ làm mất độ nhạy, không bao giờ tự tạo ra một
  "confirmed" giả.
- **Trường ĐO ĐƯỢC thì lấy số đo, cả khi số đo cao hơn.** `reachability` không
  còn là thứ Agent được phép tự khai: `correlation.py` tính nó bằng cách đối
  chiếu route khai trong source với endpoint ZAP thật sự chạm tới. Đây không
  phải nâng kết luận của Agent — đây là thay một lời khai bằng một phép đo.
  Cùng lý do khối `calibration` do Agent tự sinh bị bỏ đi.
- **Xác định.** Cùng input cho cùng output, không phụ thuộc model hay nhiệt độ.
- **Ghi vết.** Mọi lần hiệu chỉnh để lại khối `calibration` nói rõ luật nào chạy
  và đã đổi gì, để người đọc báo cáo truy ngược được.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SEVERITY_ORDER: tuple[str, ...] = ("info", "low", "medium", "high", "critical")

DISPOSITIONS: frozenset[str] = frozenset(
    {"confirmed", "likely", "needs_review", "false_positive"}
)
PROOF_VALUES: frozenset[str] = frozenset({"proven", "not_proven", "not_applicable"})

# Trần severity cho từng kết luận. Thiếu bằng chứng khai thác thì không được
# chiếm mức cao trong danh sách ưu tiên của người đọc báo cáo.
SEVERITY_CEILING: dict[str, str] = {
    "confirmed": "critical",
    "likely": "high",
    "needs_review": "medium",
    "false_positive": "info",
}

# Các cụm cho thấy Agent tự phủ nhận lỗ hổng ngay trong văn xuôi. Danh sách được
# giữ hẹp và bảo thủ: khớp nhầm chỉ làm một finding bị hạ xuống needs_review,
# không bao giờ làm một finding thật bị bỏ qua.
_DENIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"không có lỗ hổng[^.]{0,40}rõ ràng", re.IGNORECASE),
    re.compile(r"truy vấn (?:sql )?(?:là )?tĩnh", re.IGNORECASE),
    re.compile(r"câu lệnh sql[^.]{0,30}tĩnh", re.IGNORECASE),
    re.compile(r"không có dữ liệu (?:người dùng|đầu vào)[^.]{0,40}nối", re.IGNORECASE),
    re.compile(r"không có tham số hay chuỗi được nối", re.IGNORECASE),
    re.compile(r"static(?:ally)?[ -]?(?:hardcoded )?(?:sql )?quer(?:y|ies)", re.IGNORECASE),
    re.compile(r"no user[- ]controlled input", re.IGNORECASE),
    re.compile(r"no user input", re.IGNORECASE),
)

# Chỉ hai kết luận này mới có gì để hạ khi văn xuôi phủ nhận.
_DISPOSITIONS_OPEN_TO_DENIAL: frozenset[str] = frozenset({"confirmed", "likely"})

_PROSE_FIELDS: tuple[str, ...] = ("explanation", "confidence_rationale")


@dataclass
class Calibration:
    """Những gì Python đã sửa trên output của Agent, và vì sao."""

    rules: list[str] = field(default_factory=list)
    severity_from: str | None = None
    severity_to: str | None = None
    disposition_from: str | None = None
    disposition_to: str | None = None

    @property
    def applied(self) -> bool:
        return bool(self.rules)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rules": list(self.rules),
            "severity_from": self.severity_from,
            "severity_to": self.severity_to,
            "disposition_from": self.disposition_from,
            "disposition_to": self.disposition_to,
        }


def _cap(severity: str, ceiling: str) -> str:
    """Trả về mức thấp hơn giữa severity và trần. Mức lạ thì trả nguyên."""
    if severity not in SEVERITY_ORDER or ceiling not in SEVERITY_ORDER:
        return severity
    if SEVERITY_ORDER.index(severity) <= SEVERITY_ORDER.index(ceiling):
        return severity
    return ceiling


def _denies_the_vulnerability(record: dict[str, Any]) -> bool:
    for name in _PROSE_FIELDS:
        text = record.get(name)
        if not isinstance(text, str):
            continue
        if any(pattern.search(text) for pattern in _DENIAL_PATTERNS):
            return True
    return False


def calibrate_record(
    record: dict[str, Any], *, measured_reachability: str | None = None
) -> tuple[dict[str, Any], Calibration]:
    """Áp luật hiệu chỉnh lên một record, trả về (record mới, vết hiệu chỉnh).

    Record đầu vào không bị sửa tại chỗ. Khối `calibration` do Agent tự khai
    (nếu có) bị bỏ đi trước khi chạy: đây là kết luận của Python, không phải
    thứ Agent được phép tự nhận.
    """
    if not isinstance(record, dict):
        return record, Calibration()

    result = dict(record)
    result.pop("calibration", None)
    calibration = Calibration()

    disposition = result.get("disposition")
    severity = result.get("severity")
    attacker_control = result.get("attacker_control")
    reachability = result.get("reachability")

    # Phép đo thắng lời khai. Giá trị lạ thì bỏ qua, không ghi bừa vào record.
    if measured_reachability in PROOF_VALUES and measured_reachability != reachability:
        result["reachability"] = measured_reachability
        reachability = measured_reachability
        calibration.rules.append("reachability_measured")


    if disposition not in DISPOSITIONS:
        # Không có kết luận hợp lệ thì không có gì để hiệu chỉnh theo. Schema
        # đã chặn ở tầng trước; ở đây chỉ cần không làm sập lần chạy.
        return result, calibration

    original_disposition = disposition
    original_severity = severity

    # Chưa có phép đo độc lập cho attacker_control: hạ mọi lời tự khai "proven"
    # xuống "not_proven" để tránh cấp "confirmed" giả dựa trên hallucination của LLM.
    # Khi nào hệ thống có measured_attacker_control thì thay bằng phép đo thật.
    if attacker_control == "proven":
        attacker_control = "not_proven"
        result["attacker_control"] = "not_proven"
        calibration.rules.append("attacker_control_unverifiable")

    # Luật 1 — "confirmed" đòi cả attacker control lẫn reachability được chứng minh.
    if disposition == "confirmed" and not (
        attacker_control == "proven" and reachability == "proven"
    ):
        disposition = "needs_review"
        calibration.rules.append("confirmed_requires_proof")

    # Luật 2 — văn xuôi phủ nhận lỗ hổng thì kết luận không được ở mức khẳng định.
    if disposition in _DISPOSITIONS_OPEN_TO_DENIAL and _denies_the_vulnerability(result):
        disposition = "needs_review"
        if "prose_contradicts_disposition" not in calibration.rules:
            calibration.rules.append("prose_contradicts_disposition")

    # Luật 3 — trần severity theo kết luận cuối cùng.
    if isinstance(severity, str):
        capped = _cap(severity, SEVERITY_CEILING[disposition])
        if capped != severity:
            severity = capped
            calibration.rules.append("severity_ceiling_for_disposition")

        # Luật 4 — chưa chứng minh được attacker control thì không quá `medium`,
        # kể cả khi kết luận vẫn là "likely".
        if attacker_control == "not_proven":
            capped = _cap(severity, "medium")
            if capped != severity:
                severity = capped
                calibration.rules.append("attacker_control_not_proven")

    if disposition != original_disposition:
        calibration.disposition_from = original_disposition
        calibration.disposition_to = disposition
        result["disposition"] = disposition

    if severity != original_severity:
        calibration.severity_from = original_severity
        calibration.severity_to = severity
        result["severity"] = severity

    if calibration.applied:
        result["calibration"] = calibration.as_dict()

    return result, calibration


__all__ = [
    "SEVERITY_ORDER",
    "DISPOSITIONS",
    "PROOF_VALUES",
    "SEVERITY_CEILING",
    "Calibration",
    "calibrate_record",
]
