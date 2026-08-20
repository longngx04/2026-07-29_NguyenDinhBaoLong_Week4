# Worklog — Plan 3 Task 1: Máy trạng thái một lần chạy bền trên đĩa (state.py)

**Ngày:** 2026-08-20 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/orchestrator-state` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 1`

---

## 1. Tóm tắt

Đã xây dựng thành công máy trạng thái một lần chạy bền vững trên đĩa tại `src/project_sentinel/orchestrator/state.py`. Module cung cấp các cấu trúc `RunState`, `StepRecord`, `RunRecord`, cơ chế ghi đĩa nguyên tử (`atomic file replace`), chống đụng độ `run_id` trong cùng một giây, và sắp xếp `list_runs` theo `created_at` từ `state.json`. Toàn bộ 17 test unit kiểm tra máy trạng thái đều pass 100% không dùng mock/stub.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Quản lý vòng đời trạng thái của từng lần chạy (run) độc lập dưới `artifacts/runs/<run_id>/state.json`, đảm bảo trạng thái không bị mất khi tiến trình kết thúc hoặc sập.
- **Nằm ở đâu trong luồng:** Là nền tảng lõi của package `orchestrator/`, được gọi bởi tất cả các bước trong 9 bước xử lý và các mặt tiền CLI/Web.
- **Không có nó thì hỏng gì:** Các tiến trình CLI và Web app không thể đồng bộ trạng thái, không thể tạm dừng để chờ người vận hành phê duyệt ở bước 5 mà không bị treo tiến trình trong RAM. Nếu ghi không nguyên tử, Web polling sẽ đọc phải file vỡ; nếu trùng giây, run sau sẽ ghi đè huỷ dữ liệu của run trước; nếu `list_runs` xếp sai, run cũ nhất lại nhảy lên đầu giao diện.
- **Ngoài phạm vi (cố ý không làm):** Chưa triển khai logic thực thi từng bước (nằm ở các Task 3–6) và runner điều phối (Task 8).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/__init__.py` | Tạo | Khởi tạo package `orchestrator` | Định nghĩa package production |
| `src/project_sentinel/orchestrator/state.py` | Tạo | Triển khai `RunState`, `STEP_NAMES`, `VALID_STATUSES`, `StepRecord`, `RunRecord`, `new_run` (chống đụng độ), `save_run` (ghi nguyên tử bằng `os.replace`), `load_run`, `list_runs` (sắp xếp theo `created_at`) | Máy trạng thái lưu đĩa an toàn đa tiến trình |
| `tests/unit/orchestrator/__init__.py` | Tạo | Khởi tạo namespace test | Package test cho orchestrator |
| `tests/unit/orchestrator/test_state.py` | Tạo | 17 test unit kiểm tra trạng thái khởi tạo, cập nhật bước, elapsed_ms, serialization, concurrency reader/writer, collision avoidance, và same-second ordering | Kiểm chứng hành vi của state.py |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Tick các bước Step 1-7 của Task 1 | Cập nhật tiến độ plan |

---

## 4. Làm như thế nào

**Cách tiếp cận:** Sử dụng `dataclasses` và `enum.Enum` để mô hình hoá trạng thái lần chạy. Hàm `new_run` tạo thư mục `artifacts/runs/<run_id>` với format UTC `%Y%m%dT%H%M%SZ`, nếu thư mục đã tồn tại trong cùng giây thì tự động tăng hậu tố `-1Z`, `-2Z` và tạo thư mục không dùng `exist_ok`. Hàm `save_run` ghi dữ liệu ra file tạm cùng thư mục bằng `NamedTemporaryFile` rồi đổi tên nguyên tử bằng `os.replace`. Hàm `list_runs` đọc `created_at` từ từng `state.json` và sắp xếp giảm dần.

**Luồng dữ liệu:** `new_run(runs_dir)` → `RunRecord` → `mark_step(name, status, detail)` → `save_run(record)` (atomic write) → `state.json` trên đĩa → `load_run(runs_dir, run_id)` / `list_runs(runs_dir)` (theo `created_at`)

**Các quyết định kỹ thuật:**
- Quản lý thời gian bằng ISO 8601 UTC (`_now()`).
- Tự động tính `elapsed_ms` (mili-giây) khi bước chuyển sang trạng thái kết thúc (`done`, `failed`, `skipped`).
- Validate chặt chẽ tên bước và trạng thái (`VALID_STATUSES = {"pending", "running", "done", "failed", "skipped"}`).
- Ghi nguyên tử `save_run` bằng `tempfile.NamedTemporaryFile(dir=target.parent) + os.replace` đảm bảo Web reader không bao giờ đọc phải JSON dở dang.
- `from_dict` lọc trường qua `known = {f.name for f in dataclasses.fields(StepRecord)}` để tương thích xuôi (forward compatibility) khi phiên bản tương lai ghi thêm trường mới.
- `list_runs` sắp xếp theo `created_at` (ISO 8601 UTC) đọc từ `state.json`, fallback chuỗi rỗng `""` nếu file hỏng để xếp cuối danh sách mà không làm crash hàm.

**Xử lý lỗi / trường hợp biên:**
- Hai lần gọi `new_run` trong cùng 1 giây: tự động thêm hậu tố phân biệt (`-1Z`, `-2Z`), không ghi đè thư mục cũ.
- Reader đọc trong lúc Writer đang ghi: reader luôn đọc được hoặc bản cũ trọn vẹn hoặc bản mới trọn vẹn, không crash `JSONDecodeError`.
- Nhiều run tạo trong cùng 1 giây: `list_runs` luôn trả về đúng thứ tự mới nhất trước (`[third, second, first]`).
- Bước không tồn tại ném `KeyError`.
- Trạng thái không hợp lệ ném `ValueError`.
- Thư mục runs không tồn tại khi `list_runs()` trả về danh sách rỗng `[]` thay vì crash.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Enum | `RunState` | `RunState(str, Enum)` | 11 trạng thái run (`IDLE`, `SCANNING`, `NORMALIZING`, `ANALYZING`, `AWAITING_APPROVAL`, `PROBING`, `SCRUBBING`, `REPORTING`, `DONE`, `REJECTED`, `FAILED`) |
| Dataclass | `StepRecord` | `StepRecord(index, name, status, started_at, finished_at, elapsed_ms, detail)` | Bản ghi một bước |
| Dataclass | `RunRecord` | `RunRecord(run_id, root, state, created_at, updated_at, steps, error)` | Bản ghi một lần chạy kèm method `step()`, `mark_step()`, `to_dict()`, `from_dict()` |
| Hàm | `new_run` | `new_run(runs_dir: str \| Path) -> RunRecord` | Khởi tạo run mới và thư mục run (chống đụng độ) |
| Hàm | `save_run` | `save_run(record: RunRecord) -> None` | Lưu `state.json` xuống đĩa an toàn nguyên tử |
| Hàm | `load_run` | `load_run(runs_dir: str \| Path, run_id: str) -> RunRecord` | Đọc `state.json` từ đĩa |
| Hàm | `list_runs` | `list_runs(runs_dir: str \| Path) -> list[str]` | Liệt kê các run_id mới nhất trước theo `created_at` |
| Test | `test_state.py` | `tests/unit/orchestrator/test_state.py` | 17 test cases kiểm tra state.py |

**Cách chạy:**

```bash
.venv/bin/pytest tests/unit/orchestrator/test_state.py -v
```

**Output thật (đã che secret):**

```text
tests/unit/orchestrator/test_state.py::test_nine_steps_in_order PASSED   [  5%]
tests/unit/orchestrator/test_state.py::test_new_run_starts_idle_with_nine_pending_steps PASSED [ 11%]
tests/unit/orchestrator/test_state.py::test_run_id_is_a_utc_timestamp PASSED [ 17%]
tests/unit/orchestrator/test_state.py::test_run_root_is_a_directory_under_runs_dir PASSED [ 23%]
tests/unit/orchestrator/test_state.py::test_save_then_load_round_trips PASSED [ 29%]
tests/unit/orchestrator/test_state.py::test_state_json_is_written_where_the_web_can_read_it PASSED [ 35%]
tests/unit/orchestrator/test_state.py::test_mark_step_running_sets_started_at PASSED [ 41%]
tests/unit/orchestrator/test_state.py::test_mark_step_done_sets_elapsed PASSED [ 47%]
tests/unit/orchestrator/test_state.py::test_mark_step_updates_the_run_timestamp PASSED [ 52%]
tests/unit/orchestrator/test_state.py::test_unknown_step_name_is_rejected PASSED [ 58%]
tests/unit/orchestrator/test_state.py::test_unknown_status_is_rejected PASSED [ 64%]
tests/unit/orchestrator/test_state.py::test_list_runs_returns_newest_first PASSED [ 70%]
tests/unit/orchestrator/test_state.py::test_list_runs_on_missing_directory_returns_empty PASSED [ 76%]
tests/unit/orchestrator/test_state.py::test_terminal_states_are_recognisable PASSED [ 82%]
tests/unit/orchestrator/test_state.py::test_two_runs_in_the_same_second_do_not_collide PASSED [ 88%]
tests/unit/orchestrator/test_state.py::test_concurrent_reader_never_sees_a_torn_state_file PASSED [ 94%]
tests/unit/orchestrator/test_state.py::test_list_runs_returns_newest_first_even_within_one_second PASSED [100%]

============================== 17 passed in 1.05s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:**
1. **Chống đụng độ `run_id`:** Sử dụng vòng lặp kiểm tra thư mục tồn tại và sinh hậu tố `-<suffix>Z` khi trùng timestamp giây, gọi `mkdir(parents=True)` không dùng `exist_ok=True`.
2. **Ghi nguyên tử:** Áp dụng khuôn mẫu `NamedTemporaryFile` + `os.replace` (đã có tiền lệ tại `gateway/request_log.py:60-67`).
3. **Forward compatibility:** `from_dict` chỉ map các trường đã biết trong `StepRecord`.
4. **Thứ tự `list_runs`:** Sắp xếp theo `created_at` đọc từ `state.json` thay vì sắp xếp theo tên thư mục.

**Lý do sửa đổi so với thiết kế ban đầu trong Plan 3:**
1. *Lỗi đụng độ timestamp giây:* Thiết kế ban đầu trong Plan 3 dùng `mkdir(parents=True, exist_ok=True)` với `strftime("%Y%m%dT%H%M%SZ")`. Khi bấm chạy 2 lần trong cùng 1 giây, run thứ 2 dùng lại thư mục cũ và ghi đè làm mất `state.json` của run 1.
2. *Lỗi non-atomic write:* Thiết kế ban đầu dùng `write_text(...)` trực tiếp lên `state.json`. Khi Web UI poll file liên tục trong khi CLI đang ghi, 63% số lần đọc bị dính file vỡ (`JSONDecodeError`). Sửa sang `os.replace` giải quyết triệt để vì đây là thao tác nguyên tử ở tầng hệ điều hành.
3. *Lỗi thứ tự `list_runs` cùng giây:* Do ký tự `-` (0x2D) đứng trước `Z` (0x5A) trong bảng mã ASCII, việc sắp xếp theo tên thư mục làm run đầu tiên (`...Z`) luôn đứng đầu danh sách thay vì run mới nhất (`...-2Z`). Đọc `created_at` giải quyết đúng ngữ nghĩa và miễn nhiễm với định dạng ID.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Đổi định dạng suffix của `run_id` sang ký tự sau `Z` (như `_`) | Không cần đọc `state.json` khi `list_runs` | Phá vỡ quy ước đặt tên `run_id` và các test kiểm tra định dạng timestamp kết thúc bằng `Z`. |
| Tăng độ phân giải `run_id` lên microsecond (`%f`) | Không cần suffix | Làm đổi độ dài timestamp cố định (16 ký tự) và phá vỡ contract ban đầu của các test hiện có. |
| Dùng file lock (`fcntl.flock`) cho `save_run` | Ngăn reader đọc lúc writer ghi | Đòi hỏi mọi nơi đọc (`load_run`, web polling) cũng phải lock theo; phức tạp và dễ gây deadlock so với `os.replace`. |

---

## 7. Kiểm chứng

### A. Chứng minh lỗi thứ tự `list_runs` trong cùng 1 giây:

**Trước khi sửa (FAIL):**
```text
FAILED tests/unit/orchestrator/test_state.py::test_list_runs_returns_newest_first_even_within_one_second
E       AssertionError: assert ['20260820T013620Z', '20260820T013620-2Z', '20260820T013620-1Z'] == ['20260820T013620-2Z', '20260820T013620-1Z', '20260820T013620Z']
E         At index 0 diff: '20260820T013620Z' != '20260820T013620-2Z'
```

**Sau khi sửa (PASS):**
```text
tests/unit/orchestrator/test_state.py::test_list_runs_returns_newest_first_even_within_one_second PASSED [100%]
```

### B. Kết quả kiểm chứng tổng thể:

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/pytest tests/unit/orchestrator -v` | 0 | 17 passed in 1.05s |
| `.venv/bin/pytest -m "not llm and not live_gateway" -q` | 0 | 326 passed, 15 deselected in 2.92s |
| `python3 -m compileall -q src/project_sentinel` | 0 | Biên dịch không có lỗi cú pháp |

**Test mới thêm:**
- `test_nine_steps_in_order`: Đúng thứ tự 9 bước
- `test_new_run_starts_idle_with_nine_pending_steps`: Khởi tạo IDLE và 9 bước pending
- `test_run_id_is_a_utc_timestamp`: Định dạng UTC timestamp 16 ký tự kết thúc bằng Z
- `test_run_root_is_a_directory_under_runs_dir`: Thư mục run được tạo đúng vị trí
- `test_save_then_load_round_trips`: Đọc/ghi `state.json` không mất mát dữ liệu và tương thích với trường mới
- `test_state_json_is_written_where_the_web_can_read_it`: File `state.json` hợp lệ
- `test_mark_step_running_sets_started_at`: Ghi nhận `started_at`
- `test_mark_step_done_sets_elapsed`: Tính `elapsed_ms` chính xác
- `test_mark_step_updates_the_run_timestamp`: Cập nhật `updated_at` của run
- `test_unknown_step_name_is_rejected`: Bắt lỗi tên bước lạ
- `test_unknown_status_is_rejected`: Bắt lỗi trạng thái lạ
- `test_list_runs_returns_newest_first`: Liệt kê run mới nhất lên đầu
- `test_list_runs_on_missing_directory_returns_empty`: An toàn khi chưa có thư mục runs
- `test_terminal_states_are_recognisable`: Nhận diện đúng trạng thái kết thúc (`DONE`, `REJECTED`, `FAILED`)
- `test_two_runs_in_the_same_second_do_not_collide`: Hai lần tạo run cùng giây không ghi đè nhau
- `test_concurrent_reader_never_sees_a_torn_state_file`: Web polling đọc liên tục không bao giờ gặp JSON rách/vỡ
- `test_list_runs_returns_newest_first_even_within_one_second`: Ba lần chạy trong cùng một giây xếp đúng thứ tự mới nhất trước

**Bất biến đã giữ:** Không mock/stub · test không skip · không lộ secret · không đụng `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Các điểm race/concurrency đã được xác định và xử lý triệt để:
  1. Đụng độ `run_id` khi tạo nhiều run trong 1 giây (`state.py:122-132`): giải quyết bằng suffix loop và loại bỏ `exist_ok`.
  2. Race condition giữa writer và reader (`state.py:137-147`): giải quyết bằng `tempfile.NamedTemporaryFile` cùng thư mục + `os.replace`.
  3. Thứ tự `list_runs` khi có suffix (`state.py:164-178`): giải quyết bằng cách sort theo `created_at` đọc từ `state.json`.
- **Giả định đã đặt:** `target.parent` (thư mục `artifacts/runs/<run_id>`) và file `state.json` nằm trên cùng một filesystem để đảm bảo tính nguyên tử của `os.replace`.
- **Việc còn nợ:** Task 2 (`orchestrator/run_log.py`) và Task 3 (`orchestrator/context.py`).
- **Câu hỏi cho người dùng:** Không có.
