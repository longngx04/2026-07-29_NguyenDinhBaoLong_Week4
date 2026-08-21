"""Audit log không được mất bản ghi khi có nhiều tiến trình cùng ghi.

`log_request` đọc toàn bộ file, ghi lại vào file tạm, rồi `os.replace`. Hai writer
chạy song song đều đọc cùng một bản cũ, và writer sau ghi đè mất bản ghi của writer
trước. Đo thật: ghi 100 bản ghi đồng thời, còn lại **16**.

Audit log là bằng chứng chấm điểm và là thứ duy nhất nói request nào đã rời hệ
thống. Một audit log mất 84 % bản ghi thì tệ hơn là không có, vì nó trông đầy đủ.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from project_sentinel.gateway.request_log import log_request


def _write(path: Path, index: int) -> None:
    log_request(
        str(path),
        request_id=f"req-{index:04d}",
        method="GET",
        path="/WebGoat/login",
        status="SENT",
        status_code=200,
    )


def _ids(path: Path) -> set[str]:
    return {
        json.loads(line)["request_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def test_no_record_is_lost_under_concurrent_writers(tmp_path):
    path = tmp_path / "requests.jsonl"
    total = 100
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda i: _write(path, i), range(total)))

    written = _ids(path)
    assert len(written) == total, f"Mất {total - len(written)} bản ghi audit"
    assert written == {f"req-{i:04d}" for i in range(total)}


def test_every_line_stays_valid_json_under_concurrency(tmp_path):
    """Ghi xen kẽ không được tạo ra dòng rách."""
    path = tmp_path / "requests.jsonl"
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda i: _write(path, i), range(60)))
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            assert isinstance(json.loads(line), dict)


def test_a_burst_from_many_threads_keeps_order_within_a_thread(tmp_path):
    """Một writer ghi tuần tự thì thứ tự của chính nó phải được giữ."""
    path = tmp_path / "requests.jsonl"

    def burst(worker: int) -> None:
        for step in range(10):
            log_request(
                str(path),
                request_id=f"w{worker}-s{step}",
                method="GET",
                path="/WebGoat/login",
                status="SENT",
            )

    threads = [threading.Thread(target=burst, args=(w,)) for w in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = [
        json.loads(line)["request_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 60
    for worker in range(6):
        mine = [name for name in lines if name.startswith(f"w{worker}-")]
        assert mine == [f"w{worker}-s{step}" for step in range(10)]


def test_the_audit_contract_still_rejects_unreviewed_fields(tmp_path):
    """Sửa chuyện đồng thời không được nới lỏng allowlist trường audit."""
    import pytest

    with pytest.raises(ValueError, match="Unreviewed"):
        log_request(str(tmp_path / "x.jsonl"), request_id="r", cookie="bi-mat")
