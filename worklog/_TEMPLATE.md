# Worklog — <Tên task>

**Ngày:** YYYY-MM-DD · **Agent/Model:** <ví dụ: Antigravity · Gemini 3.6 Flash High> ·
**Branch:** `<branch>` · **Plan:** [`<đường dẫn plan>`](<đường dẫn plan>) · **Task ID:** `<Task N>`

> Điền đủ 8 mục. Mục nào không có nội dung thì ghi `Không có` — không được xoá mục.
> Mọi số liệu phải là kết quả chạy thật. Che secret bằng `***`.

---

## 1. Tóm tắt

<3 câu: đã làm gì · phục vụ ai/cái gì · kết quả cuối cùng.>

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** <task này thêm/sửa năng lực gì cho Project Sentinel>
- **Nằm ở đâu trong luồng:** <ví dụ: giữa `analysis/` và `probe/`, chạy trước bước gọi Gateway>
- **Không có nó thì hỏng gì:** <hậu quả cụ thể nếu bỏ task này>
- **Ngoài phạm vi (cố ý không làm):** <liệt kê, kèm lý do>

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `path/to/file.py` | Tạo / Sửa / Xoá / Chuyển chỗ | <mô tả cụ thể, không viết "cập nhật logic"> | <lý do> |

**`git diff --stat`:**

```text
<dán nguyên output>
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** <mô tả cách giải quyết, 3–6 câu>

**Luồng dữ liệu:** `<đầu vào>` → `<bước xử lý 1>` → `<bước xử lý 2>` → `<đầu ra>`

**Các quyết định kỹ thuật:**

- <quyết định 1 — ví dụ: validate ở tầng Python trước khi mở kết nối>
- <quyết định 2>

**Xử lý lỗi / trường hợp biên:** <input rỗng, sai kiểu, phụ thuộc không sẵn sàng… xử lý ra sao>

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm / Class / File / Config / Test | `<tên>` | `<signature hoặc path>` | <mô tả> |

**Cách chạy:**

```bash
<lệnh chạy tính năng này>
```

**Output thật (đã che secret):**

```text
<dán output thật từ terminal>
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** <mô tả ngắn>

**Lý do:** <ràng buộc từ plan/`.agents/`/kiến trúc hiện có dẫn tới lựa chọn này. Nếu plan đã
chỉ định thì trích đúng dòng đó và giải thích vì sao nó hợp lý.>

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| <phương án B> | <ưu điểm> | <lý do loại — hiệu năng, vi phạm bất biến, phình phạm vi…> |

**Đánh đổi đã chấp nhận:** <ví dụ: chậm hơn nhưng dễ kiểm chứng>

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest -m "not llm" -q tests` | 0 | <ví dụ: 128 passed> |
| `python3 -m compileall -q src/project_sentinel` | 0 | — |
| `<lệnh khác>` | | |

**Test mới thêm:**

- `tests/.../test_x.py::test_y` — <test này khẳng định điều gì>

**Bất biến đã giữ:** <no mock/stub · test không skip · không lộ secret · chỉ Gateway bind cổng
loopback · không đụng `reports/week-XX/` · …>

**Còn fail / chưa chạy được:** <ghi thật; không có thì ghi "Không có">

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** <file:line + lý do>
- **Giả định đã đặt:** <giả định + hệ quả nếu giả định sai>
- **Việc còn nợ:** <phần đã cố ý hoãn>
- **Câu hỏi cho người dùng:** <nếu có>
