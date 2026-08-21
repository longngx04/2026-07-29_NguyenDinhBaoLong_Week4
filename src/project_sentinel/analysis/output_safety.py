"""Chặn payload khai thác trong chính output của Agent.

System prompt cấm rõ: không exploit payload, không destructive request, không shell
command, chỉ đề xuất code review / unit test / kiểm chứng không phá huỷ. Nhưng prompt
là lời dặn, không phải ràng buộc — và Agent đã vi phạm nó. Artifact đã commit chứa
`'; DROP TABLE employees --'` và `ping localhost; id`.

Safe Probe không bao giờ thực thi các chuỗi đó, nên chúng chưa từng chạm tới WebGoat.
Nhưng `analysis.jsonl` và `report.md` LÀ deliverable: chúng được người đọc, được
copy-paste, được nộp cho mentor. Một hướng dẫn `DROP TABLE` trong báo cáo bảo mật là
output không đạt, bất kể downstream có chặn hay không.

**Chỉ quét field do Agent viết.** `evidence` chứa mã nguồn WebGoat nguyên văn, và
WebGoat cố ý để sẵn chuỗi tấn công trong comment (`// The answer: Smith' union
select ...`). Quét cả evidence sẽ đánh trượt mọi record hợp lệ.
"""

from __future__ import annotations

import re
from typing import Any

# Field do AGENT viet. `evidence` co chu y KHONG nam trong danh sach nay.
AGENT_AUTHORED_FIELDS: tuple[str, ...] = (
    "explanation",
    "confidence_rationale",
    "preconditions",
    "verification_steps",
    "remediation",
    "limitations",
)

# Field cua verification_objective, cung do Agent viet.
OBJECTIVE_FIELDS: tuple[str, ...] = (
    "description",
    "rationale",
    "expected_signal",
)

_UNSAFE: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Lenh SQL pha huy du lieu.
    (
        "destructive_sql",
        re.compile(r"\b(?:DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    ),
    (
        "destructive_sql",
        re.compile(r"\bDELETE\s+FROM\b(?![^.]{0,80}\bWHERE\s+\w+\s*=\s*[?:])", re.IGNORECASE),
    ),
    # Thu thuat noi lenh he dieu hanh.
    ("shell_command", re.compile(r"\brm\s+-[rf]{1,2}\b", re.IGNORECASE)),
    ("shell_command", re.compile(r"\bxp_cmdshell\b", re.IGNORECASE)),
    ("shell_command", re.compile(r"[;&|]\s*(?:id|whoami|uname|cat|curl|wget|nc)\b")),
    ("shell_command", re.compile(r"\$\([^)]{1,80}\)")),
    # Backtick trong van xuoi ky thuat gan nhu luon la code span cua Markdown
    # (`kid`, `accountName`, `statement.executeQuery(query)`), khong phai command
    # substitution cua shell. Chi bao dong khi noi dung trong backtick THAT SU
    # trong nhu mot loi goi shell: bat dau bang mot binary nguy hiem, hoac chua
    # dau noi lenh. Khong thu hep cho nay thi 17/21 record hop le bi danh truot.
    (
        "shell_command",
        re.compile(
            # `whoami`/`uname` co trong danh sach vi chung khong phai ten bien hop
            # ly trong van xuoi cua codebase nay. `id` va `cat` CO THE la ten
            # truong, nen chung khong o day — chung da duoc bat boi luat dau noi
            # lenh ([;&|] id) o tren, la tin hieu that.
            r"`\s*(?:sh|bash|zsh|cmd|powershell|curl|wget|nc|ncat|netcat|python|perl"
            r"|ruby|php|eval|exec|system|whoami|uname|xp_cmdshell)\b[^`\n]*`",
            re.IGNORECASE,
        ),
    ),
    ("shell_command", re.compile(r"`[^`\n]*(?:;\s*\w+|&&|\|\|)[^`\n]*`")),
    # Payload SQL injection kinh dien.
    (
        "sql_injection_payload",
        re.compile(r"'\s*(?:OR|AND)\s*'?\d*'?\s*=\s*'?\d*", re.IGNORECASE),
    ),
    ("sql_injection_payload", re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE)),
    ("sql_injection_payload", re.compile(r"'\s*;\s*\w+")),
    # KHONG bat `--` theo sau dau nhay: van xuoi mo ta KY TU ("gui ky tu dac biet
    # nhu ';' hoac '--'") khop luat nay ma khong phai payload. Payload that da
    # duoc bat boi cac luat ' OR / '; / UNION SELECT / DROP TABLE o tren. Mot luat
    # ban nham o day khong lam tang an toan, no chi lam mat record.
    # Payload XSS va path traversal.
    ("xss_payload", re.compile(r"<\s*script\b", re.IGNORECASE)),
    ("xss_payload", re.compile(r"\bon(?:error|load)\s*=", re.IGNORECASE)),
    ("path_traversal_payload", re.compile(r"(?:\.\./){2,}")),
)


def _texts(value: Any) -> list[str]:
    """Trải phẳng một field thành danh sách chuỗi để dò."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            found.extend(_texts(item))
        return found
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_texts(item))
        return found
    return []


def _problems_in(label: str, text: str) -> list[str]:
    found: list[str] = []
    for kind, pattern in _UNSAFE:
        match = pattern.search(text)
        if match:
            excerpt = match.group(0)[:60]
            found.append(f"{label}: {kind} — {excerpt!r}")
    return found


def scan_unsafe_output(record: Any) -> list[str]:
    """Trả về danh sách vi phạm trong các field do Agent viết. Rỗng nghĩa là sạch."""
    if not isinstance(record, dict):
        return []

    problems: list[str] = []
    for field in AGENT_AUTHORED_FIELDS:
        for text in _texts(record.get(field)):
            problems.extend(_problems_in(field, text))

    objective = record.get("verification_objective")
    if isinstance(objective, dict):
        for field in OBJECTIVE_FIELDS:
            for text in _texts(objective.get(field)):
                problems.extend(_problems_in(f"verification_objective.{field}", text))

    # Bo trung nhung giu thu tu, de thong diep retry on dinh giua cac lan chay.
    seen: set[str] = set()
    unique: list[str] = []
    for problem in problems:
        if problem not in seen:
            seen.add(problem)
            unique.append(problem)
    return unique


__all__ = ["AGENT_AUTHORED_FIELDS", "OBJECTIVE_FIELDS", "scan_unsafe_output"]
