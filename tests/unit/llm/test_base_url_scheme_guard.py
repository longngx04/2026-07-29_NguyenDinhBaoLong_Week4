"""Client LLM chỉ được mở HTTPS.

`urllib.request.urlopen` mở được cả `file://`. `base_url` đến từ biến môi trường,
nên một `.env` bị sửa có thể biến lời gọi "LLM" thành lệnh đọc file cục bộ, và
nội dung file đó đi thẳng vào đường xử lý phản hồi.

Guard đã có sẵn trong `_call_api`. Các test này chốt nó lại để không ai nới lỏng
thành "http hoặc https" khi debug rồi quên trả lại.
"""

import pytest

from project_sentinel.llm.openrouter import OpenRouterClient


def _client(base_url: str) -> OpenRouterClient:
    return OpenRouterClient(
        api_key="khoa-thu-nghiem", base_url=base_url, model="model-thu-nghiem"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///etc/passwd",
        "file://localhost/etc/shadow",
        "ftp://example.invalid/x",
        "gopher://example.invalid/x",
        "data:text/plain,xin-chao",
        "/khong-co-scheme/v1",
        # http tran cung bi tu choi: API key se di qua mang khong ma hoa.
        "http://openrouter.ai/api/v1",
        "http://127.0.0.1:1234/v1",
    ],
)
def test_only_https_base_urls_are_allowed(base_url):
    with pytest.raises(ValueError, match="HTTPS"):
        _client(base_url).generate(system_prompt="s", user_prompt="u")


def test_the_scheme_is_checked_before_any_socket_is_opened():
    """Guard phải chạy trước urlopen, không phải sau khi kết nối hỏng."""
    with pytest.raises(ValueError, match="HTTPS"):
        _client("file:///etc/passwd").generate(system_prompt="s", user_prompt="u")


def test_missing_api_key_is_refused_before_the_scheme_check():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        OpenRouterClient(
            api_key="", base_url="https://openrouter.ai/api/v1", model="m"
        ).generate(system_prompt="s", user_prompt="u")
