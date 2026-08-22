# Thiết kế: DAST bằng OWASP ZAP

**Ngày:** 2026-08-22 · **Trạng thái:** thiết kế đã duyệt, chưa implement
**Branch:** `feat/dast-zap`

---

## 1. Vì sao làm

Pipeline hiện tại chỉ có SAST. Bước `probe` gửi request thật qua Gateway, nhưng allowlist
chỉ có ba endpoint (`/WebGoat/actuator/health`, `/WebGoat/login`, `/WebGoat/attack`) với bốn
payload lành tính. [`architecture.md`](../../architecture.md) §5 tự ghi nhận rằng verdict
`inconclusive` là "gần như mọi trường hợp", và [`limitations.md`](../../limitations.md) ghi
"Không có payload khai thác thật".

Nghĩa là chuỗi **đề xuất → phê duyệt → probe** hiện là một cơ chế an toàn đã chạy được
nhưng chưa chứng minh được điều gì về ứng dụng đích. Agent đề xuất một endpoint đoán từ
code tĩnh; allowlist từ chối gần hết; cái đi qua thì trả về một trang HTML không nói lên
gì về lỗ hổng.

DAST sửa đúng chỗ đó. Không phải vì nó làm Gateway "được dùng nhiều hơn" — ZAP không đi
qua Gateway — mà vì nó tạo ra **bằng chứng runtime**: endpoint này có thật, tham số này có
thật, ZAP chạm tới được và nhận status này. Có bằng chứng đó thì đề xuất của agent mới trỏ
vào một chỗ có thật, và kết quả probe mới đọc được.

---

## 2. Phát biểu lại ranh giới tin cậy

Phát biểu cũ — *mọi traffic tới WebGoat đi qua Gateway* — sẽ thành sai khi thêm ZAP. Phát
biểu mới, chính xác hơn về đúng mối lo ban đầu:

> **Mọi request mà nội dung của nó chịu ảnh hưởng bởi output của LLM đều phải đi qua
> Gateway.** ZAP không bao giờ đọc output của LLM, nên nó nằm ngoài mệnh đề đó.

Gateway tồn tại để chặn *mô hình* lái được request, không phải để chặn *người vận hành*
chạy scanner. ZAP là công cụ do người cấu hình, payload cố định, không có vòng phản hồi nào
từ mô hình. Nó là một actor khác hẳn về mặt tin cậy.

### Ranh giới D phải mở rộng

Alert của ZAP chứa trường `evidence` và `attack` — **là đoạn response body thật của
WebGoat**. WebGoat là ứng dụng cố ý có lỗ hổng, nên nội dung đó do kẻ tấn công kiểm soát
được.

Nếu để nó chảy thẳng vào `findings.json` → prompt analyze → LLM, ta tạo ra một đường prompt
injection **chưa từng tồn tại**: hiện `findings.json` chỉ đến từ OpenGrep đọc code tĩnh.

Do đó ranh giới D (`scan_injection()` → `redact()` → `wrap_untrusted()`) **không còn chỉ áp
cho probe result, mà áp cho cả đường normalize output ZAP**. Đây là điều kiện bắt buộc,
không phải tuỳ chọn.

```text
┌─ VÙNG 3: hạ tầng ─────────────────────────────────────────────────┐
│                                                                    │
│   ZAP  ──(traffic thật, payload cố định, KHÔNG có LLM)──►  WebGoat │
│    │                                                          ▲    │
│    │ zap-alerts.json / zap-endpoints.json                     │    │
│    │                                                          │    │
│    │                          Nginx Gateway ──allowlist───────┘    │
│    │                               ▲                               │
└────┼───────────────────────────────┼───────────────────────────────┘
     │                               │ ranh giới C (LLM → request)
     │  ★ ranh giới D (MỞ RỘNG)      │
     │  scan_injection → redact      │
     ▼                               │
┌────┴───────────── VÙNG 2: tiến trình Sentinel ─────────────────┴───┐
│   findings.json  →  analyze  →  propose  →  approval  →  probe ────┘
└────────────────────────────────────────────────────────────────────┘
```

Hai lối vào VÙNG 2 từ VÙNG 3, cả hai đều qua ranh giới D. Đúng một lối ra, qua ranh giới C.

### Bất biến được giữ nguyên

`zap` **không bind cổng host nào**. Nên invariant [`AGENTS.md`](../../../AGENTS.md) §2.4 và
test `test_every_host_port_binds_loopback_only` giữ nguyên nguyên văn. Test duy nhất phải
sửa là `test_all_four_services_exist`
([`test_compose_invariants.py`](../../../tests/unit/infra/test_compose_invariants.py)) — nó
hardcode đúng bốn service.

---

## 3. Sự thật về WebGoat đã kiểm chứng từ source

Mọi dòng dưới đây đọc từ submodule `benchmarks/targets/webgoat`, không phải phỏng đoán.

| Sự thật | Nguồn | Hệ quả |
| :--- | :--- | :--- |
| `POST /register.mvc` là `permitAll` | `container/WebSecurityConfig.java:41-42` | ZAP tự tạo tài khoản được, không cần seed thủ công |
| Đăng ký **tự động login** (`request.login(...)`) | `container/users/RegistrationController.java:60` | Một POST là có `JSESSIONID`; không cần bước login riêng |
| `csrf.disable()` | `container/WebSecurityConfig.java:61` | Không phải xử lý CSRF token |
| `headers.disable()` | `container/WebSecurityConfig.java:62` | Passive scan sẽ ra alert thật (thiếu CSP, X-Content-Type-Options, HSTS) trên **mọi** URL |
| Form đăng ký: `username` `[a-z0-9-]*` 6–45, `password` 6–10, `matchingPassword`, `agree` | `container/users/UserForm.java:22-34` | Ràng buộc cụ thể cho script tạo tài khoản |
| `formLogin` loginPage `/login`, param `username`/`password` | `container/WebSecurityConfig.java:50-54` | Đường login dự phòng nếu tài khoản đã tồn tại |
| Bề mặt `permitAll`: `/favicon.ico`, `/css/**`, `/images/**`, `/js/**`, `fonts/**`, `/plugins/**`, `/registration`, `/register.mvc`, `/actuator/**` (+ `/login`) | `container/WebSecurityConfig.java:34-44` | Đây là **toàn bộ** bề mặt mà probe ẩn danh chạm được — xem §7 |

### Điều CHƯA kiểm chứng

Phía ZAP, các chi tiết sau đến từ hiểu biết chung về công cụ và **chưa đối chiếu với image
đã pin**:

- Tên chính xác các hàm hook của `zap-baseline.py` (`zap_started`, `zap_spider`,
  `zap_pre_shutdown`).
- Chữ ký `zap.replacer.add_rule(...)`.
- Hình dạng chính xác của report `-J`.

Theo [`AGENTS.md`](../../../AGENTS.md) §2.6 (không bịa bằng chứng), **task đầu tiên của
implementation plan phải là dựng container, chạy một scan thật, ghi output thật thành
fixture, rồi mới viết code đọc nó.** Không có task đó thì phần còn lại xây trên phỏng đoán.

---

## 4. Kiến trúc: ZAP theo đúng khuôn `scanner` hiện có

### 4.1 Compose

Service thứ năm, profile riêng `dast`, không cổng host:

```yaml
  zap:
    profiles: ["dast"]
    build:
      context: ./infra/docker/zap
    image: sentinel-sec/zap:local
    volumes:
      - ./artifacts:/zap/wrk/artifacts
    networks:
      - sentinel-net
```

Không dùng `depends_on: webgoat`: webgoat thuộc profile `target`, và `depends_on` xuyên
profile sẽ lỗi khi profile kia chưa bật. Thay vào đó `scripts/scan-zap.sh` gọi
`make target-up` trước — đúng cách `agent-test: gateway-up` đang làm trong `Makefile`.

### 4.2 Image

`infra/docker/zap/Dockerfile`: `FROM zaproxy/zap-stable:<tag>` rồi
`COPY sentinel_hook.py /zap/wrk/`. **Pin version cứng**, theo đúng nhà của repo
(`webgoat:v2025.3`); không dùng `latest`. Tag cụ thể do **Task 1** chốt: task đó kéo
image, đọc version thật ZAP tự báo, ghi số đó vào Dockerfile và vào worklog. Không
đoán tag trong spec này.

### 4.3 Hook

`infra/docker/zap/sentinel_hook.py`, ba việc:

1. **Lấy session.** POST `/WebGoat/register.mvc` với giá trị hợp lệ theo ràng buộc
   `UserForm.java`. Vì `RegistrationController.java:60` tự gọi `request.login(...)`, một
   POST là ra `JSESSIONID`. Vì `csrf.disable()` (`WebSecurityConfig.java:61`), không cần token. Nếu username đã tồn tại
   thì fallback sang `POST /WebGoat/login`.
2. **Nạp session vào ZAP** bằng replacer rule đặt header `Cookie: JSESSIONID=…` cho mọi
   request. Cách này tránh phải cấu hình context/authentication/user của ZAP — vốn nhiều
   mảnh và dễ hỏng âm thầm. **Kèm exclude regex `.*logout.*` cho spider**; thiếu nó spider
   sẽ tự đăng xuất giữa chừng và phần còn lại của scan trở thành vô nghĩa.
3. **Dump bản đồ endpoint** ở `zap_pre_shutdown`, ra file thứ hai.

### 4.4 Script

`scripts/scan-zap.sh` sao cấu trúc `scripts/scan-opengrep.sh`: nhận đường dẫn output làm
tham số (bài học đã ghi ngay trong comment script đó — bỏ qua argument thì provenance nói
sai sự thật), ghi ra `mktemp`, `jq -e` kiểm hình dạng, rồi mới `mv`.

### 4.5 Artifact

| File (trong thư mục run) | Nội dung | Phục vụ |
| :--- | :--- | :--- |
| `zap-alerts.json` | Report ZAP thô | Slice A |
| `zap-endpoints.json` | URL + method + tên tham số đã thấy | Slice B, C |

### 4.6 Vị trí trong luồng

DAST **gộp vào bước `scan`**. Số bước vẫn là **9**; `STEP_NAMES` không đổi.

Ngữ nghĩa lỗi: SAST chạy trước và vẫn bắt buộc thành công. DAST chạy sau; hỏng hoặc không
có target thì ghi `detail={"dast": "skipped", "dast_reason": ...}` cộng một dòng `warn` vào
`run.log.jsonl`, **không kéo cả bước fail**. Lý do: SAST là xương sống; máy dev không Docker
vẫn phải chạy được run.

---

## 5. Slice A — finding ZAP vào chung `findings.json`

Module mới `src/project_sentinel/ingestion/zap_normalizer.py`, **song song** với
`normalizer.py` chứ không sửa nó.

### 5.1 Map sang schema chung

Schema chung khớp sẵn: trường đã tên là **`file_or_url`**, và `line` vốn đã nullable.

| Trường chung | Nguồn ZAP |
| :--- | :--- |
| `id` | `zap-NNN` (không đụng `opengrep-NNN`) |
| `tool` | `"zap"` |
| `severity` | risk `High/Medium/Low/Informational` → `high/medium/low/info` |
| `file_or_url` | URL của alert |
| `line` | `null` |
| `rule_id`, `raw_check_id` | `pluginId` |
| `cwe` | `cweid` |
| `message` | mô tả alert |
| `confidence` | confidence của ZAP |

Vì tiền tố ID tách bạch, provenance validator **không cần đổi gì ở phần ID**.

### 5.2 Ranh giới D áp tại đây

`evidence` và `attack` đi `scan_injection()` → `redact()` → `wrap_untrusted()`, đúng thứ tự
mà [`architecture.md`](../../architecture.md) §3 đã lập luận. Mỗi lần phát hiện ghi một dòng
vào `events.jsonl`.

### 5.3 Gộp theo loại alert

Vì `headers.disable()` (`WebSecurityConfig.java:62`), **mọi URL** sẽ dính alert thiếu CSP / X-Content-Type-Options /
HSTS. Spider ra vài trăm URL thì normalize kiểu một-alert-một-finding cho ra hàng nghìn
finding, làm nổ `findings.json` và đốt token ở bước analyze.

Quyết định: **một finding cho mỗi loại alert**, kèm `instances[]` liệt kê URL/param bị ảnh
hưởng, **cắt ở 20 instance đầu tiên** và giữ `instances_total` là con số đầy đủ. Đây
cũng là cách chính ZAP trình bày. Chọn 20 vì nó đủ để thấy một alert trải rộng khắp
ứng dụng hay chỉ ở một chỗ, mà không kéo cả trăm URL gần giống nhau vào prompt.

**Đánh đổi đã chấp nhận:** "một finding" của DAST không cùng hạt với "một finding" của SAST.
`metrics.json` phải nói rõ điều đó (§8).

### 5.4 Đường trích bằng chứng thứ hai

`evidence.extract_source_window` cần file+line; finding ZAP không có. Thêm một nhánh điều
phối, **không sửa nhánh cũ** (giữ `AGENTS.md` §2.1 behavior preservation):

| Finding | Bằng chứng là gì |
| :--- | :--- |
| có `file` + `line` | `extract_source_window()` — **y nguyên như hiện nay** |
| `tool == "zap"` | khối request/response đã scrub từ chính alert, đã `wrap_untrusted()` |

### 5.5 Provenance validator

Nhận thêm một hình dạng vị trí: URL. Cùng nguyên tắc cũ — LLM chỉ được nhắc tới URL **có
thật trong input** — chỉ là hình dạng thứ hai bên cạnh `path:line`.

---

## 6. Slice B — đối chiếu SAST ↔ DAST

### 6.1 Cầu nối

Finding SAST là `.../SqlInjectionLesson5a.java:47`. Endpoint DAST là
`/WebGoat/SqlInjection/attack5a`. Không có gì nối hai thứ đó một cách hiển nhiên.

**Cầu nối là annotation route trong chính file chứa finding.** WebGoat là Spring MVC, nên
class chứa dòng bị OpenGrep bắt gần như luôn khai `@GetMapping` / `@PostMapping` /
`@RequestMapping` với path cụ thể. Trích annotation đó là thao tác **tất định, đọc file,
không hỏi LLM** — cùng loại với `extract_source_window`. Rồi so path đó với danh sách URL
ZAP thật sự chạm tới trong `zap-endpoints.json`.

### 6.2 Vị trí

Module mới `src/project_sentinel/analysis/correlation.py`, chạy **cuối `step_normalize`** —
tất định, không LLM, nên thuộc giai đoạn chuẩn hoá chứ không phải phân tích. Số bước vẫn là 9.

### 6.3 Khối gắn vào mỗi finding SAST

| `strength` | Nghĩa |
| :--- | :--- |
| `reachable_and_alerted` | Route có thật, ZAP chạm được, **và** có alert ZAP trên chính URL đó |
| `reachable` | Route có thật và ZAP chạm được (có status code thật) |
| `route_known_not_reached` | Trích được route từ source nhưng ZAP không tới |
| `no_route` | Không trích được route; finding này không có mặt runtime |

Khối kèm: `route`, `route_source` (file:line của annotation), `observed_status`,
`dast_alerts[]`.

### 6.4 Hệ quả lên `calibration.py`

Hiện `reachability` là trường **agent tự khai**, và vì không chứng minh được nên luật
`confirmed_requires_proof` hạ cấp gần như mọi kết luận.

> **Quyết định:** `reachability` thôi là trường agent khai. Python **tính** nó từ
> correlation và **ghi đè** giá trị agent đưa ra.

Điều này khớp đúng kỷ luật repo đã có — khối `calibration` cũng bị bỏ nếu agent tự sinh. Ta
mở rộng cùng nguyên tắc sang một trường nữa, và lần này theo hướng *có thể nâng*, vì bằng
chứng đến từ Python chứ không từ mô hình.

### 6.5 Giới hạn phải nói trước

Slice B chứng minh được **reachability**, **không** chứng minh được `attacker_control`.
Muốn `attacker_control: proven` thì phải có alert từ **active scan** — thứ giai đoạn 1 cố ý
không làm.

Nên sau slice B, verdict **không** nhảy lên `confirmed`. Nó thoát khỏi cảnh "mọi thứ đều bị
hạ cấp", nhưng trần vẫn là `needs_review` với severity không còn bị kẹp bởi luật
reachability.

Đổi lại, bước `propose` có căn cứ thật: agent đề xuất kiểm chứng một route đã biết chắc là
sống, có status thật, thay vì một path đoán từ code.

---

## 7. Slice C — allowlist từ endpoint ZAP

### 7.1 Cơ chế

Generator đọc `zap-endpoints.json`, sinh **`artifacts/dast/allowlist-candidates.json`** —
một file *ứng viên*, **không bao giờ ghi thẳng vào allowlist đang chạy**. Mỗi ứng viên mang
provenance runtime thật (`ZAP run <id>, GET → 200`), tốt hơn cách hiện nay là trích dẫn dòng
Java thủ công.

Mặc định `GET`, `payload_kind: null`. Generator **không được phép** đề xuất POST hay payload
— thứ đó phải do người viết tay.

### 7.2 Điều tuyệt đối không tự động hoá

**Allowlist Nginx.** Hai allowlist tồn tại vì chúng được **suy ra độc lập**;
[`architecture.md`](../../architecture.md) §3 nói rõ, bằng chứng cho một request bị chặn là
*Nginx access log không có thêm dòng nào*, tức bằng chứng ở tầng hạ tầng. Nếu một script
sinh cả hai từ cùng một nguồn ZAP, chúng thôi độc lập và lớp phòng thủ kép sập xuống còn một
lớp. **Người phải viết tay phía Nginx.**

### 7.3 Giá trị của slice C bị chặn bởi vấn đề session

ZAP crawl **trong session đã đăng nhập**. Probe của Sentinel qua Gateway thì **không có
session**. Nên phần lớn endpoint ZAP tìm được, khi Sentinel probe thật, sẽ trả 302 về
`/login`.

Bề mặt truy cập được khi chưa đăng nhập là danh sách `permitAll` ở §3. Trừ đi ba endpoint
allowlist đã có, **ứng viên thật sự mới gần như chỉ còn `/WebGoat/registration` và vài route
`/actuator/*`** — toàn thứ không có giá trị kiểm chứng lỗ hổng.

Vì vậy generator phải tự đánh dấu trường **`unauthenticated_reachable`** cho mỗi ứng viên,
bằng cách đối chiếu với danh sách `permitAll`, để người review thấy ngay ứng viên nào thực
tế probe được.

**Quyết định:** spec mô tả C đầy đủ, nhưng implementation plan đặt C **sau A và B, sau một
điểm dừng đánh giá**. Muốn C có giá trị thật thì phải cho probe mang session — đó là thay
đổi bán kính thiệt hại lớn (agent lái được request *đã xác thực*) và xứng đáng một vòng
thiết kế riêng, không nhét vào đợt này.

---

## 8. Số liệu

`collect_metrics` hiện có `findings_total` đọc thẳng `findings.json`
([`metrics.py`](../../../src/project_sentinel/orchestrator/metrics.py)). Sau slice A con số
đó sẽ âm thầm trộn hai loại hạt khác nhau (§5.3).

Thêm:

- `findings_by_tool: {"opengrep": n, "zap": m}`
- `dast: {endpoints_discovered, alerts_total, instances_total}`
- Phân bố `strength` của correlation (slice B)

Giữ `findings_total` nguyên nghĩa cũ để không phá test đang có.

---

## 9. Kiểm chứng

[`AGENTS.md`](../../../AGENTS.md) §2.2: không mock, và test không tới được dependency thì
**fail chứ không skip**.

- **Marker mới `dast`** trong `pyproject.toml`, cùng kiểu opt-in với `live_gateway` — nhưng
  đã chọn thì thiếu ZAP là đỏ, không xanh.
- **Fixture ghi từ một lần chạy ZAP thật** (task 1 của plan), không phải JSON bịa tay.
- `tests/integration/test_dast_live.py` (marker `dast`): ZAP thật quét WebGoat thật, khẳng
  định alert khác rỗng và `zap-endpoints.json` có `/WebGoat/login`.
- **Test bảo mật quan trọng nhất:** một alert ZAP có `evidence` chứa chuỗi prompt injection
  phải sinh dòng trong `events.jsonl` và phải bị `wrap_untrusted()` trước khi vào
  `findings.json`. Không có test này thì §2 chỉ là lời hứa.
- `test_compose_invariants.py`: `test_all_four_services_exist` → 5 service; thêm
  `test_zap_is_never_published_on_host` (khoá `zap` không có `ports`, đúng cách WebGoat đang
  được khoá).
- Unit test correlation trên fixture thật.

---

## 10. Tài liệu phải cập nhật đồng bộ

`test_docs_complete.py` đang khoá bộ tài liệu bắt buộc, nên không được để lệch.

| File | Sửa gì |
| :--- | :--- |
| `docs/architecture.md` | Sơ đồ vùng mới (§2), ranh giới D mở rộng, `scan` giờ làm hai việc |
| `docs/limitations.md` | Chỉ baseline không active scan; không chứng minh `attacker_control`; probe ẩn danh nên slice C bị chặn |
| `docs/target-webgoat.md` | Bề mặt `permitAll` và vì sao nó giới hạn ứng viên allowlist |
| `README.md`, `docs/demo-script.md` | `make dast`, và DAST xuất hiện ở đâu trong demo |
| `AGENTS.md` §1 | Thêm `infra/docker/zap/` vào cây thư mục |
| `Makefile` | Target `dast` + `.PHONY` |

---

## 11. Ngoài phạm vi (cố ý không làm)

| Việc | Vì sao không làm lần này |
| :--- | :--- |
| Active scan (ZAP bắn payload khai thác thật) | Chạy 15–40+ phút, kết quả dao động giữa các lần, làm bẩn trạng thái WebGoat, khó đưa vào CI/demo |
| Cho probe mang `JSESSIONID` | Thay đổi bán kính thiệt hại lớn nhất từ trước tới nay; cần vòng thiết kế riêng |
| Tự sinh allowlist Nginx | Phá tính độc lập của hai lớp allowlist (§7.2) |
| Trỏ DAST vào target khác WebGoat | Target cố định là quyết định có chủ ý đã ghi trong `limitations.md` |

---

## 12. Thứ tự thực thi

```text
Task 1   Dựng container, chạy ZAP thật, GHI FIXTURE  ← chặn mọi task sau
   │
Slice A  compose + hook + script + zap_normalizer + ranh giới D + evidence + validator
   │
Slice B  correlation.py + calibration ghi đè reachability
   │
   ▼  ĐIỂM DỪNG ĐÁNH GIÁ — đếm xem còn bao nhiêu ứng viên allowlist đáng làm
   │
Slice C  allowlist-candidates + unauthenticated_reachable
```
