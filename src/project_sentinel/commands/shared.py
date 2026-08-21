"""Tiện ích dùng chung giữa các handler lệnh."""

from __future__ import annotations

import json
from pathlib import Path

from project_sentinel.guardrails.approval import ApprovalRequest


def _confine_path(path: Path, allowed_parent_dir: Path, arg_name: str) -> Path:
    """Bảo đảm path nằm hẳn bên trong allowed_parent_dir, không có đường thoát."""
    allowed_parent = allowed_parent_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_parent)
    except ValueError:
        # `from None` có chủ ý: đây là một biên giới bảo mật. Lỗi gốc của
        # relative_to() mang theo đường dẫn đã resolve, và nối nó vào traceback
        # sẽ lộ cấu trúc thư mục thật cho người gây ra vi phạm.
        raise ValueError(
            f"Path confinement violation: {arg_name} ({path}) "
            f"must be located within {allowed_parent}"
        ) from None
    return resolved


def _read_approval_request(path: Path) -> ApprovalRequest:
    request_data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(request_data, dict):
        raise ValueError("approval-request.json không phải JSON object")
    request = ApprovalRequest(**request_data)
    if not request.request_fingerprint:
        raise ValueError("approval-request.json thiếu request_fingerprint hợp lệ")
    return request


__all__ = ["_confine_path", "_read_approval_request"]
