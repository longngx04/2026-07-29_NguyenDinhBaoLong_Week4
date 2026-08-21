"""Không lời gọi LLM nào được đi ra với một prompt thay thế im lặng.

Báo cáo Tuần 6 ghi lại sự cố: đường dẫn System Prompt mặc định trỏ sai thư mục,
nên chương trình dùng một chuỗi dự phòng dài 80 ký tự thay cho 3.994 ký tự luật
đã được review. Mọi lời gọi trước đó không nhận được luật chống prompt injection
lẫn luật giới hạn endpoint — và 457 test đều xanh.

`PromptBuilder` đã fail loudly. `OpenRouterClient` thì chưa: nó vẫn còn nhánh dự
phòng. Hai nơi cùng nạp một file mà hai chính sách khác nhau thì chính sách lỏng
hơn là chính sách thật.
"""

from pathlib import Path

import pytest

from project_sentinel.analysis.prompt_builder import PromptBuilder
from project_sentinel.llm.openrouter import OpenRouterClient

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEWED_PROMPT = REPO_ROOT / "configs" / "prompts" / "security-analysis-system.md"


def _client(path):
    return OpenRouterClient(
        api_key="khoa-thu-nghiem",
        base_url="https://example.invalid/v1",
        model="model-thu-nghiem",
        system_prompt_path=path,
    )


def test_missing_prompt_file_raises_instead_of_substituting():
    """Thiếu file luật thì dừng, không được tự bịa ra một prompt ngắn."""
    with pytest.raises(FileNotFoundError):
        _client(Path("/khong/ton/tai/prompt.md"))._load_system_prompt()


def test_both_loaders_apply_the_same_policy():
    """PromptBuilder và OpenRouterClient phải hỏng như nhau khi thiếu file."""
    missing = Path("/khong/ton/tai/prompt.md")
    with pytest.raises(FileNotFoundError):
        PromptBuilder(system_prompt_path=missing).load_system_prompt()
    with pytest.raises(FileNotFoundError):
        _client(missing)._load_system_prompt()


def test_default_path_resolves_to_the_reviewed_prompt():
    """Không truyền đường dẫn thì phải nạp đúng file luật đã review."""
    loaded = _client(None)._load_system_prompt()
    assert loaded == REVIEWED_PROMPT.read_text(encoding="utf-8")


def test_the_reviewed_prompt_is_not_a_stub():
    """Chốt kích thước: một prompt vài chục ký tự nghĩa là luật đã biến mất."""
    assert len(REVIEWED_PROMPT.read_text(encoding="utf-8")) > 2000


def test_loaded_prompt_carries_the_rules_that_matter():
    loaded = _client(None)._load_system_prompt()
    for rule in ("untrusted", "allowed_endpoints", "disposition", "attacker_control"):
        assert rule in loaded, f"System prompt thiếu luật `{rule}`"
