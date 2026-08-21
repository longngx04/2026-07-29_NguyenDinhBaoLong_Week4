# Giới hạn đã biết và rủi ro còn tồn tại

**Cập nhật:** 2026-08-21 · Mọi số liệu dưới đây lấy từ lần chạy thật, không suy đoán.

Tài liệu này viết cho người sắp dùng Project Sentinel để ra quyết định. Nó liệt kê những
gì hệ thống **không** làm được, kèm bằng chứng. Phần nào chưa đo được thì ghi là chưa đo.

---

## 1. Bao phủ — giới hạn lớn nhất

### 1.1 Hệ thống chỉ thấy 18,7 % số lỗ hổng có thật

Đối chiếu với bộ nhãn recall (75 lỗ hổng WebGoat đã biết, dựng từ chính tài
liệu `.adoc` và file hint của WebGoat, độc lập với mọi scanner):

| Chỉ số | Giá trị |
| :--- | ---: |
| Lỗ hổng đã biết | 75 |
| Scanner tìm tới | **14 (18,7 %)** |
| Bỏ sót | **61** — gồm 2 critical, 34 high |
| Tới được báo cáo cuối | 14 (18,7 %) |

**Precision cao không bù được cho recall thấp.** Một hệ thống chỉ thấy chưa tới một phần
năm số lỗ hổng thì việc "những gì nó nói thì đáng tin" **không** có nghĩa là "nó nói đủ".
Đừng dùng sản phẩm này như bằng chứng rằng một codebase đã sạch.

### 1.2 Nguyên nhân là bộ rule, không phải Agent

[`configs/opengrep/java-security.yml`](../configs/opengrep/java-security.yml) hiện có
**ba rule**: command execution, SQL statement execution, unsafe deserialization. Những lớp
lỗ hổng dưới đây **hoàn toàn vô hình** với hệ thống vì không có rule nào bắt chúng:

XSS phản chiếu · JWT bỏ qua xác minh chữ ký (`alg=none`) · PRNG yếu cho mục đích bảo mật ·
CSRF · auth bypass · IDOR / broken access control · XXE · thuật toán băm lỗi thời ·
lộ khoá riêng · path traversal · SSRF.

Đây là việc **sửa được**: thêm rule là tăng recall. Nhưng ở thời điểm bàn giao thì chưa làm.

### 1.3 Bộ nhãn recall có thể còn thiếu

Bộ v2 bỏ 4 mục có trong v1 mà vẫn trỏ tới file có thật trong submodule
(`missingac-004`, `sqlinjection-013`, `xxe-002`, `xxe-003`). Nếu 4 mục đó vẫn hợp lệ thì
recall thật **thấp hơn** 18,7 %. Chi tiết:
[`eval/ground-truth/recall/PROVENANCE.md`](../eval/ground-truth/recall/PROVENANCE.md).

---

## 2. Chất lượng phán đoán của Agent

### 2.1 Kết quả dao động giữa các lần chạy

Cùng mã nguồn, cùng 23 cảnh báo đầu vào, chạy lại nhiều lần cho kết quả khác nhau:

| Chỉ số | Khoảng đo được |
| :--- | :--- |
| Triage precision | 56,5 % – 75,0 % |
| Over-claim rate | 25,0 % – 33,3 % |
| Số record sinh ra | 19 – 21 trên 21 nhóm |
| `invalid_output_count` | 0 – 2 |

**Không bảng kết quả nào của hệ thống này là một cam kết.** Mỗi bảng là một lần lấy mẫu.
Khi báo cáo, hãy chạy `make eval REPEAT=n` và đọc phần phân bố, đừng trích một lần chạy.

### 2.2 `label accuracy` không phải `precision`

Bộ chấm in ra một con số từng được gọi là `triage_precision`. Nó thực chất là
**accuracy nhiều lớp** — tỷ lệ record mà kết luận của Agent trùng nhãn người review.
Nó **không** phải precision theo nghĩa thống kê, và không nên trích dẫn như vậy.
Con số đáng lo là **over-claim rate**, đo riêng.

### 2.3 Agent vẫn trình bày một phần false positive như lỗ hổng thật

Over-claim rate hiện tại **25–33 %**: cứ ba cảnh báo thật sự là false positive thì khoảng
một cái vẫn được trình bày như lỗ hổng có thật. Con số này đã giảm từ 100 % ở mốc nền,
nhưng nó chưa về 0 và **sẽ không về 0** với cách tiếp cận hiện tại.

Hai ca hỏng lặp lại là `opengrep-014` và `opengrep-016`: một truy vấn **hằng** nằm ngay
cạnh một điểm nguy hiểm có thật trong cùng một hàm.

Trước đây chúng thừa hưởng `confirmed/high` vì bị **gộp chung nhóm** với lỗ hổng thật —
schema chỉ cho một kết luận mỗi nhóm. Việc gộp đó đã bị tắt. Nhưng ở lần chạy sau khi
sửa, Agent **vẫn** tự xếp chúng là `likely/high`. Nguyên nhân máy móc đã hết; nguyên
nhân phán đoán thì chưa, và nó sẽ không hết nếu không có phân tích taint thật.

### 2.4 Tầng hiệu chỉnh không chặn được lời khai sai

`analysis/calibration.py` chỉ hạ kết luận **khi Agent tự thừa nhận thiếu bằng chứng**
(`attacker_control: not_proven`) hoặc khi văn xuôi của nó tự mâu thuẫn. Một Agent khai
thẳng `attacker_control: proven` cho một truy vấn hằng sẽ **đi qua toàn bộ ba lớp** — vì
mọi ID, vị trí và CWE nó dùng đều có thật.

Đây là giới hạn về nguyên tắc, không phải lỗi cần vá: **không có phân tích taint thật**
thì phía Python không có cách nào độc lập kiểm chứng lời khai đó.

### 2.5 Bộ ground truth precision là một điểm tin cậy đơn

23 nhãn trong [`eval/ground-truth/webgoat-findings.json`](../eval/ground-truth/webgoat-findings.json)
do **một người** đặt, không có người thứ hai đối chiếu. Nếu một nhãn sai thì mọi con số
tính từ nó đều lệch theo. Bốn ca `needs_review` (`opengrep-002`, `003`, `005`, `020`) là
những ca tranh luận được nhất: chúng có thể là `true_positive` nếu đọc thêm tầng đăng ký
người dùng hoặc tầng gọi hàm.

---

## 3. Phạm vi kiểm chứng

### 3.1 Mỗi lần chạy chỉ gửi một request

23 cảnh báo → 21 nhóm → nhiều đề xuất → **một** request được gửi. Tỷ lệ bao phủ theo
finding khoảng **4 %**.

### 3.2 Probe gần như luôn `inconclusive`

Hệ thống nay tự nói ra điều này thay vì để người đọc hiểu nhầm, nhưng sự thật không đổi:
với môi trường WebGoat hiện tại, kết quả probe hầu như luôn là `inconclusive`.

Lý do: WebGoat yêu cầu đăng nhập, nên các endpoint chứa lỗ hổng trả HTTP 302; các endpoint
trả 200 (`/WebGoat/login`, `/WebGoat/actuator/health`) không liên quan tới lỗ hổng trong
mã nguồn. `supports`/`refutes` chỉ đạt tới được khi Agent khai trước `expected_signal`
**và** endpoint đó xuất hiện trong bằng chứng của finding — điều chưa xảy ra lần nào.

**Kết quả probe hiện tại chứng minh Gateway tới được ứng dụng và response được lọc.**
Nó không khẳng định lỗ hổng nào tồn tại.

---

## 4. Redaction và dữ liệu nhạy cảm

### 4.1 Redaction dựa trên mẫu, nên có trần

Bộ che nhận diện email, JWT, khoá kiểu `sk-`/`ghp_`, chuỗi hex ≥32, trường password, số
điện thoại Việt Nam và một số dạng số dài. **Một định dạng bí mật ngoài danh sách đó sẽ
lọt.** Đây là giới hạn về nguyên tắc của mọi bộ che dựa trên mẫu.

Điều đã được kiểm chứng bằng test: với các dạng **đã biết**, không byte nào chạm đĩa —
`tests/unit/orchestrator/test_probe_scrub_redaction_chain.py` quét **mọi** file trong thư
mục lần chạy để tìm canary.

### 4.2 Response bị cắt còn 512 byte

Chỉ 512 byte đầu của response được giữ. Bộ che chạy trên **toàn bộ** body trước khi cắt
(đổi lại chi phí regex trên tối đa 64 KiB), nên không có mảnh bí mật nào bị xé đôi ở mốc
cắt. Nhưng phần sau 512 byte thì không ai xem, kể cả để phát hiện injection.

---

## 5. Ranh giới thực thi

### 5.1 `SENTINEL_SCAN_COMMAND` chạy được một chương trình bất kỳ

Lệnh quét lấy từ biến môi trường. Tham số shell đã bị chặn, nhưng **kẻ kiểm soát được môi
trường và hệ thống file vẫn chỉ định được một chương trình bất kỳ để chạy.**

Đây là **rủi ro còn tồn tại được chấp nhận có ý thức**, không phải lỗi bị bỏ sót. Ai kiểm
soát được biến môi trường của tiến trình thì thường đã chạy được lệnh theo nhiều đường
khác. Nếu triển khai ở nơi ranh giới đó có ý nghĩa, hãy cố định lệnh quét trong mã.

### 5.2 WebGoat là ứng dụng cố ý có lỗ hổng

`docker-compose.yml` buộc Gateway bind loopback và **không** mở cổng host cho WebGoat.
Đừng sửa cấu hình mạng container. Đừng chạy stack này trên máy có địa chỉ công khai.

---

## 6. Vận hành

### 6.1 Phê duyệt tự động vẫn dùng được và vẫn nguy hiểm

`--yes` bỏ qua người vận hành. Nó **không giả làm** người: `metrics.json` ghi
`decided_by: ["cli-auto"]` và báo cáo in một dòng cảnh báo. Nhưng nó vẫn gửi request thật.
Chỉ dùng trong môi trường tự động, trên đích tự dựng.

### 6.2 Bước analyze chiếm ~95 % thời gian

Một lần chạy đầy đủ mất khoảng 4,5 phút, gần như toàn bộ nằm ở 21 lời gọi LLM tuần tự
theo nhóm. Đây là giới hạn thông lượng, không phải giới hạn đúng/sai.

### 6.3 Đề xuất kiểm chứng của Agent phần lớn bị từ chối

Lần chạy cuối: **17/23 objective** bị allowlist từ chối, chủ yếu vì Agent đề xuất
`special_chars` cho `POST /WebGoat/attack` trong khi registry chỉ duyệt `empty_value`
và `long_string` cho endpoint đó.

Chúng **không** làm mất record — objective bị đặt `null` và đếm lại — nhưng nó nghĩa là
Agent đọc chưa đúng phần `allowed_endpoints` của packet. Con số này nay hiện trong
`metrics.json` (`llm.invalid_objectives`) thay vì bị im lặng lọc muộn ở bước propose.

### 6.4 Coverage không theo được vào tiến trình con

`normalizer.py` và `finding_schema.py` hiện báo 0 % coverage. Chúng **không** phải mã
chết — chúng chạy qua subprocess CLI trong integration test, và `coverage` không theo được
vào tiến trình con. Tổng coverage thật cao hơn con số 80 % được báo.

---

## 7. Những gì chưa từng được đo

Ghi ra để không ai tưởng nhầm là đã kiểm:

- **Chưa chạy trên một codebase nào ngoài WebGoat.** Mọi số liệu chất lượng chỉ nói về
  WebGoat, với rule OpenGrep hiện tại.
- **Chưa thử với model nào ngoài `qwen/qwen3-235b-a22b-2507`.** `.env.example` từng mặc
  định DeepSeek; ai clone theo nó sẽ không tái lập được cùng số liệu.
- **Chưa đo hành vi khi Gateway hoặc WebGoat sập giữa chừng.** State trên đĩa được thiết
  kế để chịu được, nhưng chưa có test cho tình huống đó.
- **Chưa có kiểm thử tải hay chạy song song nhiều lần chạy cùng lúc.**
