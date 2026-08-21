# Giới hạn đã biết và rủi ro còn tồn tại

**Cập nhật:** 2026-08-21 · Mọi số liệu dưới đây lấy từ lần chạy thật, không suy đoán.

Tài liệu này viết cho người sắp dùng Project Sentinel để ra quyết định. Nó liệt kê những
gì hệ thống **không** làm được, kèm bằng chứng. Phần nào chưa đo được thì ghi là chưa đo.

---

## 1. Chất lượng phán đoán của Agent

### 1.1 Kết quả dao động giữa các lần chạy

Cùng mã nguồn, cùng 23 cảnh báo đầu vào, chạy lại nhiều lần cho kết quả khác nhau:

| Chỉ số | Khoảng đo được |
| :--- | :--- |
| Triage precision | 56,5 % – 75,0 % |
| Over-claim rate | 25,0 % – 33,3 % |
| Số record sinh ra | 19 – 21 trên 21 nhóm |
| `invalid_output_count` | 0 – 2 |

**Không bảng kết quả nào của hệ thống này là một cam kết.** Mỗi bảng là một lần lấy mẫu.
Khi báo cáo, hãy chạy `make eval REPEAT=n` và đọc phần phân bố, đừng trích một lần chạy.

### 1.2 Agent vẫn trình bày một phần false positive như lỗ hổng thật

Over-claim rate hiện tại **25–33 %**: cứ ba cảnh báo thật sự là false positive thì khoảng
một cái vẫn được trình bày như lỗ hổng có thật. Con số này đã giảm từ 100 % ở mốc nền,
nhưng nó chưa về 0 và **sẽ không về 0** với cách tiếp cận hiện tại.

Hai ca hỏng lặp lại là `opengrep-014` và `opengrep-016`: một truy vấn **hằng** nằm ngay
cạnh một điểm nguy hiểm có thật trong cùng một hàm. Cửa sổ bằng chứng rộng giúp Agent
thấy đường vào, nhưng cũng khiến nó gộp kết luận của hai dòng sát nhau.

### 1.3 Tầng hiệu chỉnh không chặn được lời khai sai

`analysis/calibration.py` chỉ hạ kết luận **khi Agent tự thừa nhận thiếu bằng chứng**
(`attacker_control: not_proven`) hoặc khi văn xuôi của nó tự mâu thuẫn. Một Agent khai
thẳng `attacker_control: proven` cho một truy vấn hằng sẽ **đi qua toàn bộ ba lớp** — vì
mọi ID, vị trí và CWE nó dùng đều có thật.

Đây là giới hạn về nguyên tắc, không phải lỗi cần vá: **không có phân tích taint thật**
thì phía Python không có cách nào độc lập kiểm chứng lời khai đó.

### 1.4 Bộ ground truth là một điểm tin cậy đơn

23 nhãn trong [`eval/ground-truth/webgoat-findings.json`](../eval/ground-truth/webgoat-findings.json)
do **một người** đặt, không có người thứ hai đối chiếu. Nếu một nhãn sai thì mọi con số
tính từ nó đều lệch theo. Bốn ca `needs_review` (`opengrep-002`, `003`, `005`, `020`) là
những ca tranh luận được nhất: chúng có thể là `true_positive` nếu đọc thêm tầng đăng ký
người dùng hoặc tầng gọi hàm.

---

## 2. Phạm vi kiểm chứng

### 2.1 Mỗi lần chạy chỉ gửi một request

23 cảnh báo → 21 nhóm → nhiều đề xuất → **một** request được gửi. Tỷ lệ bao phủ theo
finding khoảng **4 %**.

### 2.2 Probe gần như luôn `inconclusive`

Hệ thống nay tự nói ra điều này thay vì để người đọc hiểu nhầm, nhưng sự thật không đổi:
với môi trường WebGoat hiện tại, kết quả probe hầu như luôn là `inconclusive`.

Lý do: WebGoat yêu cầu đăng nhập, nên các endpoint chứa lỗ hổng trả HTTP 302; các endpoint
trả 200 (`/WebGoat/login`, `/WebGoat/actuator/health`) không liên quan tới lỗ hổng trong
mã nguồn. `supports`/`refutes` chỉ đạt tới được khi Agent khai trước `expected_signal`
**và** endpoint đó xuất hiện trong bằng chứng của finding — điều chưa xảy ra lần nào.

**Kết quả probe hiện tại chứng minh Gateway tới được ứng dụng và response được lọc.**
Nó không khẳng định lỗ hổng nào tồn tại.

---

## 3. Redaction và dữ liệu nhạy cảm

### 3.1 Redaction dựa trên mẫu, nên có trần

Bộ che nhận diện email, JWT, khoá kiểu `sk-`/`ghp_`, chuỗi hex ≥32, trường password, số
điện thoại Việt Nam và một số dạng số dài. **Một định dạng bí mật ngoài danh sách đó sẽ
lọt.** Đây là giới hạn về nguyên tắc của mọi bộ che dựa trên mẫu.

Điều đã được kiểm chứng bằng test: với các dạng **đã biết**, không byte nào chạm đĩa —
`tests/unit/orchestrator/test_probe_scrub_redaction_chain.py` quét **mọi** file trong thư
mục lần chạy để tìm canary.

### 3.2 Response bị cắt còn 512 byte

Chỉ 512 byte đầu của response được giữ. Bộ che chạy trên **toàn bộ** body trước khi cắt
(đổi lại chi phí regex trên tối đa 64 KiB), nên không có mảnh bí mật nào bị xé đôi ở mốc
cắt. Nhưng phần sau 512 byte thì không ai xem, kể cả để phát hiện injection.

---

## 4. Ranh giới thực thi

### 4.1 `SENTINEL_SCAN_COMMAND` chạy được một chương trình bất kỳ

Lệnh quét lấy từ biến môi trường. Tham số shell đã bị chặn, nhưng **kẻ kiểm soát được môi
trường và hệ thống file vẫn chỉ định được một chương trình bất kỳ để chạy.**

Đây là **rủi ro còn tồn tại được chấp nhận có ý thức**, không phải lỗi bị bỏ sót. Ai kiểm
soát được biến môi trường của tiến trình thì thường đã chạy được lệnh theo nhiều đường
khác. Nếu triển khai ở nơi ranh giới đó có ý nghĩa, hãy cố định lệnh quét trong mã.

### 4.2 WebGoat là ứng dụng cố ý có lỗ hổng

`docker-compose.yml` buộc Gateway bind loopback và **không** mở cổng host cho WebGoat.
Đừng sửa cấu hình mạng container. Đừng chạy stack này trên máy có địa chỉ công khai.

---

## 5. Vận hành

### 5.1 Phê duyệt tự động vẫn dùng được và vẫn nguy hiểm

`--yes` bỏ qua người vận hành. Nó **không giả làm** người: `metrics.json` ghi
`decided_by: ["cli-auto"]` và báo cáo in một dòng cảnh báo. Nhưng nó vẫn gửi request thật.
Chỉ dùng trong môi trường tự động, trên đích tự dựng.

### 5.2 Bước analyze chiếm ~95 % thời gian

Một lần chạy đầy đủ mất khoảng 4,5 phút, gần như toàn bộ nằm ở 21 lời gọi LLM tuần tự
theo nhóm. Đây là giới hạn thông lượng, không phải giới hạn đúng/sai.

### 5.3 Coverage không theo được vào tiến trình con

`normalizer.py` và `finding_schema.py` hiện báo 0 % coverage. Chúng **không** phải mã
chết — chúng chạy qua subprocess CLI trong integration test, và `coverage` không theo được
vào tiến trình con. Tổng coverage thật cao hơn con số 80 % được báo.

---

## 6. Những gì chưa từng được đo

Ghi ra để không ai tưởng nhầm là đã kiểm:

- **Chưa chạy trên một codebase nào ngoài WebGoat.** Mọi số liệu chất lượng chỉ nói về
  WebGoat, với rule OpenGrep hiện tại.
- **Chưa thử với model nào ngoài `qwen/qwen3-235b-a22b-2507`.** `.env.example` từng mặc
  định DeepSeek; ai clone theo nó sẽ không tái lập được cùng số liệu.
- **Chưa đo hành vi khi Gateway hoặc WebGoat sập giữa chừng.** State trên đĩa được thiết
  kế để chịu được, nhưng chưa có test cho tình huống đó.
- **Chưa có kiểm thử tải hay chạy song song nhiều lần chạy cùng lúc.**
