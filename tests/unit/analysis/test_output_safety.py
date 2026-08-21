"""Agent không được sinh payload khai thác, dù chỉ dưới dạng "hướng dẫn kiểm chứng".

System prompt cấm rõ: không exploit payload, không destructive request, không shell
command, chỉ đề xuất code review / unit test / kiểm chứng không phá huỷ. Artifact đã
commit vẫn chứa `'; DROP TABLE employees --'` và `ping localhost; id`.

Safe Probe không thực thi các chuỗi đó, nên chúng chưa từng chạm tới WebGoat. Nhưng
`analysis.jsonl` và `report.md` LÀ deliverable của Agent: chúng được người đọc, được
copy-paste, và được nộp cho người review. Một hướng dẫn `DROP TABLE` trong báo cáo bảo mật
là output không đạt, bất kể downstream có chặn hay không.

Ranh giới quan trọng nhất của module này: **chỉ quét field do Agent viết**. Trường
`evidence` chứa mã nguồn WebGoat nguyên văn, mà WebGoat cố ý có sẵn chuỗi tấn công
trong comment. Quét cả evidence sẽ khiến mọi record hợp lệ đều bị đánh trượt.
"""

import pytest

from project_sentinel.analysis.output_safety import (
    AGENT_AUTHORED_FIELDS,
    scan_unsafe_output,
)

DESTRUCTIVE = [
    "'; DROP TABLE employees --'",
    "DELETE FROM users WHERE 1=1",
    "TRUNCATE TABLE accounts",
    "ping localhost; id",
    "rm -rf /var/data",
    "'; EXEC xp_cmdshell('whoami') --",
    "$(cat /etc/passwd)",
    "`whoami`",
]

EXPLOIT = [
    "Gửi payload ' OR '1'='1 vào tham số name",
    "Smith' UNION SELECT userid, password FROM user_data --",
    "<script>alert(document.cookie)</script>",
    "../../../../etc/passwd",
]

SAFE = [
    "Đọc lại mã nguồn quanh dòng 47 để xác định nguồn của biến query",
    "Viết unit test khẳng định PreparedStatement được dùng",
    "Kiểm tra cấu hình Spring Security có bật CSRF không",
    "Xem lại tài liệu OWASP về Injection",
    "Gửi request lành tính loại empty_value và quan sát mã trạng thái",
]


def _record(**overrides):
    base = {
        "analysis_id": "analysis-a",
        "title": "SQL Injection",
        "explanation": "Tham số request được nối vào truy vấn.",
        "confidence_rationale": "Thấy rõ đường đi dữ liệu.",
        "preconditions": ["Ứng dụng nhận dữ liệu người dùng"],
        "verification_steps": [
            {"action": "review_source", "detail": "Đọc lại hàm injectableQuery"}
        ],
        "remediation": ["Dùng PreparedStatement"],
        "limitations": ["Chỉ phân tích tĩnh"],
        "evidence": [],
        "verification_objective": None,
    }
    base.update(overrides)
    return base


# --- bắt được ---------------------------------------------------------------


@pytest.mark.parametrize("payload", DESTRUCTIVE + EXPLOIT)
def test_unsafe_text_in_explanation_is_caught(payload):
    problems = scan_unsafe_output(_record(explanation=f"Ví dụ: {payload}"))
    assert problems, f"Không bắt được: {payload!r}"


@pytest.mark.parametrize("payload", DESTRUCTIVE)
def test_unsafe_text_in_a_verification_step_detail_is_caught(payload):
    record = _record(
        verification_steps=[{"action": "send_benign_template", "detail": payload}]
    )
    assert scan_unsafe_output(record)


@pytest.mark.parametrize("payload", DESTRUCTIVE[:4])
def test_unsafe_text_in_the_objective_is_caught(payload):
    record = _record(
        verification_objective={
            "description": f"Gửi {payload}",
            "endpoint_hint": "GET /WebGoat/login",
            "payload_kind": "empty_value",
            "rationale": "r",
        }
    )
    assert scan_unsafe_output(record)


def test_unsafe_text_in_the_expected_signal_is_caught():
    record = _record(
        verification_objective={
            "description": "d",
            "endpoint_hint": "GET /WebGoat/login",
            "payload_kind": "empty_value",
            "rationale": "r",
            "expected_signal": "'; DROP TABLE x --",
        }
    )
    assert scan_unsafe_output(record)


@pytest.mark.parametrize("field", ["preconditions", "remediation", "limitations"])
def test_unsafe_text_in_any_list_field_is_caught(field):
    assert scan_unsafe_output(_record(**{field: ["rm -rf /var/data"]}))


def test_the_report_says_which_field_and_what_matched():
    problems = scan_unsafe_output(_record(explanation="chạy rm -rf /tmp/x"))
    assert any("explanation" in p for p in problems)


# --- KHÔNG được bắt nhầm ----------------------------------------------------


@pytest.mark.parametrize("text", SAFE)
def test_safe_guidance_is_not_flagged(text):
    record = _record(
        explanation=text,
        verification_steps=[{"action": "review_source", "detail": text}],
    )
    assert scan_unsafe_output(record) == []


def test_webgoat_source_evidence_is_never_scanned():
    """WebGoat cố ý có chuỗi tấn công trong comment. Đó là bằng chứng, không phải
    output của Agent — quét nó sẽ đánh trượt mọi record hợp lệ."""
    record = _record(
        evidence=[
            {
                "type": "source",
                "path": "SqlInjectionLesson6a.java",
                "start_line": 40,
                "end_line": 45,
                "content": (
                    "// The answer: Smith' union select userid,user_name,password "
                    "from user_data --"
                ),
            },
            {
                "type": "scanner",
                "finding_id": "opengrep-008",
                "content": "'; DROP TABLE employees --'",
            },
        ]
    )
    assert scan_unsafe_output(record) == []


def test_evidence_is_not_in_the_scanned_field_list():
    assert "evidence" not in AGENT_AUTHORED_FIELDS


def test_mentioning_a_vulnerability_class_is_not_unsafe():
    record = _record(
        title="SQL Injection",
        explanation="Đây là lỗ hổng SQL Injection do nối chuỗi.",
        remediation=["Dùng PreparedStatement thay vì Statement"],
    )
    assert scan_unsafe_output(record) == []


# --- bền với dữ liệu hỏng ---------------------------------------------------


def test_a_broken_record_does_not_crash():
    assert scan_unsafe_output({}) == []
    assert scan_unsafe_output({"explanation": None}) == []
    assert scan_unsafe_output({"verification_steps": "chuoi"}) == []
    assert scan_unsafe_output(None) == []


# --- backtick: code span Markdown khác command substitution ------------------


@pytest.mark.parametrize(
    "text",
    [
        "Biến `kid` lấy từ header của JWT.",
        "Tham số `accountName` được nối vào truy vấn.",
        "Lời gọi `statement.executeQuery(query)` chạy trên Statement.",
        "Hàm `injectableQuery` nhận tham số từ controller.",
        "Dùng `PreparedStatement` thay cho `Statement`.",
    ],
)
def test_markdown_code_spans_are_not_shell_commands(text):
    """Backtick trong văn xuôi kỹ thuật gần như luôn là code span.

    Không thu hẹp luật này thì 17/21 record hợp lệ bị đánh trượt, và pipeline sẽ
    mất record hàng loạt — biến một guardrail thành một lỗi.
    """
    assert scan_unsafe_output(_record(explanation=text)) == []


@pytest.mark.parametrize(
    "text",
    [
        "Chạy `curl http://evil/x` để lấy dữ liệu",
        "Thử `bash -c whoami`",
        "Gửi `ping localhost; id`",
        "`python -c 'import os'`",
    ],
)
def test_a_backtick_holding_a_real_shell_invocation_is_caught(text):
    assert scan_unsafe_output(_record(explanation=text))


@pytest.mark.parametrize(
    "text",
    [
        "Gửi ký tự đặc biệt như ';' hoặc '--' để quan sát phản hồi",
        "Ký tự '--' bắt đầu một comment trong SQL",
        "Các ký tự cần chú ý: ';', '--', '/*'",
    ],
)
def test_prose_describing_sql_characters_is_not_a_payload(text):
    """Mô tả ký tự khác với đưa ra payload. Bắt nhầm ở đây chỉ làm mất record."""
    record = _record(
        verification_objective={
            "description": "d",
            "endpoint_hint": "GET /WebGoat/login",
            "payload_kind": "empty_value",
            "rationale": text,
        }
    )
    assert scan_unsafe_output(record) == []
