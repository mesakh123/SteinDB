"""Internationalization support for SteinDB."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).parent.parent.parent.parent / "locales"
DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES: list[str] = [
    "en",
    "ja",
    "ko",
    "zh-CN",
    "zh-TW",
    "de",
    "fr",
    "pt-BR",
    "es",
    "hi",
    "id",
    "th",
    "vi",
    "tr",
    "it",
    "nl",
    "pl",
    "ar",
]

NAMESPACES: list[str] = ["common", "cli"]


@lru_cache(maxsize=128)
def load_messages(locale: str, namespace: str) -> dict[str, Any]:
    """Load translation messages for a locale and namespace.

    Falls back to English if the requested locale file does not exist.
    """
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE
    if namespace not in NAMESPACES:
        msg = f"Unknown namespace: {namespace}. Must be one of {NAMESPACES}"
        raise ValueError(msg)

    path = LOCALES_DIR / locale / f"{namespace}.json"
    if not path.exists():
        path = LOCALES_DIR / DEFAULT_LOCALE / f"{namespace}.json"
    with open(path, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


def t(
    key: str,
    locale: str = DEFAULT_LOCALE,
    namespace: str = "common",
    **kwargs: str | int | float,
) -> str:
    """Translate a key with optional variable interpolation.

    Supports nested keys with dots (e.g., ``"commands.scan.help"``).
    Variables use ``{name}`` syntax in translation strings.

    Args:
        key: Dot-separated key path into the translation messages.
        locale: Target locale code (e.g., ``"ja"``, ``"de"``).
        namespace: Message namespace (``"common"``, ``"cli"``).
        **kwargs: Variables to interpolate into the translated string.

    Returns:
        The translated string, or the key itself if not found.
    """
    messages = load_messages(locale, namespace)

    # Navigate nested keys: "commands.scan.help" -> messages["commands"]["scan"]["help"]
    parts = key.split(".")
    value: Any = messages
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            # Key not found — return the raw key as fallback
            return key

    if isinstance(value, str):
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        return value

    return str(value)


def get_locale_from_env() -> str:
    """Detect locale from environment variables.

    Checks (in order):
    1. ``STEIN_LOCALE`` — explicit override
    2. ``LANG`` / ``LC_ALL`` — system locale

    Returns:
        A supported locale code, defaulting to ``"en"``.
    """
    # Explicit override
    stein_locale = os.getenv("STEIN_LOCALE", "")
    if stein_locale and stein_locale in SUPPORTED_LOCALES:
        return stein_locale

    # System locale detection
    lang = os.getenv("LANG", os.getenv("LC_ALL", "en"))
    for supported in SUPPORTED_LOCALES:
        normalized = supported.replace("-", "_")
        if lang.startswith(normalized):
            return supported

    return DEFAULT_LOCALE


__all__ = [
    "DEFAULT_LOCALE",
    "LOCALES_DIR",
    "NAMESPACES",
    "SUPPORTED_LOCALES",
    "get_locale_from_env",
    "load_messages",
    "t",
]
