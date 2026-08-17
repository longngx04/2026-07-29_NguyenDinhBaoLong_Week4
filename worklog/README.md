# `worklog/` — Báo cáo sau mỗi task của coding agent

Mỗi task do coding agent thực hiện phải để lại **đúng một** file báo cáo trong thư mục này.
Đây là nơi người dùng review công việc của agent mà không cần đọc lại toàn bộ diff.

## Quy tắc

| Mục | Quy định |
|---|---|
| Tên file | `YYYY-MM-DD-<task-slug>.md` — ví dụ `2026-08-17-task1-gop-compose.md` |
| Khung nội dung | Copy nguyên từ [`_TEMPLATE.md`](_TEMPLATE.md), đủ 8 mục, không xoá mục nào |
| Số liệu | Chỉ ghi output/exit code đã chạy thật. Cấm phỏng đoán, cấm bịa |
| Secret | Không dán API key, token, nội dung `.env`. Che bằng `***` |
| Sửa file cũ | Không sửa worklog của task đã xong. Task lặp lại thì tạo file mới `-v2` |
| Ai viết | Agent viết ở Gate 3 của [`.agents/rules/task_prompt_template.md`](../.agents/rules/task_prompt_template.md) |

## Khác gì `reports/week-XX/`?

- `reports/week-XX/` — báo cáo sprint chính thức, bất biến, viết cho bên ngoài đọc.
- `worklog/` — nhật ký từng task, viết cho người review nội bộ, tần suất dày, vòng đời ngắn.

## Checklist review nhanh

- [ ] File worklog tồn tại, tên đúng định dạng.
- [ ] Đủ 8 mục, không mục nào để trống (không có thì ghi "Không có").
- [ ] Mục 5 có output thật dán từ terminal.
- [ ] Mục 6 nêu được ít nhất một phương án đã loại bỏ và lý do.
- [ ] Mục 7 có bảng lệnh + exit code; fail được ghi là fail.
- [ ] Mục 8 nêu chỗ agent tự thấy ít chắc chắn nhất.
- [ ] `git diff --stat` khớp với bảng file ở mục 3.
