# Project Sentinel

AI-assisted SAST finding normalization, knowledge retrieval, and security analysis pipeline
evaluated on [OWASP WebGoat](https://owasp.org/www-project-webgoat/). Every request the agent
proposes is constrained by an allowlist, a human approval gate, and an independent API Gateway;
sensitive data is redacted before it reaches an external model or disk.

---

## Luồng chín bước

Chạy bằng **một câu lệnh**. Luồng dừng ở giữa để chờ người phê duyệt.

```text
   GIAI ĐOẠN 1 — không có gì rời khỏi hệ thống
   ┌──────────────────────────────────────────────────────────────┐
   │  1 scan       OpenGrep trên mã nguồn        → raw.json        │
   │  2 normalize  đưa về một định dạng chung    → findings.json   │
   │  3 analyze    Agent + kho tri thức          → analysis.jsonl  │
   │  4 propose    Agent đề xuất request         → proposal.json   │
   └──────────────────────────────┬───────────────────────────────┘
                       ┌──────────▼──────────┐
                       │  5  CỔNG PHÊ DUYỆT  │  ◄── luồng DỪNG ở đây
                       │  mặc định = TỪ CHỐI │      ràng buộc bằng dấu vân tay
                       └──────────┬──────────┘
   GIAI ĐOẠN 2 — có traffic thật │
   ┌──────────────────────────────▼───────────────────────────────┐
   │  6 probe      GET/POST qua Gateway          → probe-result    │
   │  7 scrub      quét injection rồi che PII    → scrubbed.json   │
   │  8 report     dựng báo cáo cho người đọc    → report.md/json  │
   │  9 finalize   chốt số liệu, trạng thái cuối → metrics.json    │
   └──────────────────────────────────────────────────────────────┘
```

Bốn chốt guardrail nằm cắt ngang luồng đó. Mỗi chốt được đặt ở nơi **mọi** đường mã đều
buộc phải chạm, nên không caller nào quên gọi được:

```text
build_llm()        ──> RedactingProvider     # không gì tới mô hình ngoài mà chưa che
log_request()      ──> redact_structure()    # không gì chạm đĩa mà chưa che
send_probe()       ──> requires_approval()   # POST hoặc payload đặc biệt cần người duyệt
send_probe()       ──> redact() tại cửa ra   # response được che trước khi rời hàm
```

Nội dung lấy từ ứng dụng đích là **dữ liệu không đáng tin**: nó bị quét tìm mẫu injection,
cắt bỏ chỉ dẫn, che dữ liệu nhạy cảm, rồi bọc trong thẻ `<untrusted_app_response>` trước
khi bất kỳ mô hình nào nhìn thấy.

Chi tiết ranh giới tin cậy, vòng đời state và ba lớp chống bịa đặt:
**[docs/architecture.md](docs/architecture.md)**.

Tài liệu target: [docs/target-webgoat.md](docs/target-webgoat.md)

---

## Repository Structure

```text
project-sentinel/
├── src/project_sentinel/         # Production Python code
│   ├── ingestion/ retrieval/     #   SAST normalization and knowledge search
│   ├── analysis/ llm/            #   Analysis pipeline and LLM providers
│   ├── guardrails/               #   Redaction, injection defence, approval, event log
│   ├── gateway/ probe/           #   Allowlist, audit log, and the only request path out
│   ├── orchestrator/steps/       #   Chín bước của luồng, một file mỗi giai đoạn
│   ├── commands/                 #   Một file cho mỗi lệnh con CLI
│   └── demo/                     #   Runnable guardrails demo scenario
├── tests/                        # Unit, integration tests, and fixtures
├── eval/                         # Bộ sáu ca + ground truth 23 finding WebGoat + bộ chấm
├── docs/                         # Kiến trúc, mô tả sản phẩm, giới hạn, kịch bản demo
├── data/knowledge-base/          # OWASP & vulnerability knowledge base
├── configs/                      # Prompts, OpenGrep rules, gateway allowlist
├── schemas/                      # JSON Schema definitions
├── artifacts/runs/<run-id>/      # Output runtime của từng lần chạy (Git ignore)
├── reports/                      # Báo cáo theo tuần + evidence pack đã lọc
├── worklog/                      # Báo cáo của agent sau mỗi task
├── benchmarks/targets/webgoat/   # WebGoat benchmark (Git submodule)
└── infra/docker/                 # Scanner image and Nginx API Gateway build context
```

---

## Quick Start

Prerequisites:

- Python 3.10 or newer (CI uses Python 3.12).
- Docker Engine with Docker Compose v2.
- Git, `curl`, `jq`, and `openssl` available on the host.
- Outbound network access for the first container build and live LLM tests.

```bash
# Clone with submodules (if downloading fresh)
git submodule update --init --recursive

# Create an isolated environment and install the locked grader dependencies.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Generate an ephemeral Gateway credential for this shell. It is never printed
# or written to Git; repeat this export in a new shell when needed.
export SENTINEL_GATEWAY_API_KEY="$(openssl rand -hex 32)"

# Run the non-LLM test suite against the real Gateway and WebGoat.
# the target containers are started automatically and left running for debugging.
make agent-test

# Validate analysis output schema
make validate-analysis
```

---

## Chạy luồng chín bước

Đây là đường chính của sản phẩm. Mọi thứ khác trong README là công cụ hỗ trợ.

```bash
# Chuẩn bị (một lần)
cp .env.example .env                                    # điền LLM_API_KEY
export SENTINEL_GATEWAY_API_KEY="$(openssl rand -hex 32)"
make target-up                                          # Gateway + WebGoat

# Chạy đầu-cuối. Luồng DỪNG ở cổng phê duyệt và hỏi bạn.
python -m project_sentinel.cli run
#   → gõ 'approve' để đồng ý
#   → gõ bất cứ thứ gì khác để TỪ CHỐI (mặc định an toàn)

# Xem lại các lần chạy
python -m project_sentinel.cli runs

# Duyệt một lần chạy đang chờ, từ một terminal khác
python -m project_sentinel.cli approve <run-id> --decision approve
python -m project_sentinel.cli approve <run-id> --decision reject

# Không có người trực (CI). KHÔNG giả làm người: metrics ghi decided_by=cli-auto
# và báo cáo in một dòng cảnh báo.
python -m project_sentinel.cli run --yes

# Dọn dẹp — giữ 5 lần chạy gần nhất
make clean-runs                    # KEEP=10 để giữ nhiều hơn
make target-down
```

Bước `analyze` mất khoảng **4,5 phút** (21 lời gọi LLM). Đừng chạy trực tiếp khi đang
trình diễn — xem [docs/demo-script.md](docs/demo-script.md).

### Bảy lệnh con

| Lệnh | Việc |
| :--- | :--- |
| `python -m project_sentinel.cli run` | Chạy chín bước đầu-cuối, dừng ở cổng phê duyệt |
| `python -m project_sentinel.cli runs` | Liệt kê các lần chạy và trạng thái của chúng |
| `python -m project_sentinel.cli approve <run-id> --decision approve\|reject` | Quyết định rồi chạy tiếp một lần chạy đang chờ |
| `python -m project_sentinel.cli analyze --input … --output …` | Chỉ chạy bước phân tích trên một file findings |
| `python -m project_sentinel.cli validate --input …` | Đối chiếu một `analysis.jsonl` với JSON Schema |
| `python -m project_sentinel.cli probe --method GET --path …` | Gửi một request thủ công qua Gateway để kiểm tra hạ tầng |
| `python -m project_sentinel.cli demo` | Chạy kịch bản trình diễn guardrails |

Thêm `--help` sau bất kỳ lệnh nào để xem tham số đầy đủ.

### Artifact của một lần chạy

Mỗi lần chạy ghi vào `artifacts/runs/<run-id>/`. Thư mục này **bị Git ignore** vì nó là
output runtime. Bộ đã lọc dùng để chấm nằm trong
[`reports/week-06/artifacts/`](reports/week-06/artifacts/).

Đọc gì trước: `report.md` (cho người) · `metrics.json` (năm nhóm số liệu) ·
`events.jsonl` (sự kiện guardrail) · `state.json` (tiến độ chín bước).
Danh sách đầy đủ: [docs/architecture.md](docs/architecture.md) §6.

### Đo chất lượng Agent

```bash
make eval                          # sáu ca tự viết, cần LLM_API_KEY
make eval REPEAT=3                 # chạy ba lần, báo phân bố thay vì một mẫu

# Chấm trên 23 cảnh báo WebGoat THẬT, đối chiếu nhãn người review
make score-ground-truth ANALYSIS=artifacts/runs/<run-id>/analysis.jsonl
```

Ba bộ đo ba thứ khác nhau:

| Bộ | Trả lời câu | Chỉ số |
| :--- | :--- | :--- |
| `eval/cases/` (6 ca tự viết) | Agent có chạy đúng trên input mẫu không? | smoke test |
| `eval/ground-truth/webgoat-findings.json` (23 mục) | Cái được báo có thật không? | **precision** |
| `eval/ground-truth/recall/` (75 mục) | Cái có thật có được tìm ra không? | **recall** |

`make score-ground-truth` chấm cả precision lẫn recall trong một lần nếu thư mục lần chạy
có `findings.json`.

> **Con số cần nhìn trước:** recall hiện là **18,7 %** — hệ thống chỉ thấy 14/75 lỗ hổng
> có thật trong WebGoat, vì bộ rule scanner chỉ có ba rule. Đừng dùng kết quả "không tìm
> thấy gì" như bằng chứng rằng mã nguồn đã sạch.

Kết quả và cách đọc: [reports/week-06/report.md](reports/week-06/report.md) §4.4 và §4.5.
Bộ nhãn recall lấy từ nguồn ngoài — nguồn gốc và bản quyền:
[eval/ground-truth/recall/PROVENANCE.md](eval/ground-truth/recall/PROVENANCE.md).

### Kiểm tra chất lượng mã

```bash
make quality        # ruff + mypy + coverage (ngưỡng 78 %) + dependency audit
make lint           # riêng ruff
make typecheck      # riêng mypy
```

CI chạy đúng bộ lệnh này trong job `quality-gates`.

---

## Common Commands

```bash
# Run OpenGrep in its isolated scanner stack (no Gateway API key required)
make scan

# Normalize raw OpenGrep output
make normalize

# Search security knowledge base
make search Q='SQL Injection'

# Real OpenRouter analysis run. Read the key without echoing it or storing it in
# shell history; alternatively put it in an untracked .env copied from .env.example.
read -rsp 'OpenRouter API key: ' LLM_API_KEY && export LLM_API_KEY && printf '\n'
make analyze
make validate-analysis

# API Gateway & Safe Verification Probe
export SENTINEL_GATEWAY_API_KEY="${SENTINEL_GATEWAY_API_KEY:-$(openssl rand -hex 32)}"
make target-up        # start Gateway & WebGoat containers with health check
make probe            # run safe probe request through Gateway
make gateway-demo
make gateway-test      # focused gateway + probe tests
make gateway-live-test # real Docker Gateway + WebGoat acceptance test
make llm-test          # real OpenRouter tests, sequential by default for reliability
make target-down

# Guardrails
make guardrails-test              # guardrail unit tests + the six mandatory acceptance cases
make guardrails-demo              # interactive demo: you approve or reject each risky request
make guardrails-demo ARGS=--auto  # same scenario, unattended, for CI or capturing a log
```

`make guardrails-demo` walks seven steps and prints a pass/fail verdict for each: prompt
injection in an application response, a forged closing tag, redaction on the way to the LLM,
redaction on the way to disk, a rejected request, and an approved one. It requires the real
Gateway; the proof that a rejected request sends nothing is that the Nginx access log gains
no line, which is evidence at the infrastructure boundary rather than a call count inside
Python.

`requirements.txt` is the locked, pip-compatible grader entry point exported from `uv.lock`; it
installs this repository in editable mode. After an intentional dependency change in
`pyproject.toml`, regenerate both files with:

```bash
uv lock
uv export --locked --extra dev --no-hashes --output-file requirements.txt
```

`make llm-test` bounds grader runs to one pytest worker, one finding-group request at a time, and a
60-second absolute provider deadline with no transport retry. Production runs keep the runtime values from
`.env`; the live suite retains one schema-validation retry for malformed model output.

---

## Tài liệu

| Tài liệu | Dành cho ai |
| :--- | :--- |
| [docs/architecture.md](docs/architecture.md) | Người cần hiểu ranh giới tin cậy và vòng đời state |
| [docs/product-brief.md](docs/product-brief.md) | Người quyết định có nên dùng sản phẩm này không |
| [docs/limitations.md](docs/limitations.md) | **Đọc trước khi tin bất kỳ con số nào** |
| [docs/demo-script.md](docs/demo-script.md) | Người sắp trình diễn 10–15 phút |
| [docs/target-webgoat.md](docs/target-webgoat.md) | Người cần biết về ứng dụng đích |

---

## Historical Sprint Reports

- [Week 1 Report — OpenGrep SAST Setup](reports/week-01/report.md)
- [Week 2 Report — Finding Normalization & Knowledge Retrieval](reports/week-02/report.md)
- [Week 3 Report — Security Analysis Agent & Provenance Guardrails](reports/week-03/report.md)
- [Week 4 Report — API Gateway & Safe Test Request Tool](reports/week-04/report.md)
- [Week 5 Report — Guardrails, Human-in-the-Loop & Redaction](reports/week-05/report.md)
- [Week 6 Report — Tích hợp, đánh giá và bàn giao](reports/week-06/report.md)
  · [evidence pack](reports/week-06/artifacts/)

---

## Security Invariants & Target Binding

> **SECURITY NOTE**: OWASP WebGoat is an intentionally vulnerable benchmark application.
> The `docker-compose.yml` configuration strictly binds Nginx Gateway to loopback (`127.0.0.1:9080:8080`). WebGoat container port 8080 is internal only and not exposed on host interfaces.
> Do not modify container networking to expose WebGoat or Gateway on public network interfaces (`0.0.0.0`).
