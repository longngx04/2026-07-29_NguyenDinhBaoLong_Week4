"""
Factory for creating LLM providers based on AppConfig.
"""

from project_sentinel.config import AppConfig
from project_sentinel.llm.base import LLMProvider
from project_sentinel.llm.openrouter import OpenRouterClient


def build_llm(config: AppConfig) -> LLMProvider:
    """Instantiate the OpenRouter LLM provider."""
    provider_type = (config.provider_type or "openrouter").lower()

    if provider_type == "openrouter":
        config.ensure_openrouter_ready()
        return OpenRouterClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model_name,
            timeout_seconds=config.timeout,
            max_retries=config.max_retries,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {config.provider_type}")
