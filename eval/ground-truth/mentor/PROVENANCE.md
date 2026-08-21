# Nguồn gốc bộ dữ liệu này

Bộ này **không phải do nhóm Project Sentinel tạo ra**. Nó được sao chép nguyên văn từ
công trình của mentor.

| | |
| :--- | :--- |
| **Tác giả** | Dương Mạnh Kiên (VinSOC-NC&UDAI-PTUD) |
| **Nguồn** | https://github.com/dmk1en/gt |
| **Commit** | `ab1b674` (2026-07-21, "v2") |
| **Lấy về ngày** | 2026-08-21 |
| **Giấy phép** | **Repo gốc không có file LICENSE.** Xem mục "Điều cần xác nhận" bên dưới. |

## File trong thư mục này

| File | Nội dung |
| :--- | :--- |
| `webgoat-vulnerabilities.jsonl` | Bản **v2**, 79 mục. Đây là bản đang được dùng. |
| `webgoat-vulnerabilities-v1.jsonl` | Bản **v1**, 70 mục. Giữ lại để đối chiếu, không dùng để chấm. |
| `UPSTREAM-README.md` | README gốc của mentor, chép nguyên văn. |

## Vì sao bộ này có mặt ở đây

Project Sentinel có sẵn một bộ nhãn khác trong
[`../webgoat-findings.json`](../webgoat-findings.json). Hai bộ **đo hai thứ khác nhau**:

| | `webgoat-findings.json` (nhóm tự làm) | `webgoat-vulnerabilities.jsonl` (mentor) |
| :--- | :--- | :--- |
| Nội dung | Đúng 23 cảnh báo OpenGrep **đã báo** | Lỗ hổng **thực sự tồn tại** trong WebGoat |
| Cách lập | Đọc source tại từng `file:line` | Đối chiếu `.adoc` và hint `.properties` của chính WebGoat |
| Trả lời câu hỏi | "Cái được báo có thật không?" | "Cái có thật có được tìm ra không?" |
| Chỉ số | **Precision** | **Recall** |

Bộ của nhóm **về mặt cấu trúc không thể** đo recall: nó chỉ chứa những gì scanner đã tìm
ra, nên theo định nghĩa nó không biết gì về những lỗ hổng bị bỏ sót. Bộ của mentor lấp
đúng chỗ đó.

## v2 khác v1 chỗ nào

v2 **không** bao trọn v1. Nó thêm 17 mục và **bỏ 8 mục**. Bốn mục bị bỏ vẫn trỏ tới file
có thật trong submodule WebGoat mà repo này đang ghim:

- `missingac-004` — Security by Obscurity via Client-Side Hidden Menus
- `sqlinjection-013` — SQL Injection via Incomplete/Bypassable Keyword Filter
- `xxe-002` — XML External Entity (XXE) Injection
- `xxe-003` — Blind XXE Injection

Bốn mục còn lại (`openredirect-002..005`) trỏ tới file **không tồn tại** trong submodule
này, nên nhiều khả năng v2 được dựng lại trên một phiên bản WebGoat khác.

Nhóm dùng **v2 làm bản chính** vì đó là bản mentor commit sau cùng, và **không tự gộp v1
vào** — việc mentor rút bốn mục kia có thể là một quyết định có lý do, và tự đặt lại chúng
là ghi đè phán đoán của mentor mà không biết vì sao.

> **Câu cần hỏi mentor:** v2 có thay thế hẳn v1 không, hay bốn mục trên bị rút do dựng lại
> trên phiên bản WebGoat khác? Nếu chúng vẫn hợp lệ thì con số recall hiện tại đang **hơi
> lạc quan** — mẫu số bị thiếu bốn lỗ hổng.

## Tính chất blind-scan vẫn được giữ

README gốc cảnh báo: *"Do not copy this file or its contents into the scan target repo…
doing so defeats the blind-scan test."*

Cảnh báo đó vẫn được tôn trọng. Scanner của Project Sentinel chỉ quét
`benchmarks/targets/webgoat` và lọc kết quả theo đúng tiền tố đó
([`scripts/scan-opengrep.sh`](../../../scripts/scan-opengrep.sh)). Thư mục `eval/`
nằm ngoài phạm vi quét, nên Agent không bao giờ đọc được bộ nhãn này. Có test canh điều
kiện đó: `tests/test_ground_truth_stays_out_of_the_scan.py`.

## Điều cần xác nhận

Repo gốc **không có file LICENSE**, nên về mặt pháp lý mặc định là "bảo lưu mọi quyền".
Bộ này được đưa vào đây theo yêu cầu trực tiếp của chủ repo, người có quan hệ trực tiếp
với tác giả.

**Trước khi push lên bất kỳ remote công khai nào, hãy xin xác nhận của tác giả.** Nếu
tác giả không đồng ý, xoá thư mục này và truyền đường dẫn ngoài repo qua
`--recall-truth` — bộ chấm đã hỗ trợ sẵn cách đó.
