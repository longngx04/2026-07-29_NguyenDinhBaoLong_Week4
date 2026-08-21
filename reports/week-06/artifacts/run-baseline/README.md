# Mốc nền `20260821T045519Z` — trạng thái TRƯỚC khi harden

Đây là lần chạy được trích dẫn làm mốc nền trong
[`../../report.md`](../../report.md) §4.4: **over-claim rate 100 %**, cả 5 cảnh báo
false positive khớp được record đều được trình bày ở mức `high`.

Bộ này được commit vì hai lý do:

1. **Báo cáo trích số từ nó.** Một con số không tái lập được từ bản clone là một
   con số người đọc phải tin lời.
2. **Test dựa vào nó.** `tests/integration/test_ground_truth_scoring.py` chốt lại
   mốc nền để không ai vô tình "cải thiện" nó bằng cách đổi cách đo. Trước đây các
   test đó đọc `artifacts/runs/` — thư mục bị Git ignore — nên suite chỉ xanh trên
   máy còn giữ artifact cũ, và fail trên fresh clone.

Bản chạy này **sinh trước** khi có `disposition`, nên các record ở đây không có
field đó. Bộ chấm xử lý đúng chuyện này: nó chấm theo **cách trình bày**
(`severity`) chứ không theo sự tồn tại của field — nếu không, một bản chạy cũ gán
`high` cho mọi thứ sẽ được báo "over-claim 0 %" chỉ vì thiếu dữ liệu.

Chỉ giữ bốn file cần cho việc chấm và cho việc kiểm chứng con số trong báo cáo.
