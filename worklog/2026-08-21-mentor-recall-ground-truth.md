# Worklog — Tích hợp bộ ground truth của mentor để đo recall

**Ngày:** 2026-08-21 · **Agent/Model:** Claude Code · Opus 5 ·
**Branch:** `feat/handoff-hardening` · **Task ID:** `recall`

> **Ghi chú sau (2026-08-21):** thư mục đã đổi tên thành
> [`eval/ground-truth/recall/`](../eval/ground-truth/recall/) — tên nói bộ nhãn
> dùng để làm gì thay vì nói ai làm ra nó. Ghi công vẫn ở `PROVENANCE.md`.
> Các đường dẫn `eval/ground-truth/mentor/` bên dưới là đường dẫn tại thời điểm
> viết worklog này.

---

## 1. Tóm tắt

Người dùng đưa bộ ground truth WebGoat do mentor làm (https://github.com/dmk1en/gt) và
hỏi có dùng được không. **Dùng được, và nó lấp đúng lỗ hổng lớn nhất trong bộ đánh giá:**
bộ nhãn của nhóm chỉ đo precision, không thể đo recall. Kết quả đo được: hệ thống chỉ
thấy **14/75 (18,7 %)** số lỗ hổng có thật, bỏ sót 2 critical và 34 high.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** trả lời câu "trong số lỗ hổng thực sự tồn tại, hệ thống
  nói cho ta biết bao nhiêu?" — câu mà mọi bộ nhãn hiện có đều không trả lời được.
- **Nằm ở đâu trong luồng:** ngoài luồng chạy; là tầng đo lường trên artifact của lần chạy.
- **Không có nó thì hỏng gì:** báo cáo bàn giao công bố precision 56–75 % mà không nói
  hệ thống chỉ thấy 18,7 % số lỗ hổng. Người đọc sẽ hiểu nhầm rằng "không tìm thấy gì"
  nghĩa là "sạch".
- **Ngoài phạm vi (cố ý không làm):** thêm rule OpenGrep để nâng recall. Đó là việc lớn
  riêng, và cần đo trước rồi mới sửa.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung |
|---|---|---|
| `eval/ground-truth/mentor/` | Tạo | Vendor v2 (79 mục) + v1 (70 mục) + README gốc + `PROVENANCE.md` |
| `eval/recall.py` | Tạo | Nạp bộ nhãn, lọc theo submodule, chấm scanner recall và end-to-end recall |
| `eval/score_ground_truth.py` | Sửa | Thêm `--findings`/`--recall-truth`; in cả precision lẫn recall |
| `Makefile` | Sửa | `score-ground-truth` tự tìm `findings.json` cùng thư mục |
| `tests/integration/test_recall_scoring.py` | Tạo | 11 test |
| `tests/test_ground_truth_stays_out_of_the_scan.py` | Tạo | 4 test canh tính chất blind-scan |
| `reports/week-06/report.md` | Sửa | Thêm §4.6; recall thành giới hạn số 1 ở §6 |
| `docs/limitations.md` | Sửa | Recall lên **mục 1** — nó là giới hạn lớn nhất |
| `docs/product-brief.md`, `README.md` | Sửa | Thêm cảnh báo bao phủ; đổi ưu tiên số 1 thành "thêm rule" |

---

## 4. Làm như thế nào

**Cách tiếp cận:** không tin README, đo trước. Ba câu hỏi phải trả lời trước khi tích hợp:

1. **Đường dẫn có khớp submodule không?** Có — chỉ 11/197 lệch, do mentor dựng trên một
   bản WebGoat khác (lesson `openredirect`, `securitymisconfiguration`).
2. **Nó đo được thứ bộ hiện có không đo được không?** Có. Bộ của nhóm chứa **đúng** 23
   cảnh báo scanner đã báo, nên nó không thể biết gì về cái bị bỏ sót.
3. **Đưa vào repo có phá tính chất blind-scan mentor cảnh báo không?** Không. Scanner chỉ
   quét `benchmarks/targets/webgoat` và lọc output theo đúng tiền tố đó, nên `eval/` nằm
   ngoài phạm vi. Đã thêm test canh.

**Các quyết định kỹ thuật:**

- **Tách scanner recall khỏi end-to-end recall.** Gộp làm một chỉ ra "bỏ sót nhiều" mà
  không nói sửa ở đâu. Tách ra thì rõ: hỏng ở scanner → thêm rule; hỏng ở end-to-end →
  chỉnh Agent. Lần chạy này hai số bằng nhau, nên toàn bộ khoảng cách nằm ở scanner.
- **Lọc bỏ mục trỏ tới file không tồn tại.** Giữ lại thì chúng thành false negative vĩnh
  viễn và làm recall xấu đi **sai sự thật** — hệ thống bị trách vì không tìm ra thứ không
  có trong mã nguồn.
- **Dùng v2, không tự gộp v1.** v2 bỏ 4 mục vẫn trỏ tới file có thật. Tự đặt lại chúng là
  ghi đè phán đoán của mentor mà không biết vì sao, nên thay vào đó ghi câu hỏi vào
  `PROVENANCE.md`. Hệ quả: recall hiện tại có thể **hơi lạc quan**.
- **Record bị mất tính là "người đọc không biết".** Nếu scanner báo mà không record nào
  phủ finding đó (record mất ở bước analyze), lỗ hổng vẫn không tới được người đọc, nên
  nó được tính vào `dismissed_by_agent` chứ không được tính là đã báo cáo.

---

## 5. Output là gì

```bash
make score-ground-truth ANALYSIS=artifacts/runs/<run-id>/analysis.jsonl
```

**Output thật:**

```text
=== Recall — đối chiếu bộ nhãn lỗ hổng của mentor ===
  Lỗ hổng đã biết trong WebGoat : 75
  Scanner tìm tới               : 14/75 (18.7%)
  Scanner bỏ sót                : 61/75
  Tới được báo cáo cuối         : 14/75 (18.7%)

  Bỏ sót theo mức nghiêm trọng:
    critical : 2
    high     : 34
    medium   : 17
    low      : 8
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** vendor bộ nhãn kèm ghi nguồn đầy đủ, viết một module đo riêng, và đưa
recall lên **đầu** danh sách giới hạn.

**Lý do:** trước khi có bộ này, phần đánh giá của project chỉ đo precision và hoàn toàn im
lặng về bao phủ. Một báo cáo nói "over-claim giảm từ 100 % xuống 25 %" mà không nói "chúng
tôi chỉ thấy 18,7 % số lỗ hổng" là một báo cáo gây hiểu nhầm — đúng loại vấn đề mà cả đợt
review này đang sửa.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Gộp bộ mentor vào `webgoat-findings.json` | Một bộ duy nhất | Hai bộ đo hai thứ; gộp là mất cả hai chỉ số |
| Gộp v1 + v2 | Bao phủ rộng nhất | Ghi đè quyết định của mentor mà không biết lý do |
| Không commit, chỉ đọc đường dẫn ngoài | Không đụng bản quyền | Mentor clone repo sẽ không chạy lại được số recall |
| Thêm rule OpenGrep luôn cho recall đẹp | Số đẹp hơn | Sửa trước khi đo xong; và làm mốc nền biến mất |

**Đánh đổi đã chấp nhận:** vendor dữ liệu của người khác vào repo khi repo gốc **không có
LICENSE**. Đã ghi rõ trong `PROVENANCE.md` rằng cần xin xác nhận tác giả trước khi push
lên remote công khai, và bộ chấm hỗ trợ sẵn đường dẫn ngoài repo nếu phải gỡ ra.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả thật |
|---|---:|---|
| `pytest -m "not llm and not live_gateway" -q` | 0 | `597 passed` (trước: 582) |
| `make gateway-live-test` | 0 | `8 passed` |
| `make guardrails-test` | 0 | `120 passed` |
| `make lint` / `make typecheck` | 0 | sạch |
| `make coverage` | 0 | `80.72 %` |
| `make score-ground-truth …` | 0 | in cả precision lẫn recall |

**Test mới thêm (15):**

- `test_recall_scoring.py` — bộ nhãn nạp được · mục ngoài submodule bị lọc · lỗ hổng không
  ai quét là scanner miss · `related_files` cũng tính là chạm tới · Agent gạt đi lỗ hổng
  thật là end-to-end miss · bỏ sót được gom theo loại và theo mức · chốt con số thật.
- `test_ground_truth_stays_out_of_the_scan.py` — script quét chỉ nhắm submodule · bộ nhãn
  nằm ngoài cây bị quét · không file giống đáp án nào lọt vào đích · bộ lọc output vẫn
  ghim tiền tố.

**Bất biến đã giữ:** tính chất blind-scan của mentor · không lộ secret · không đụng
`reports/week-01..05/` · không push.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** ghép lỗ hổng với finding theo **đường dẫn file**, không theo
  dòng. Một file có hai lỗ hổng khác nhau mà scanner chỉ bắt được một thì cả hai vẫn được
  tính là "đã tìm tới" — nên **recall thật có thể thấp hơn 18,7 %**.
- **Điểm cần mentor quyết định:** v2 có thay thế hẳn v1 không? Bốn mục `missingac-004`,
  `sqlinjection-013`, `xxe-002`, `xxe-003` bị rút khỏi v2 nhưng vẫn trỏ tới file có thật.
- **Việc còn nợ:** nâng recall bằng cách thêm rule OpenGrep. Đã đưa lên ưu tiên số 1 trong
  `docs/product-brief.md` nhưng chưa làm.
- **Câu hỏi cho người dùng:** repo gốc không có LICENSE — cần xin phép tác giả trước khi
  push nhánh này lên remote công khai.
