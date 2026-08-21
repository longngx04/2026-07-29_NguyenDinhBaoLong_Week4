"""Evidence pack được commit vào Git — nó phải sạch, và phải sạch mãi.

Bộ artifact dưới `reports/week-06/artifacts/` là thứ mentor clone repo sẽ đọc.
Một lần thêm file cẩu thả vào đó là một lần lộ secret vĩnh viễn trong lịch sử
Git. Test này chạy trong suite offline nên mọi lần thêm file đều bị soi lại.
"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANARY = Path(__file__).resolve().parent / "fixtures" / "secrets" / "canary-values.env"
PACK = REPO_ROOT / "reports" / "week-06" / "artifacts"

# Cac gia tri bi mat that, doc tu .env cua may dang chay (neu co).
SECRET_NAME = re.compile(r"(?i)(key|token|secret|password|passwd)$")

# Mau nhan dang secret theo hinh dang, khong phu thuoc .env.
SHAPE_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "API key kieu sk-"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."), "JWT"),
    (
        re.compile(r"(?i)x-sentinel-api-key\s*[\"':=]+\s*[A-Za-z0-9]{16,}"),
        "Gateway API key trong header",
    ),
    (
        re.compile(r"(?i)authorization\s*[\"':=]+\s*bearer\s+\S{12,}"),
        "Bearer token",
    ),
]

# Chuoi hex 64 ky tu duoc phep khi va chi khi no la mot digest provenance da
# duoc review: prompt hash, dau van tay phe duyet, hoac digest cua Docker/OpenGrep
# trong log build. Danh sach nay co chu y HEP.
ALLOWED_HEX_CONTEXT = re.compile(
    r'(?i)("(?:prompt_sha256|request_fingerprint|fingerprint)"\s*:\s*")'
    r"|(sha256:)"
    r"|(opengrep)"
)


def _pack_files():
    if not PACK.exists():
        return []
    return sorted(p for p in PACK.rglob("*") if p.is_file())


def _env_secrets() -> dict[str, str]:
    env = REPO_ROOT / ".env"
    if not env.exists():
        return {}
    found = {}
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if value and len(value) >= 8 and SECRET_NAME.search(name):
            found[name] = value
    return found


def test_the_evidence_pack_exists():
    assert _pack_files(), (
        "Không có evidence pack. Mentor clone repo sẽ không có bằng chứng nào "
        "vì artifacts/runs/ bị Git ignore."
    )


def _canary_secrets() -> dict[str, str]:
    """Bộ giá trị committed, luôn có mặt kể cả trên máy không có `.env`."""
    found: dict[str, str] = {}
    for line in CANARY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        found[name.strip()] = value.strip()
    return found


def test_no_secret_value_appears_in_the_pack():
    """Không bao giờ skip. Không có `.env` thì vẫn đối chiếu bộ canary.

    Repo tự đặt invariant "test không skip khi thiếu dependency" (AGENTS.md D10),
    nhưng test này skip trên mọi máy không có `.env` — nghĩa là trên CI và trên
    máy mentor vừa clone. Một cổng chất lượng chỉ chạy ở máy của tác giả thì
    không phải cổng.

    Hai chế độ, và test nói rõ nó đang chạy chế độ nào:

    - Có `.env`: đối chiếu GIÁ TRỊ THẬT. Đây là phép kiểm mạnh.
    - Không có `.env`: đối chiếu bộ canary committed. Yếu hơn, nhưng vẫn là một
      khẳng định thật và vẫn chạy ở mọi nơi.
    """
    secrets = _canary_secrets()
    secrets.update(_env_secrets())
    assert secrets, f"{CANARY} phải chứa ít nhất một giá trị canary"

    leaks = []
    for path in _pack_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, value in secrets.items():
            if value in text:
                leaks.append(f"{path.relative_to(PACK)} chứa giá trị của {name}")
    assert not leaks, "Secret trong evidence pack: " + "; ".join(leaks)


def test_no_secret_shaped_string_appears_in_the_pack():
    leaks = []
    for path in _pack_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in SHAPE_PATTERNS:
            match = pattern.search(text)
            if match:
                leaks.append(
                    f"{path.relative_to(PACK)} khớp {label}: {match.group(0)[:16]}…"
                )
    assert not leaks, "Chuỗi giống secret trong evidence pack: " + "; ".join(leaks)


def test_every_long_hex_string_is_a_reviewed_digest():
    """Hex 64 ký tự phải là digest đã biết, không phải một khoá lọt vào."""
    hex64 = re.compile(r"\b[A-Fa-f0-9]{64}\b")
    suspicious = []
    for path in _pack_files():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if hex64.search(line) and not ALLOWED_HEX_CONTEXT.search(line):
                suspicious.append(f"{path.relative_to(PACK)}: {line[:100]}")
    assert not suspicious, (
        "Chuỗi hex 64 ký tự không nằm trong ngữ cảnh digest đã duyệt: "
        + "; ".join(suspicious[:5])
    )


def test_no_dotenv_or_private_key_file_was_copied_in():
    bad = [
        p.relative_to(PACK).as_posix()
        for p in _pack_files()
        if p.name in {".env", "id_rsa", "id_ed25519"}
        or p.suffix in {".pem", ".key", ".p12", ".pfx"}
    ]
    assert not bad, f"File nhạy cảm trong evidence pack: {bad}"
