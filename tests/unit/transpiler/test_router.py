# tests/unit/transpiler/test_router.py
"""Tests for the BYOK router."""

from __future__ import annotations

import pytest
from steindb.transpiler.router import (
    BYOKConfig,
    BYOKRouter,
    ModelProvider,
    _validate_base_url,
)


class TestBYOKConfig:
    def test_openai_config(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="sk-test-key",
            model="gpt-4o",
        )
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4o"

    def test_custom_endpoint(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.CUSTOM,
            api_key="test",
            model="my-model",
            base_url="http://localhost:8000/v1",
        )
        assert config.base_url == "http://localhost:8000/v1"

    def test_anthropic_config(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-sonnet-4-20250514",
        )
        assert config.provider == ModelProvider.ANTHROPIC

    def test_ollama_config(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OLLAMA,
            api_key="",  # Ollama doesn't need a key
            model="deepseek-coder-v2:33b",
            base_url="http://localhost:11434/v1",
        )
        assert "ollama" in config.provider.value

    def test_all_providers_defined(self) -> None:
        providers = {p.value for p in ModelProvider}
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
        assert "custom" in providers

    def test_google_default_url(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.GOOGLE,
            api_key="test",
            model="gemini-pro",
        )
        assert "generativelanguage" in str(config.base_url)

    def test_openrouter_default_url(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENROUTER,
            api_key="test",
            model="meta-llama/llama-3-70b",
        )
        assert "openrouter" in str(config.base_url)

    def test_default_temperature(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="test",
            model="gpt-4o",
        )
        assert config.temperature == 0.1

    def test_default_max_tokens(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="test",
            model="gpt-4o",
        )
        assert config.max_tokens == 8192


class TestBYOKRouter:
    def test_create_router(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="sk-test",
            model="gpt-4o",
        )
        router = BYOKRouter(config)
        assert router is not None

    def test_build_headers_openai(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="sk-test",
            model="gpt-4o",
        )
        router = BYOKRouter(config)
        headers = router._build_headers()
        assert headers["Authorization"] == "Bearer sk-test"

    def test_build_headers_anthropic(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-sonnet-4-20250514",
        )
        router = BYOKRouter(config)
        headers = router._build_headers()
        assert headers["x-api-key"] == "sk-ant-test"
        assert "anthropic-version" in headers

    def test_build_request_body(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="sk-test",
            model="gpt-4o",
        )
        router = BYOKRouter(config)
        body = router._build_request_body(
            system_prompt="You are an expert.",
            user_prompt="Convert this SQL.",
        )
        assert body["model"] == "gpt-4o"
        assert body["temperature"] == 0.1
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"

    def test_build_request_body_custom_temperature(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="sk-test",
            model="gpt-4o",
            temperature=0.5,
        )
        router = BYOKRouter(config)
        body = router._build_request_body("sys", "usr")
        assert body["temperature"] == 0.5

    def test_extract_response_text(self) -> None:
        config = BYOKConfig(
            provider=ModelProvider.OPENAI,
            api_key="sk-test",
            model="gpt-4o",
        )
        router = BYOKRouter(config)
        data = {"choices": [{"message": {"content": "SELECT CURRENT_TIMESTAMP"}}]}
        assert router._extract_response_text(data) == "SELECT CURRENT_TIMESTAMP"


class TestSSRFValidation:
    """SSRF protection: block private/internal IPs and hostnames."""

    def test_blocks_localhost(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            BYOKRouter(
                BYOKConfig(
                    provider=ModelProvider.CUSTOM,
                    api_key="test",
                    model="m",
                    base_url="http://localhost:9999/v1",
                )
            )

    def test_blocks_127_0_0_1(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            BYOKRouter(
                BYOKConfig(
                    provider=ModelProvider.CUSTOM,
                    api_key="test",
                    model="m",
                    base_url="http://127.0.0.1:8080/v1",
                )
            )

    def test_blocks_metadata_ip(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            BYOKRouter(
                BYOKConfig(
                    provider=ModelProvider.CUSTOM,
                    api_key="test",
                    model="m",
                    base_url="http://169.254.169.254/latest/meta-data/",
                )
            )

    def test_blocks_private_ip(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            BYOKRouter(
                BYOKConfig(
                    provider=ModelProvider.CUSTOM,
                    api_key="test",
                    model="m",
                    base_url="http://10.0.0.1:8080/v1",
                )
            )

    def test_allows_public_url(self) -> None:
        router = BYOKRouter(
            BYOKConfig(
                provider=ModelProvider.OPENAI,
                api_key="sk-test",
                model="gpt-4o",
            )
        )
        assert router is not None

    def test_allows_ollama_default_url(self) -> None:
        """Ollama default localhost URL is allowed (known local provider)."""
        router = BYOKRouter(
            BYOKConfig(
                provider=ModelProvider.OLLAMA,
                api_key="",
                model="llama3",
                base_url="http://localhost:11434/v1",
            )
        )
        assert router is not None

    def test_validate_base_url_blocks_0_0_0_0(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("http://0.0.0.0:8080/v1", ModelProvider.CUSTOM)
