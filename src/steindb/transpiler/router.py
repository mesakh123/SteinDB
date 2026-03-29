# src/steindb/transpiler/router.py
"""BYOK (Bring Your Own Key) router.

Routes Oracle-to-PostgreSQL conversion requests to any OpenAI-compatible
API endpoint. Supports OpenAI, Anthropic, Ollama, and any custom endpoint.
"""

from __future__ import annotations

import ipaddress
import urllib.parse
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ModelProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    VLLM_LOCAL = "vllm_local"
    CUSTOM = "custom"


# Default base URLs for known providers
_DEFAULT_BASE_URLS: dict[ModelProvider, str] = {
    ModelProvider.OPENAI: "https://api.openai.com/v1",
    ModelProvider.ANTHROPIC: "https://api.anthropic.com/v1",
    ModelProvider.GOOGLE: "https://generativelanguage.googleapis.com/v1beta/openai",
    ModelProvider.OPENROUTER: "https://openrouter.ai/api/v1",
    ModelProvider.OLLAMA: "http://localhost:11434/v1",
    ModelProvider.LMSTUDIO: "http://localhost:1234/v1",
    ModelProvider.VLLM_LOCAL: "http://localhost:8000/v1",
}


@dataclass(frozen=True)
class BYOKConfig:
    """Configuration for a BYOK model endpoint."""

    provider: ModelProvider
    api_key: str
    model: str
    base_url: str | None = None
    temperature: float = 0.1
    max_tokens: int = 8192
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.base_url is None:
            object.__setattr__(
                self,
                "base_url",
                _DEFAULT_BASE_URLS.get(self.provider, ""),
            )


_BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "169.254.169.254",
        "metadata.google.internal",
    }
)

# Known-safe provider hosts that are allowed even though some resolve to
# localhost (e.g. Ollama, LM Studio, vLLM local).  These are only reachable
# when the *default* base URL is used (i.e. the user did not override it).
_KNOWN_LOCAL_PROVIDERS: frozenset[ModelProvider] = frozenset(
    {
        ModelProvider.OLLAMA,
        ModelProvider.LMSTUDIO,
        ModelProvider.VLLM_LOCAL,
    }
)


def _validate_base_url(url: str, provider: ModelProvider) -> None:
    """Raise ValueError if *url* points to a private / internal address.

    Known local providers (Ollama, LM Studio, vLLM) are exempted when the URL
    matches their default base URL so that legitimate local inference still
    works.  User-supplied overrides are always checked.
    """
    # Skip validation for known local providers using their default URL.
    if provider in _KNOWN_LOCAL_PROVIDERS:
        default_url = _DEFAULT_BASE_URLS.get(provider, "")
        if url == default_url:
            return

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""

    if host in _BLOCKED_HOSTS:
        raise ValueError(f"SSRF blocked: {host} is not allowed as base_url")

    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"SSRF blocked: private IP {host} not allowed")
    except ValueError as exc:
        if "SSRF blocked" in str(exc):
            raise
        # hostname, not IP — allow


class BYOKRouter:
    """Routes conversion requests to an OpenAI-compatible endpoint."""

    def __init__(self, config: BYOKConfig) -> None:
        _validate_base_url(config.base_url or "", config.provider)
        self._config = config

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Send a chat completion request and return the response text."""
        headers = self._build_headers()
        body = self._build_request_body(system_prompt, user_prompt)
        url = f"{self._config.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()

        data: dict[str, Any] = response.json()
        return self._extract_response_text(data)

    def _build_headers(self) -> dict[str, str]:
        """Build auth headers for the configured provider."""
        if self._config.provider == ModelProvider.ANTHROPIC:
            return {
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

    def _build_request_body(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Build the OpenAI-compatible request body."""
        return {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }

    def _extract_response_text(self, data: dict[str, Any]) -> str:
        """Extract the assistant message text from the response."""
        return str(data["choices"][0]["message"]["content"])
