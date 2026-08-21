# Project Sentinel — Bản mô tả sản phẩm

**Cập nhật:** 2026-08-21 · Một trang cho người quyết định, một trang cho người triển khai.

---

## Vấn đề

Chạy một công cụ SAST lên một codebase vừa phải cho ra hàng chục tới hàng trăm cảnh báo,
tất cả đều mang nhãn nghiêm trọng như nhau. Trên OWASP WebGoat, OpenGrep cho **23 cảnh
báo và gán `high` cho cả 23**. Sau khi đọc mã nguồn tại từng vị trí, thực tế là:

- **13** là lỗ hổng thật,
- **6** là báo động giả — điểm nguy hiểm chỉ nhận chuỗi hằng, dù file tên là `SqlInjection…`,
- **4** chưa kết luận được nếu không đọc thêm mã ngoài đoạn được trích.

Nghĩa là **hơn 40 % thời gian của người trực bảo mật bị tiêu vào những cảnh báo không dẫn
tới đâu** — và không có cách nào biết trước cái nào là cái nào ngoài việc đọc từng cái.

## Sản phẩm làm gì

Project Sentinel đặt một Agent LLM vào giữa scanner và người đọc. Với mỗi nhóm cảnh báo, nó:

1. **Đọc mã nguồn quanh vị trí** cảnh báo và tra kho tri thức bảo mật nội bộ.
2. **Kết luận rõ ràng** bằng bốn mức: `confirmed` · `likely` · `needs_review` · `false_positive`,
   kèm hai lời khai tách bạch: dữ liệu tới điểm nguy hiểm **có do kẻ tấn công kiểm soát
   không**, và đoạn mã đó **có đạt tới được không**.
3. **Đề xuất một request kiểm chứng** nếu có endpoint phù hợp — rồi dừng lại chờ người duyệt.
4. **Dựng một báo cáo** nói rõ điều gì đã được chứng minh và điều gì chưa.

Đầu ra là một báo cáo mà người đọc có thể **xếp thứ tự ưu tiên**, thay vì một danh sách
phẳng toàn `high`.

## Ai dùng

| Người dùng | Dùng để làm gì |
| :--- | :--- |
| **Kỹ sư bảo mật ứng dụng** | Phân loại output SAST trước khi giao việc cho đội phát triển |
| **Đội phát triển** | Đọc một finding kèm giải thích và cách khắc phục, thay vì một mã rule |
| **Người vận hành / trực ca** | Duyệt hay từ chối từng request kiểm chứng, với đủ ngữ cảnh |

## Giá trị đo được

Trên 23 cảnh báo WebGoat, so với mốc nền (mọi cảnh báo đều `high`, không có kết luận):

| Chỉ số | Mốc nền | Hiện tại |
| :--- | ---: | ---: |
| False positive được trình bày như lỗ hổng thật | **100 %** | **25–33 %** |
| Cảnh báo mang kết luận rõ ràng | 0 % | 100 % |
| Xác định đúng khả năng kiểm soát đầu vào | — | **82–90 %** |
| Xếp đúng mức nghiêm trọng | 57 % | **74–85 %** |

**Nhưng bao phủ mới là con số cần nhìn trước:** đối chiếu bộ nhãn lỗ hổng độc lập,
hệ thống hiện **chỉ thấy 14/75 (18,7 %)** số lỗ hổng có thật trong WebGoat. Nguyên nhân
là bộ rule scanner chỉ có ba rule, không phải Agent. Sản phẩm này **thu hẹp việc phải
đọc, nó không chứng minh một codebase đã sạch.**

Đọc kèm: các con số này **dao động giữa các lần chạy**. Xem
[`limitations.md`](limitations.md) §1.1.

## Điều làm sản phẩm này khác

Phần lớn công cụ "AI bảo mật" để mô hình vừa phán đoán vừa hành động. Ở đây, **output của
mô hình là dữ liệu không đáng tin**:

- Mọi giá trị mô hình đề xuất mà thực thi được đều bị **đối chiếu lại từng field** với một
  danh sách đã review ở phía Python trước khi có request nào tồn tại.
- Một **allowlist thứ hai độc lập** ở tầng Nginx chặn lại lần nữa. Bằng chứng cho việc một
  request bị chặn là access log không có thêm dòng nào — bằng chứng ở hạ tầng, không phải
  một biến đếm trong Python.
- Kết luận của Agent bị **hiệu chỉnh xác định phía Python**, và tầng đó **chỉ hạ, không
  bao giờ nâng**.
- Nội dung lấy từ ứng dụng đích được quét prompt injection, cắt bỏ chỉ dẫn, che dữ liệu
  nhạy cảm, rồi bọc trong thẻ `<untrusted_app_response>` trước khi bất kỳ mô hình nào nhìn thấy.
- **Cổng phê duyệt nằm trong công cụ, không nằm ở giao diện.** Nó ràng buộc bằng dấu vân
  tay tính từ method + path + payload thật, nên không thể duyệt một request rồi gửi request khác.

## Phạm vi hiện tại

**Có:** pipeline chín bước chạy bằng một câu lệnh · phân loại và giải thích finding · một
request kiểm chứng có người duyệt mỗi lần chạy · bộ guardrail đầy đủ · báo cáo và số liệu ·
bộ chấm chất lượng trên nhãn người review.

**Chưa có:** phân tích taint · nhiều request kiểm chứng mỗi lần chạy · ngôn ngữ ngoài Java ·
đích ngoài WebGoat · giao diện web · chạy nhiều lần song song.

## Rủi ro cần biết trước khi dùng

1. **Sản phẩm vẫn trình bày sai khoảng một phần ba số false positive.** Nó thu hẹp việc
   phải đọc, không thay thế việc đọc.
2. **Kết quả không tất định.** Cùng đầu vào, cùng mã nguồn, hai lần chạy cho hai kết quả khác nhau.
3. **Bước kiểm chứng gần như luôn `inconclusive`** với môi trường đích hiện tại. Hệ thống
   nói thẳng điều đó thay vì để người đọc hiểu nhầm, nhưng giá trị kiểm chứng vẫn còn thấp.
4. **Bao phủ chỉ 18,7 %.** Không dùng kết quả "không tìm thấy gì" như bằng chứng an toàn.

Đầy đủ: [`limitations.md`](limitations.md).

## Hướng đi tiếp, theo thứ tự giá trị

| Ưu tiên | Việc | Vì sao |
| :--- | :--- | :--- |
| **Cao nhất** | **Thêm rule cho scanner** (XSS, JWT, CSRF, crypto, access control) | **Bỏ sót 61/75 lỗ hổng — giới hạn lớn nhất, và sửa được** |
| Cao | Nhiều request kiểm chứng mỗi lần chạy | Bao phủ hiện chỉ ~4 % số finding |
| Cao | Đích có phiên đăng nhập sẵn để probe chạm được endpoint có lỗ hổng | Để `supports`/`refutes` đạt tới được |
| Trung bình | Phân tích taint/dataflow nhẹ ở phía Python | Kiểm chứng độc lập lời khai `attacker_control` của Agent |
| Trung bình | Người thứ hai đối chiếu bộ ground truth | Hiện là điểm tin cậy đơn |
| Thấp | Giao diện web đọc artifact | Tăng trực quan; không sửa được vấn đề nào ở trên |
