"""
Production OpenRouter Client for Project Sentinel.
Direct HTTPS calls via standard library (urllib.request) with bounded retries and sanitized logging.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from project_sentinel.llm.base import AnalysisPacket, LLMProvider, LLMResult

logger = logging.getLogger(__name__)


def _sanitize_error(message: str, api_key: Optional[str] = None) -> str:
    if api_key and api_key in message:
        return message.replace(api_key, "[REDACTED_API_KEY]")
    return message


def _unwrap_json_envelope(parsed: Any) -> Any:
    """Unwrap an OpenRouter JSON envelope without assuming an output schema."""
    if (
        isinstance(parsed, dict)
        and isinstance(parsed.get("data"), dict)
        and set(parsed).issubset({"type", "data"})
    ):
        return parsed["data"]
    return parsed


class OpenRouterClient(LLMProvider):
    """Direct OpenRouter HTTPS client using standard library only."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "deepseek/deepseek-v4-flash-0731",
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        system_prompt_path: Optional[Path] = None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.system_prompt_path = system_prompt_path

    def _load_system_prompt(self) -> str:
        if self.system_prompt_path and self.system_prompt_path.exists():
            return self.system_prompt_path.read_text(encoding="utf-8")
        default_path = Path(__file__).parent.parent.parent.parent / "configs" / "prompts" / "security-analysis-system.md"
        if default_path.exists():
            return default_path.read_text(encoding="utf-8")
        return "You are a professional security analyst. Return valid JSON only."

    def _sanitize_error(self, message: str) -> str:
        return _sanitize_error(message, self.api_key)

    def _call_api(self, messages: List[Dict[str, str]]) -> LLMResult:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=openrouter")

        if not self.base_url.startswith("https://"):
            raise ValueError("LLM_BASE_URL must be an HTTPS URL")

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "reasoning": {"effort": "none"},
        }

        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Project-Sentinel/1.0"
        }

        attempts = 0
        last_error: Optional[str] = None
        start_time = time.time()

        while attempts <= self.max_retries:
            attempts += 1
            req = urllib.request.Request(endpoint, data=body_bytes, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    resp_bytes = response.read()
                    resp_json = json.loads(resp_bytes.decode("utf-8"))

                    if "choices" not in resp_json or not resp_json["choices"]:
                        last_error = "OpenRouter response missing 'choices'"
                        if attempts <= self.max_retries:
                            continue
                        break

                    first_choice = resp_json["choices"][0]
                    content_str = first_choice.get("message", {}).get("content", "")

                    if not content_str:
                        last_error = "OpenRouter choice message content is empty"
                        if attempts <= self.max_retries:
                            continue
                        break

                    content_clean = content_str.strip()
                    if content_clean.startswith("```"):
                        lines = content_clean.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        content_clean = "\n".join(lines).strip()

                    try:
                        parsed = _unwrap_json_envelope(json.loads(content_clean))
                    except json.JSONDecodeError as je:
                        last_error = f"Malformed assistant JSON response: {je}"
                        if attempts <= self.max_retries:
                            continue
                        break

                    usage = resp_json.get("usage", {})
                    latency = (time.time() - start_time) * 1000

                    return LLMResult(
                        raw_response=content_str,
                        parsed_response=parsed,
                        model_name=resp_json.get("model", self.model),
                        request_id=resp_json.get("id"),
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                        latency_ms=latency
                    )

            except urllib.error.HTTPError as e:
                status_code = e.code
                err_msg = f"HTTP Error {status_code}: {e.reason}"
                last_error = self._sanitize_error(err_msg)
                if status_code in (429, 500, 502, 503, 504) and attempts <= self.max_retries:
                    time.sleep(1.0 * attempts)
                    continue
                break

            except (urllib.error.URLError, TimeoutError) as e:
                err_msg = f"Network Error: {str(e)}"
                last_error = self._sanitize_error(err_msg)
                if attempts <= self.max_retries:
                    time.sleep(1.0 * attempts)
                    continue
                break

            except Exception as e:
                err_msg = f"Unexpected Error: {str(e)}"
                last_error = self._sanitize_error(err_msg)
                break

        latency = (time.time() - start_time) * 1000
        return LLMResult(
            raw_response="",
            parsed_response=None,
            model_name=self.model,
            latency_ms=latency,
            error=last_error or "Unknown error in OpenRouter provider"
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        """Generate structured JSON using raw system and user prompts."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self._call_api(messages)

    def analyze(self, packet: AnalysisPacket, system_prompt: Optional[str] = None) -> LLMResult:
        """Analyze packet by sending HTTPS request to OpenRouter Chat Completions API."""
        active_system_prompt = system_prompt or self._load_system_prompt()
        packet_dict = {
            "task": packet.task,
            "output_language": packet.output_language,
            "group_key": packet.group_key,
            "finding_group": packet.finding_group,
            "source_evidence": packet.source_evidence,
            "knowledge_hits": packet.knowledge_hits,
            "output_schema": packet.output_schema,
        }
        messages = [
            {"role": "system", "content": active_system_prompt},
            {"role": "user", "content": json.dumps(packet_dict, ensure_ascii=False)}
        ]
        return self._call_api(messages)
