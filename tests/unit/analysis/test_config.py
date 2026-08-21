from pathlib import Path
import pytest
from project_sentinel.config import AppConfig


def test_config_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    config = AppConfig()
    assert config.provider_type == "openrouter"
    assert config.model_name == "deepseek/deepseek-v4-flash-0731"
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.timeout == 60.0
    assert config.max_retries == 1
    assert config.top_k_knowledge == 3
    assert config.source_radius == 28
    assert isinstance(config.project_root, Path)
    assert isinstance(config.schema_path, Path)


def test_config_from_env_openrouter(monkeypatch, tmp_path):
    no_env = tmp_path / "empty.env"
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4-flash-0731")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-not-real")

    config = AppConfig.from_env(dotenv_path=no_env)
    assert config.provider_type == "openrouter"
    assert config.model_name == "deepseek/deepseek-v4-flash-0731"
    assert config.timeout == 45.0
    assert config.api_key == "sk-test-not-real"


def test_ensure_openrouter_ready(monkeypatch, tmp_path):
    no_env = tmp_path / "empty.env"
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_API_KEY", "")
    config = AppConfig.from_env(dotenv_path=no_env)

    with pytest.raises(ValueError, match="LLM_API_KEY is required"):
        config.ensure_openrouter_ready()

    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_BASE_URL", "http://insecure.url")
    config_bad_url = AppConfig.from_env(dotenv_path=no_env)
    with pytest.raises(ValueError, match="LLM_BASE_URL must be an HTTPS URL"):
        config_bad_url.ensure_openrouter_ready()

    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    config_valid = AppConfig.from_env(dotenv_path=no_env)
    config_valid.ensure_openrouter_ready()  # Should not raise


def test_from_env_loads_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=sk-from-dotenv\nLLM_MODEL=test-model-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    config = AppConfig.from_env(dotenv_path=env_file)
    assert config.api_key == "sk-from-dotenv"
    assert config.model_name == "test-model-dotenv"


def test_env_var_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=sk-from-dotenv\nLLM_MODEL=test-model-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("LLM_API_KEY", "sk-explicit-env")
    monkeypatch.setenv("LLM_MODEL", "test-model-env")

    config = AppConfig.from_env(dotenv_path=env_file)
    assert config.api_key == "sk-explicit-env"
    assert config.model_name == "test-model-env"
