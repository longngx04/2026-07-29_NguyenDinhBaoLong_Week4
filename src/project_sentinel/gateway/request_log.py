"""Secret-safe JSONL audit logging for verification executions."""

from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_sentinel.guardrails.redaction import redact_structure

AUDIT_FIELD_NAMES = {
    "request_id",
    "candidate_id",
    "objective_id",
    "proposal_id",
    "endpoint_id",
    "template_id",
    "method",
    "path",
    "payload_type",
    "status",
    "status_code",
    "elapsed_ms",
    "response_bytes_observed",
    "truncated",
    "response_preview",
    "error_class",
    "error_reason",
    "policy_decision",
}
MAX_AUDIT_PREVIEW_BYTES = 512


def log_request(log_path: str, **fields: Any) -> None:
    """Append one bounded audit record containing only the reviewed contract fields."""
    unknown_fields = set(fields).difference(AUDIT_FIELD_NAMES)
    if unknown_fields:
        raise ValueError(f"Unreviewed audit fields are forbidden: {sorted(unknown_fields)}")
    preview = fields.get("response_preview")
    if preview is not None and (
        not isinstance(preview, str)
        or len(preview.encode("utf-8")) > MAX_AUDIT_PREVIEW_BYTES
    ):
        raise ValueError("response_preview must be text bounded to 512 UTF-8 bytes")
    safe_fields, _ = redact_structure(dict(fields))
    preview_out = safe_fields.get("response_preview")
    if isinstance(preview_out, str):
        encoded = preview_out.encode("utf-8")
        if len(encoded) > MAX_AUDIT_PREVIEW_BYTES:
            safe_fields["response_preview"] = encoded[:MAX_AUDIT_PREVIEW_BYTES].decode(
                "utf-8", errors="ignore"
            )
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **safe_fields,
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Append co khoa, khong phai read-modify-replace.
    #
    # Cach cu doc ca file, ghi lai vao file tam, roi os.replace. Hai writer song
    # song deu doc cung mot ban cu, va writer sau ghi de mat ban ghi cua writer
    # truoc. Do that: ghi 100 ban ghi dong thoi, con lai 16.
    #
    # Audit log la bang chung cham diem va la thu duy nhat noi request nao da roi
    # he thong. Mot audit log mat 84% ban ghi te hon la khong co, vi no TRONG day du.
    #
    # O_APPEND cong voi khoa doc quyen: moi dong duoc ghi tron ven va khong ai ghi
    # de ai. Ban ghi luon nam gon duoi 4 KiB nen khong bi xe giua chung.
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
