"""Chín bước của luồng. Mỗi bước là một hàm thuần (record, ctx) -> record.

Bước nào hỏng thì ném StepFailure với thông điệp đọc được; runner bắt lại và
chuyển trạng thái sang FAILED.

Trước đây cả chín bước nằm trong một file 722 dòng. Việc gộp đó đã che một lỗi
thật: hai nhánh khác nhau của cùng một hàm dài dùng chung một tên biến `reason`,
nên một nhánh đọc phải giá trị của nhánh kia. Nay mỗi giai đoạn một file:

- `common`  — kiểu lỗi, ghi artifact qua nút thắt redaction, chạy lệnh ngoài
- `ingest`  — bước 1–3: scan, normalize, analyze
- `propose` — bước 4–5: đề xuất kiểm chứng và cổng phê duyệt
- `probe`   — bước 6–7: gửi request qua Gateway và lọc response
- `finish`  — bước 8–9: dựng báo cáo và chốt trạng thái

Đường import công khai giữ nguyên: `from project_sentinel.orchestrator.steps
import step_scan` vẫn chạy như cũ.
"""

from project_sentinel.orchestrator.steps.common import (
    SUBPROCESS_TIMEOUT_SECONDS,
    StepFailure,
    _run_command,
    _write_json_artifact,
)
from project_sentinel.orchestrator.steps.finish import step_finalize, step_report
from project_sentinel.orchestrator.steps.ingest import (
    step_analyze,
    step_normalize,
    step_scan,
)
from project_sentinel.orchestrator.steps.probe import step_probe, step_scrub
from project_sentinel.orchestrator.steps.propose import step_approval, step_propose

__all__ = [
    "SUBPROCESS_TIMEOUT_SECONDS",
    "StepFailure",
    # Hai ten rieng tu duoi day duoc re-export co chu y: test va cac buoc
    # deu dung chung nut that ghi artifact nay.
    "_run_command",
    "_write_json_artifact",
    "step_analyze",
    "step_approval",
    "step_finalize",
    "step_normalize",
    "step_probe",
    "step_propose",
    "step_report",
    "step_scan",
    "step_scrub",
]
