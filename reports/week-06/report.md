# Week 6 Report — Orchestrator, CLI và bộ đánh giá

**Project:** Sentinel · **Updated:** 21/08/2026 · **Status:** Đang hoàn thiện

Báo cáo này ghi lại các giới hạn quan sát được từ artifact và những lần chạy thật. Các con số
dưới đây không được diễn giải rộng hơn phạm vi bằng chứng đã nêu.

## Giới hạn đã biết

1. **Mỗi lần chạy chỉ gửi một probe.** Lần chạy `20260821T024650Z` đi từ 23 finding thô tới
   21 nhóm phân tích và 18 objective được đề xuất, nhưng chỉ một probe được gửi. Tỷ lệ bao phủ
   theo finding vì vậy xấp xỉ **4%** (`1/23`); 22 finding còn lại không nhận được bằng chứng từ
   probe trong lần chạy đó.

2. **Probe hiện chưa khẳng định hay bác bỏ được một finding cụ thể.** WebGoat yêu cầu đăng nhập,
   nên `POST /WebGoat/attack` trả HTTP 302. Hai endpoint trả HTTP 200 là `/WebGoat/login` và
   `/WebGoat/actuator/health`, nhưng chúng không liên quan tới finding về lỗ hổng trong mã nguồn.
   Kết quả hiện tại chỉ chứng minh Gateway có thể tới ứng dụng và nhận response, không chứng minh
   lỗ hổng tồn tại hoặc đã được loại trừ.

3. **Bộ đánh giá dùng LLM thật nên kết quả bất định.** Cùng sáu ca và cùng code, hai lần chạy
   liên tiếp cho kết quả **6/6 (0 FP, 0 FN)** và **5/6 (0 FP, 1 FN)**. False negative nằm ở ca
   `06-injection-in-finding`: trong lần 5/6, Agent không sinh record cho finding đó. Không được
   dùng snapshot 6/6 như cam kết rằng lần chạy sau sẽ lặp lại kết quả này.

4. **Màn hình web chưa được triển khai.** Plan 4 chưa bắt đầu; việc xem run, phê duyệt và đọc
   security events hiện vẫn dựa trên CLI và artifact trong thư mục run.
