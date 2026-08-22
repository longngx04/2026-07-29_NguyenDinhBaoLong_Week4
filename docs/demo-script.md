# Kịch bản demo — 15 phút

## Chuẩn bị trước khi lên trình bày

```bash
export SENTINEL_GATEWAY_API_KEY="$(openssl rand -hex 32)"
export LLM_API_KEY="$(sed -n 's/^LLM_API_KEY=//p' .env)"
make target-up
make run                      # chạy sẵn một lần thành công
make runs                     # ghi lại run_id của nó
export SENTINEL_DEMO_RUN=<run_id vừa ghi>
make web
```

Mở sẵn `http://127.0.0.1:8000`. Nếu mạng hoặc LLM chết giữa buổi, lần chạy đã ghim
vẫn cho bấm đủ bảy màn hình.

## Diễn tiến

| Phút | Nói gì | Bấm gì |
|---|---|---|
| 0–1 | Một lần quét SAST đẻ ra hàng trăm cảnh báo. Ai đọc hết? Ai biết cái nào thật? | Overview |
| 1–2 | Chín bước, từ quét tới báo cáo, có con người ở giữa | sơ đồ trong README |
| 2–4 | Bấm quét — OpenGrep chạy trên mã Java thật của WebGoat | **Quét mã nguồn** → Run |
| 4–6 | Agent nhóm cảnh báo trùng, giải thích, **và trích dẫn bằng chứng từ scanner** | Findings → Analysis |
| 6–8 | Agent đề xuất một request kiểm chứng. Đây là chỗ nguy hiểm: đầu ra LLM là dữ liệu không đáng tin. Chỉ endpoint trong allowlist mới tồn tại | Analysis → Security events |
| 8–10 | **Bấm Reject.** Rồi mở nhật ký request ra: **trống**. Không phải giao diện nhớ hỏi — công cụ từ chối chạy khi chưa có phê duyệt | Approvals → Requests |
| 10–11 | Chạy lại, **bấm Approve**. Giờ request đi qua Gateway và có response | Approvals → Requests |
| 11–13 | Response chứa chỉ dẫn tấn công — bị cắt. Chứa email và số điện thoại — bị che. Chiếu before/after | Security events |
| 13–14 | Báo cáo cuối, số liệu, kết quả bộ đánh giá sáu ca kèm FP/FN | Overview → `reports/week-06/eval-results.md` |
| 14–15 | Hạn chế còn lại và hướng phát triển | `docs/limitations.md` |

## Bảy hạng mục đề bài bắt buộc trình diễn

| Hạng mục | Phút |
|---|---|
| Một lần chạy công cụ quét | 2–4 |
| Agent tạo báo cáo | 4–6 |
| Agent đề xuất request kiểm tra | 6–8 |
| Người dùng Approve hoặc Reject | 8–11 |
| Request đi qua API Gateway | 10–11 |
| Prompt Injection bị chặn | 11–13 |
| Dữ liệu nhạy cảm bị che | 11–13 |

## Phương án dự phòng

| Hỏng gì | Làm gì |
|---|---|
| LLM hết hạn mức hoặc timeout | Chuyển sang lần chạy đã ghim ở `SENTINEL_DEMO_RUN` |
| Docker không lên | Chiếu `reports/week-06/report.md` và artifact của lần chạy đã lưu |
| Mất mạng hoàn toàn | Web không dùng tài nguyên ngoài nào; chỉ phần gọi LLM hỏng, mọi màn hình đọc vẫn chạy |
| Quét quá lâu | Đã có lần chạy sẵn từ bước chuẩn bị; mở thẳng nó |

## Câu hỏi có thể bị hỏi

**"Sao không để agent tự gửi request luôn?"** Vì đầu ra LLM không đáng tin. Cổng
duyệt nằm bên trong `probe/tool.py`, không nằm ở giao diện — quên nối UI thì hệ
thống đứng, chứ không âm thầm gửi.

**"Bộ phát hiện injection này qua mặt được không?"** Được, nó dựa trên mẫu. Nên nó
không phải lớp phòng thủ duy nhất: allowlist và phê duyệt của con người mới là
lớp chặn thật.

**"Vì sao tuần 4 lại có thư mục bài tập riêng?"** Đó là bài tập độc lập để hiểu
gateway kiểm soát request thế nào, chạy bằng compose riêng ở
`exercises/week4-gateway/`. Luồng cuối dùng Nginx Gateway trước WebGoat.
