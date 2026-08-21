# Kịch bản trình diễn — 10–15 phút

**Cập nhật:** 2026-08-21 · Dùng cho buổi bàn giao. Mọi lệnh dưới đây đã chạy thật.

Kịch bản này trình diễn **cả đường Approve lẫn đường Reject** với người vận hành thật, chứ
không dùng `--yes`.

---

## Chuẩn bị (làm TRƯỚC buổi demo, ~10 phút)

Bước analyze mất khoảng 4,5 phút mỗi lần chạy. **Đừng chạy nó trực tiếp trên sân khấu.**

```bash
# 1. Môi trường
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env          # điền LLM_API_KEY
export SENTINEL_GATEWAY_API_KEY="$(openssl rand -hex 32)"

# 2. Hạ tầng đích
make target-up                # Gateway + WebGoat, chờ health check

# 3. Kiểm tra sẵn sàng — cả ba phải xanh
make lint typecheck
pytest -m "not llm and not live_gateway" -q
make gateway-live-test

# 4. Chuẩn bị sẵn MỘT lần chạy đã hoàn tất để nói tới khi cần
python -m project_sentinel.cli runs | head -3
```

> Nếu mạng hỏng giữa buổi: mọi thứ cần nói đều đã nằm trong
> `reports/week-06/artifacts/` và đọc được offline.

---

## Phần 1 — Vấn đề (2 phút)

**Thông điệp: scanner không nói cho bạn biết nên đọc cái nào trước.**

```bash
python -c "
import json,collections
d=json.load(open('reports/week-06/artifacts/run-approved/findings.json'))
c=collections.Counter(f['severity'] for f in d['findings'])
print('OpenGrep cho', len(d['findings']), 'canh bao:', dict(c))"
```

> 23 cảnh báo, cả 23 đều `high`. Không có thứ tự ưu tiên.

Mở [`eval/ground-truth/webgoat-findings.json`](../eval/ground-truth/webgoat-findings.json)
và chỉ vào `opengrep-011`:

```java
ResultSet results = stmt.executeQuery("SELECT * FROM access_log");
```

> Đây là một truy vấn hằng. Không có đầu vào nào. Nó nằm trong file tên
> `SqlInjectionLesson10.java`, nên rule bắt được — nhưng nó không phải lỗ hổng.
> Sáu trong 23 cảnh báo thuộc loại này.

---

## Phần 2 — Agent phân loại (2 phút)

**Thông điệp: kết luận tách rời khỏi mức của scanner.**

```bash
python -c "
import json,collections
rs=[json.loads(l) for l in open('reports/week-06/artifacts/run-approved/analysis.jsonl') if l.strip()]
print('disposition:', dict(collections.Counter(r['disposition'] for r in rs)))
print('severity   :', dict(collections.Counter(r['severity'] for r in rs)))
print('da hieu chinh:', sum(1 for r in rs if r.get('calibration')))"
```

Chỉ vào một record đã bị hạ:

```bash
python -c "
import json
rs=[json.loads(l) for l in open('reports/week-06/artifacts/run-approved/analysis.jsonl') if l.strip()]
r=[x for x in rs if x.get('calibration')][0]
print('title      :', r['title'])
print('disposition:', r['disposition'], '| severity:', r['severity'])
print('calibration:', r['calibration'])"
```

> Đây là hệ thống **hạ kết luận của chính Agent**, ở phía Python, theo luật xác định.
> Tầng này chỉ hạ, không bao giờ nâng — nên một luật sai chỉ làm mất độ nhạy, không bao
> giờ tự tạo ra một lỗ hổng giả.

---

## Phần 3 — Guardrails (3 phút)

**Thông điệp: ba lớp bảo vệ, mỗi lớp có bằng chứng riêng.**

```bash
make guardrails-demo          # dừng lại và HỎI bạn ở các bước rủi ro
```

Bảy bước, mỗi bước in một dòng pass/fail. Ba điểm cần nói khi nó chạy:

1. **Prompt injection trong response của ứng dụng** — chỉ dẫn bị cắt bỏ, không được làm theo.
2. **Che dữ liệu trước khi tới mô hình và trước khi chạm đĩa** — hai chốt khác nhau.
3. **Một request bị từ chối** — bằng chứng là **Nginx access log không có thêm dòng nào**.
   Đó là bằng chứng ở tầng hạ tầng, không phải một biến đếm bên trong Python.

```bash
make guardrails-test          # 120 test, trong đó có 6 ca bắt buộc của đề bài
```

---

## Phần 4 — Đường TỪ CHỐI (2 phút)

**Thông điệp: mặc định là từ chối, và từ chối nghĩa là không byte nào rời hệ thống.**

```bash
python -m project_sentinel.cli run
# tại cổng phê duyệt: gõ bất cứ thứ gì KHÁC 'approve', ví dụ: no
```

> Lưu ý: lần chạy này mất ~4,5 phút ở bước analyze. Nếu buổi demo eo hẹp, hãy bỏ qua và
> chỉ vào bằng chứng đã có sẵn:

```bash
cat reports/week-06/artifacts/run-rejected/metrics.json | python -m json.tool | head -20
cat reports/week-06/artifacts/run-rejected/probe-result.json
```

> `requests_total: 0`. `denied_reason: "Người vận hành đã từ chối request này."`
> Không có gì được gửi.

---

## Phần 5 — Đường PHÊ DUYỆT (3 phút)

**Thông điệp: người thật duyệt, và hệ thống ghi lại ai duyệt.**

```bash
python -m project_sentinel.cli run
# tại cổng phê duyệt: gõ approve
```

Hoặc dùng bằng chứng đã có:

```bash
python -c "
import json
m=json.load(open('reports/week-06/artifacts/run-approved/metrics.json'))
print('approvals:', m['approvals'])
print('requests :', m['requests_total'], 'gui,', m['requests_denied'], 'bi chan')"
```

> `decided_by: ["cli-operator"]`. Nếu ai đó dùng `--yes`, chỗ này ghi `cli-auto` và báo
> cáo in một dòng cảnh báo — hệ thống không giả vờ có người duyệt.

Chỉ vào cặp dấu vân tay:

```bash
python -c "
import json
a=json.load(open('reports/week-06/artifacts/run-approved/approval-request.json'))
d=json.load(open('reports/week-06/artifacts/run-approved/decision.json'))
print('yeu cau  :', a['method'], a['endpoint'])
print('van tay  :', a['request_fingerprint'][:16], '...')
print('quyet dinh khop:', a['request_fingerprint'] == d['request_fingerprint'])"
```

> Dấu vân tay tính từ method + path + payload **thật**. Duyệt một request rồi đổi payload
> thì phiếu duyệt cũ vô hiệu — không thể duyệt A gửi B.

---

## Phần 6 — Điều probe KHÔNG chứng minh (2 phút)

**Thông điệp: đây là phần trung thực nhất của hệ thống.**

```bash
python -c "
import json
d=json.load(open('reports/week-06/artifacts/run-approved/report.json'))
v=d['probe_verdict']
print('HTTP:', d['probe_status_code'])
print('Ket luan:', v['verdict'])
print('Ly do   :', v['reason'])"
```

> Request trả HTTP 200. Hệ thống vẫn ghi `inconclusive`, và nói rõ vì sao: endpoint đó
> không nằm trong bằng chứng của finding nào. **HTTP 200 tự nó không chứng minh gì cả.**
>
> Bản trước của báo cáo in "HTTP 200" ngay dưới danh sách finding SQL Injection mà không
> nói gì thêm. Người đọc nhanh sẽ hiểu là lỗ hổng đã được kiểm chứng. Nó chưa được.

---

## Phần 7 — Chất lượng được đo, không phải được tuyên bố (2 phút)

```bash
make score-ground-truth ANALYSIS=reports/week-06/artifacts/run-approved/analysis.jsonl
```

Ba điểm cần nói:

1. **Scanner precision 56,5 %** — thuộc tính của OpenGrep, không phải của Agent.
2. **Over-claim rate** đã từ **100 %** xuống **25–33 %**. Chưa về 0, và sẽ không về 0
   nếu không có phân tích taint thật.
3. **Nguyên nhân gốc không nằm ở model.** Với cửa sổ bằng chứng 4 dòng, Agent không nhìn
   thấy `@RequestParam` của **bất kỳ** true positive nào (0/13). Nó viết "không có bằng
   chứng cho thấy tham số đến từ người dùng" cho chính ca mà toàn bộ câu truy vấn **là**
   tham số request. Nới cửa sổ lên 28 dòng: với tới 12/13.

---

## Nếu còn thời gian

```bash
make quality                  # ruff, mypy, coverage 80 %, dependency audit
make eval REPEAT=3            # phân bố qua nhiều lần chạy (tốn token LLM)
```

---

## Checklist trước khi bắt đầu

- [ ] `make target-up` xong, health check xanh
- [ ] `pytest -m "not llm and not live_gateway" -q` xanh
- [ ] `make gateway-live-test` xanh
- [ ] `.env` có `LLM_API_KEY`, `SENTINEL_GATEWAY_API_KEY` đã export
- [ ] Mở sẵn `reports/week-06/artifacts/` để dùng khi mạng hỏng
- [ ] Cỡ chữ terminal đủ lớn để người ngồi cuối phòng đọc được

## Sau buổi demo

```bash
make target-down
make clean-runs               # giữ 5 lần chạy gần nhất
```
