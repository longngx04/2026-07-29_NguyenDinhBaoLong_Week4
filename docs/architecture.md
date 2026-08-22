# Kiến trúc Project Sentinel

**Cập nhật:** 2026-08-21 · **Trạng thái:** mô tả hệ thống đang chạy, không phải kế hoạch

Tài liệu này mô tả **hệ thống thật ở thời điểm bàn giao**. Mọi thành phần nêu ở đây đều
tồn tại trong mã nguồn và đã chạy đầu-cuối trong lần chạy `20260821T083837Z`.

---

## 1. Bài toán và hình dạng lời giải

Một công cụ SAST cho ra hàng chục cảnh báo, gần một nửa không phải lỗ hổng thật (đo được
trên WebGoat: 13/23 là thật). Người trực bảo mật phải đọc từng cái. Project Sentinel đặt
một Agent LLM vào giữa để phân loại và giải thích, rồi **kiểm chứng** một số cảnh báo
bằng cách gửi request thật tới ứng dụng đang chạy.

Điều đó tạo ra một vấn đề mới: một mô hình ngôn ngữ nay có thể khiến hệ thống gửi request
HTTP tới một ứng dụng có lỗ hổng. Toàn bộ phần còn lại của kiến trúc tồn tại để giới hạn
điều mô hình đó có thể gây ra.

**Nguyên tắc xuyên suốt:** output của LLM là *dữ liệu không đáng tin*, không phải lệnh.
Mọi giá trị mô hình đề xuất mà có thể thực thi được đều bị **đối chiếu lại từng field**
với một danh sách đã review ở phía Python, trước khi bất kỳ request nào tồn tại.

---

## 2. Chín bước

Chạy bằng một câu lệnh (`python -m project_sentinel.cli run`). Luồng dừng ở giữa để chờ
người phê duyệt.

```text
   GIAI ĐOẠN 1 — không có gì rời khỏi hệ thống
   ┌──────────────────────────────────────────────────────────────┐
   │  1 scan       SAST (bắt buộc) + DAST (tuỳ chọn) → raw.json   │
   │  2 normalize  đưa về một định dạng chung    → findings.json   │
   │  3 analyze    Agent + kho tri thức          → analysis.jsonl  │
   │  4 propose    Agent đề xuất request         → proposal.json   │
   └──────────────────────────────┬───────────────────────────────┘

                                  │
                       ┌──────────▼──────────┐
                       │  5  CỔNG PHÊ DUYỆT  │  ◄── luồng DỪNG ở đây
                       │  approval-request   │      mặc định = TỪ CHỐI
                       │       ↓ decision    │
                       └──────────┬──────────┘
                                  │  chỉ đi tiếp khi dấu vân tay khớp
   GIAI ĐOẠN 2 — có traffic thật  │
   ┌──────────────────────────────▼───────────────────────────────┐
   │  6 probe      GET/POST qua Gateway          → probe-result    │
   │  7 scrub      quét injection rồi che PII    → scrubbed.json   │
   │  8 report     dựng báo cáo cho người đọc    → report.md/json  │
   │  9 finalize   chốt số liệu, trạng thái cuối → metrics.json    │
   └──────────────────────────────────────────────────────────────┘
```

Mỗi bước là một hàm thuần `(record, ctx) -> record` trong
[`orchestrator/steps/`](../src/project_sentinel/orchestrator/steps/). Bước nào hỏng thì
ném `StepFailure`; runner bắt lại và chuyển trạng thái sang `FAILED` thay vì làm sập CLI.

---

## 3. Ranh giới tin cậy

Bốn ranh giới. Mỗi ranh giới có đúng một chỗ đi qua, đặt ở nơi **mọi** đường mã đều
buộc phải chạm — không caller nào quên gọi được.

```text
┌─ VÙNG 1: mã nguồn và kho tri thức (đọc, không thực thi) ────────────────┐
│  benchmarks/targets/webgoat/   data/knowledge-base/   configs/          │
└────────────────────────────┬───────────────────────────────────────────┘
                             │  evidence.extract_source_window
                             │  ⟹ giới hạn dưới target_root, chặn path traversal
┌────────────────────────────▼─── VÙNG 2: tiến trình Sentinel ───────────┐
│                                                                         │
│   ┌── RANH GIỚI A ── build_llm() ⟹ RedactingProvider ───────────────┐  │
│   │   Không gì tới mô hình ngoài mà chưa qua bộ che.                 │  │
│   └──────────────────────────┬───────────────────────────────────────┘  │
│                              │                                          │
│   ┌── RANH GIỚI B ── log_request()/append_log()/append_event()      ─┐  │
│   │       ⟹ redact_structure()  ·  Không gì chạm đĩa mà chưa che.    │  │
│   └──────────────────────────┬───────────────────────────────────────┘  │
│                              │                                          │
│   ┌── RANH GIỚI C ── send_probe() ⟹ requires_approval() ────────────┐  │
│   │   POST hoặc payload đặc biệt phải có quyết định của người,       │  │
│   │   và quyết định đó phải khớp DẤU VÂN TAY của đúng request này.   │  │
│   └──────────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │  Agent probe: chỉ một đường ra, tới 127.0.0.1:9080
┌──────────────────────────────▼─── VÙNG 3: hạ tầng ─────────────────────┐
│   Nginx Gateway  ── allowlist ĐỘC LẬP thứ hai, deny-by-default          │
│         │  mạng Docker nội bộ, WebGoat KHÔNG mở cổng host               │
│         ▼                                                               │
│   WebGoat (ứng dụng cố ý có lỗ hổng)                                    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  response quay vào
   ┌── RANH GIỚI D ── scan_injection() → redact() → wrap_untrusted() ──┐
   │   Nội dung từ ứng dụng đích là DỮ LIỆU, không bao giờ là chỉ dẫn.  │
   └───────────────────────────────────────────────────────────────────┘
```

DAST là một luồng hạ tầng riêng, không đi qua `send_probe()` và không nới allowlist
của Agent:

```text
ZAP (baseline spider + AF requestor job)
        │  GET/HEAD/POST + X-Sentinel-DAST-Key, mạng Docker nội bộ
        ▼
gateway-dast:8081  ── chỉ /WebGoat/, thay body bằng canonical body, bỏ header của caller, rate/timeout hữu hạn
        │  không publish cổng host
        ▼
WebGoat:8080       ── internal-only
```

Khoá DAST được tạo ngẫu nhiên cho từng lệnh `make dast`, không được ghi vào artifact.
Gateway DAST tự động khởi tạo và duy trì phiên đăng nhập WebGoat (`JSESSIONID`) tại thời
điểm bootstrap container qua hook `16-acquire-dast-session.envsh`, tiêm cookie phiên vào mọi
request forward tới WebGoat, đồng thời chặn triệt để `^~ /WebGoat/logout` (HTTP 403) để bảo vệ
phiên suốt quá trình quét. ZAP hoàn toàn ẩn danh, không nhận cookie và không cần quản lý phiên.

Gateway access log ghi lại đầy đủ `path=$uri` và `query=$args` làm bằng chứng đường đi; script
từ chối công nhận lần quét nếu không có request DAST tại Gateway hoặc nếu khoá xuất hiện trong log.
ZAP chạy baseline (spider + passive scan) kết hợp với Automation Framework `requestor` job để gửi
POST lành tính tới danh sách path đã review trong `configs/gateway/dast-allowlist.json`. Bất biến then chốt:
*nội dung WebGoat nhận được từ lane DAST do lane quyết định hoàn toàn; ZAP không ảnh hưởng được method, path, header hay body.*
Mọi POST tới path ngoài allowlist đều bị từ chối với HTTP 405 ngay tại Gateway.

Raw ZAP report vẫn giữ các cảnh báo trên response `403/405` do chính Gateway sinh ra để audit.
Normalizer gộp các cảnh báo theo `pluginid`, giữ method và parameter tiêu biểu, lưu `instances` (tối đa 20)
và `instances_total`. Chỉ nhập các instance `GET/HEAD` có origin chính xác `gateway-dast:8081` và path
`/WebGoat/…`; trang bootstrap và URL ngoài scope không được biến thành finding của WebGoat.

### Vì sao có hai allowlist

Allowlist phía Python ([`gateway/allowlist.py`](../src/project_sentinel/gateway/allowlist.py))
và allowlist phía Nginx là **hai lần kiểm tra độc lập** trên cùng một chính sách. Một lỗi
trong mã Python — hoặc một đường mã nào đó quên gọi công cụ — vẫn còn Nginx chặn ở tầng hạ
tầng. Bằng chứng cho việc một request bị chặn là **Nginx access log không có thêm dòng
nào**, tức bằng chứng ở ranh giới hạ tầng chứ không phải một biến đếm bên trong Python.

### Dấu vân tay phê duyệt

Duyệt một request rồi gửi một request khác là một lớp lỗi kinh điển. Ở đây,
`request_fingerprint` được tính từ **method + path + payload thật**, đi qua cặp file
`approval-request.json` → `decision.json`. `send_probe` từ chối gửi nếu dấu vân tay của
quyết định không khớp request sắp gửi. Đổi `payload_kind` sau khi đã duyệt thì phiếu duyệt
cũ trở nên vô hiệu.

---

## 4. Ba lớp chống bịa đặt

Agent có thể bịa. Ba lớp bên dưới đều **không hỏi ý Agent**.

| Lớp | Kiểm gì | Ở đâu |
| :--- | :--- | :--- |
| **Schema** | JSON Schema chặt (`locations` chấp nhận `{file, line}` hoặc `{url}`), `additionalProperties: false` | `analysis/validators.py` |
| **Provenance** | Finding ID, vị trí file/URL, CWE/OWASP, đường dẫn tri thức và bằng chứng đều phải **có thật trong input** | `analysis/validators.py` |
| **Hiệu chỉnh** | Kết luận không được vượt quá bằng chứng; `reachability` đo bằng quan sát động | `analysis/calibration.py` |

Lớp thứ ba là lớp mới nhất và trả lời một lỗ hổng cụ thể: hai lớp đầu chỉ kiểm **cấu
trúc**. Một record có thể có mọi ID đúng, mọi vị trí đúng, mọi CWE đúng — và vẫn kết luận
`SQL Injection / high` cho một truy vấn hằng, trong khi chính phần giải thích của nó viết
"không có lỗ hổng SQL Injection rõ ràng tại vị trí này".

Đặc biệt, trường `reachability` **không do Agent tự khai** mà do Python đo đạc thực tế
(`correlation.py`) bằng cách đối chiếu route tĩnh của mã nguồn với `gateway-access.log` của DAST:
- `no_route` hoặc `route_known_not_reached` $\rightarrow$ `reachability` bị hạ về `unknown` / `unlikely`.
- `reachable` hoặc `reachable_and_alerted` $\rightarrow$ ghi nhận bằng chứng runtime `reachability_measured`.

Tầng hiệu chỉnh áp luật lên chính output đó, **chỉ hạ và không bao giờ nâng**:

| Luật | Nội dung |
| :--- | :--- |
| `reachability_measured` | `reachability` bị ghi đè bằng kết quả đo động thực tế từ DAST |
| `confirmed_requires_proof` | `confirmed` đòi **cả** `attacker_control` **và** `reachability` là `proven` |
| `prose_contradicts_disposition` | Văn xuôi tự phủ nhận lỗ hổng thì kết luận không được ở mức khẳng định |
| `severity_ceiling_for_disposition` | `needs_review` ≤ `medium`; `false_positive` = `info` |
| `attacker_control_not_proven` | Chưa chứng minh được kiểm soát đầu vào thì ≤ `medium` |

Mọi lần hiệu chỉnh để lại khối `calibration` trong record và một dòng trong báo cáo cuối.
Agent không được tự sinh khối này — mọi giá trị nó tự khai đều bị bỏ trước khi hiệu chỉnh.

---

## 5. Kết quả probe nói được gì

Một request chỉ được tính là **bằng chứng cho một finding** khi thoả **cả hai**:

1. Nó gắn với một `analysis_id` có thật (không phải do người vận hành tự chỉ định), và
2. Endpoint của nó **có mặt trong chính bằng chứng của finding đó**.

Không thoả thì kết quả là `inconclusive`, kèm lý do. HTTP 200 tự nó không chứng minh gì.
Chi tiết trong [`orchestrator/verdict.py`](../src/project_sentinel/orchestrator/verdict.py).

| Kết luận | Khi nào |
| :--- | :--- |
| `supports` | Response chứa dấu hiệu đã khai trước trong `expected_signal` |
| `refutes` | Dấu hiệu đã khai trước không xuất hiện |
| `inconclusive` | Mọi trường hợp còn lại — và với cấu hình hiện tại, gần như là mọi trường hợp |

---

## 6. Vòng đời state và artifact

**Tiến độ nằm trên đĩa, không nằm trong bộ nhớ chương trình.** Sau mỗi bước, `state.json`
được ghi bằng kỹ thuật *ghi file tạm rồi đổi tên*, nên người đọc luôn thấy hoặc bản cũ
nguyên vẹn hoặc bản mới nguyên vẹn — không bao giờ thấy file đang viết dở.

Hệ quả: tắt máy giữa chừng vẫn xem lại được đã chạy tới đâu và `resume` tiếp; và một
chương trình khác (ví dụ một màn hình web) có thể mở cùng file để theo dõi trong lúc
luồng đang chạy, không cần API riêng.

```text
artifacts/runs/<run-id>/
├── state.json              tiến độ chín bước + trạng thái   (ghi lại sau MỖI bước)
├── raw.json                output OpenGrep thô
├── zap-alerts.json         output ZAP raw trong lượt quét DAST
├── zap-findings.json       finding DAST sau khi chuẩn hoá & gộp alert
├── gateway-access.log      access log Nginx Gateway DAST kèm query args
├── findings.json           toàn bộ cảnh báo đã chuẩn hoá và đối chiếu runtime
├── analysis.jsonl          một record cho mỗi nhóm finding
├── analysis-summary.json   token, model, prompt hash, số record bị hiệu chỉnh
├── proposal.json           request Agent đề xuất + finding nó nhắm tới
├── approval-request.json   thứ người vận hành nhìn thấy   ─┐ cặp dấu vân tay
├── decision.json           quyết định của người vận hành  ─┘
├── probe-result.json       kết quả HTTP (preview ĐÃ che)
├── scrubbed.json           kết quả quét injection + số liệu redaction
├── gateway-requests.jsonl  audit log, không bao giờ chứa API key
├── events.jsonl            sự kiện guardrail (redaction/injection/approval/block)
├── run.log.jsonl           nhật ký toàn trình, mỗi dòng ≤ 2 KB, đã che
├── report.md / report.json báo cáo cuối cho người đọc
└── metrics.json            năm nhóm số liệu bắt buộc (kèm findings_by_tool & DAST)

artifacts/raw/zap.json      output ZAP baseline thô (khi chạy độc lập qua make dast)
artifacts/dast/gateway-access.log
                            bằng chứng GET/HEAD đã đi qua gateway-dast, không có khoá
artifacts/normalized/zap-findings.json
                            finding DAST đã chuẩn hoá
```


`artifacts/runs/` bị Git ignore vì nó là output runtime. Bộ đã lọc dùng để chấm nằm trong
[`reports/week-06/artifacts/`](../reports/week-06/artifacts/), và có test quét secret canh
thư mục đó.

Dọn dẹp: `make clean-runs` giữ 5 lần chạy gần nhất (`KEEP=n` để đổi).

---

## 7. Cấu trúc mã nguồn

```text
src/project_sentinel/
├── ingestion/      chuẩn hoá output OpenGrep, nạp input
├── retrieval/      tìm kiếm từ khoá trên data/knowledge-base/
├── analysis/       gom nhóm, trích bằng chứng, prompt, pipeline, HIỆU CHỈNH
├── llm/            trừu tượng nhà cung cấp + RedactingProvider (ranh giới A)
├── guardrails/     redaction, phát hiện injection, phê duyệt, sổ sự kiện
├── gateway/        allowlist, audit log (ranh giới B)
├── probe/          công cụ request an toàn — đường ra DUY NHẤT (ranh giới C)
├── orchestrator/   state, runner, chín bước, verdict, metrics, report
├── commands/       một file cho mỗi lệnh con CLI
└── web/            mặt tiền FastAPI + Jinja2 + CSS/JS 7 màn hình, chỉ đọc artifact
```

---

## 8. Những điều kiến trúc này KHÔNG bảo vệ được

Đọc kèm [`limitations.md`](limitations.md). Ngắn gọn: nó giới hạn *phạm vi* điều Agent có
thể gây ra, nhưng nó **không** làm cho phán đoán của Agent trở nên đúng. Một Agent khai
`attacker_control: proven` khi không có bằng chứng vẫn qua được cả ba lớp — vì mọi ID nó
dùng đều có thật. Đó chính là lý do bộ ground truth ở
[`eval/ground-truth/`](../eval/ground-truth/) tồn tại: nó đo phán đoán, không đo cấu trúc.
