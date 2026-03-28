"""Tests for the SteinDB internationalization (i18n) module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from steindb.i18n import (
    DEFAULT_LOCALE,
    LOCALES_DIR,
    NAMESPACES,
    SUPPORTED_LOCALES,
    get_locale_from_env,
    load_messages,
    t,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache() -> None:  # type: ignore[no-untyped-def]
    """Clear the LRU cache between tests."""
    load_messages.cache_clear()


# ---------------------------------------------------------------------------
# Basic loading
# ---------------------------------------------------------------------------


class TestLoadMessages:
    """Tests for load_messages()."""

    def test_load_english_common(self) -> None:
        msgs = load_messages("en", "common")
        assert msgs["app_name"] == "SteinDB"
        assert "actions" in msgs
        assert "status" in msgs

    def test_load_english_cli(self) -> None:
        msgs = load_messages("en", "cli")
        assert "commands" in msgs
        assert "errors" in msgs
        assert "report" in msgs

    def test_web_namespace_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown namespace"):
            load_messages("en", "web")

    def test_api_namespace_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown namespace"):
            load_messages("en", "api")

    def test_fallback_to_english_for_unknown_locale(self) -> None:
        msgs = load_messages("xx", "common")
        assert msgs["app_name"] == "SteinDB"

    def test_invalid_namespace_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown namespace"):
            load_messages("en", "nonexistent")


# ---------------------------------------------------------------------------
# Translation function t()
# ---------------------------------------------------------------------------


class TestTranslate:
    """Tests for the t() function."""

    def test_simple_key(self) -> None:
        assert t("app_name") == "SteinDB"

    def test_nested_key(self) -> None:
        result = t("actions.save")
        assert result == "Save"

    def test_deeply_nested_key(self) -> None:
        result = t("commands.scan.help", namespace="cli")
        assert "Scan" in result

    def test_variable_interpolation(self) -> None:
        result = t("commands.scan.scanning", namespace="cli", file="schema.sql")
        assert result == "Scanning schema.sql..."

    def test_multiple_variables(self) -> None:
        result = t(
            "commands.convert.complete",
            namespace="cli",
            converted="42",
            total="50",
        )
        assert "42" in result
        assert "50" in result

    def test_missing_key_returns_key(self) -> None:
        result = t("nonexistent.key.path")
        assert result == "nonexistent.key.path"

    def test_partial_key_returns_key(self) -> None:
        result = t("actions.nonexistent")
        assert result == "actions.nonexistent"

    def test_japanese_locale(self) -> None:
        result = t("actions.save", locale="ja")
        assert result == "保存"

    def test_korean_locale(self) -> None:
        result = t("actions.save", locale="ko")
        assert result == "저장"

    def test_german_locale(self) -> None:
        result = t("actions.save", locale="de")
        assert result == "Speichern"

    def test_french_locale(self) -> None:
        result = t("actions.save", locale="fr")
        assert result == "Enregistrer"

    def test_chinese_simplified_locale(self) -> None:
        result = t("actions.save", locale="zh-CN")
        assert result == "保存"

    def test_chinese_traditional_locale(self) -> None:
        result = t("actions.save", locale="zh-TW")
        assert result == "儲存"

    def test_spanish_locale(self) -> None:
        result = t("actions.save", locale="es")
        assert result == "Guardar"

    def test_portuguese_locale(self) -> None:
        result = t("actions.save", locale="pt-BR")
        assert result == "Salvar"

    def test_arabic_locale(self) -> None:
        result = t("actions.save", locale="ar")
        assert result == "حفظ"

    def test_interpolation_with_locale(self) -> None:
        result = t("time.minutes_ago", locale="ja", n="5")
        assert result == "5分前"

    def test_interpolation_missing_var_keeps_placeholder(self) -> None:
        result = t("commands.scan.scanning", namespace="cli")
        # Missing 'file' kwarg — should keep the original string with {file}
        assert "{file}" in result


# ---------------------------------------------------------------------------
# Locale detection
# ---------------------------------------------------------------------------


class TestGetLocaleFromEnv:
    """Tests for get_locale_from_env()."""

    def test_stein_locale_env(self) -> None:
        with patch.dict("os.environ", {"STEIN_LOCALE": "ja"}):
            assert get_locale_from_env() == "ja"

    def test_stein_locale_invalid_falls_through(self) -> None:
        with patch.dict("os.environ", {"STEIN_LOCALE": "xx"}, clear=True):
            result = get_locale_from_env()
            assert result in SUPPORTED_LOCALES

    def test_lang_env(self) -> None:
        with patch.dict("os.environ", {"LANG": "de_DE.UTF-8"}, clear=True):
            assert get_locale_from_env() == "de"

    def test_default_locale(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert get_locale_from_env() == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# Structure validation: all locales have the required files
# ---------------------------------------------------------------------------


class TestLocaleStructure:
    """Validate that all 18 locales have the correct file structure."""

    def test_all_locale_directories_exist(self) -> None:
        for locale in SUPPORTED_LOCALES:
            locale_dir = LOCALES_DIR / locale
            assert locale_dir.is_dir(), f"Missing locale directory: {locale}"

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_locale_has_all_namespace_files(self, locale: str) -> None:
        for namespace in NAMESPACES:
            path = LOCALES_DIR / locale / f"{namespace}.json"
            assert path.is_file(), f"Missing {namespace}.json for locale {locale}"

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_locale_files_are_valid_json(self, locale: str) -> None:
        for namespace in NAMESPACES:
            path = LOCALES_DIR / locale / f"{namespace}.json"
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict), f"Root of {path} should be a dict"


# ---------------------------------------------------------------------------
# Key consistency: all locales must have the same keys as English
# ---------------------------------------------------------------------------


def _collect_keys(data: dict[str, Any], prefix: str = "") -> set[str]:
    """Recursively collect all dot-separated key paths from a nested dict."""
    keys: set[str] = set()
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_collect_keys(v, full_key))
        else:
            keys.add(full_key)
    return keys


class TestKeyConsistency:
    """Every locale must have the same key structure as English."""

    @pytest.mark.parametrize("namespace", NAMESPACES)
    def test_all_locales_match_english_keys(self, namespace: str) -> None:
        en_path = LOCALES_DIR / "en" / f"{namespace}.json"
        with open(en_path, encoding="utf-8") as f:
            en_data: dict[str, Any] = json.load(f)
        en_keys = _collect_keys(en_data)

        for locale in SUPPORTED_LOCALES:
            if locale == "en":
                continue
            locale_path = LOCALES_DIR / locale / f"{namespace}.json"
            with open(locale_path, encoding="utf-8") as f:
                locale_data: dict[str, Any] = json.load(f)
            locale_keys = _collect_keys(locale_data)

            missing = en_keys - locale_keys
            assert (
                not missing
            ), f"Locale '{locale}' namespace '{namespace}' is missing keys: {missing}"
            extra = locale_keys - en_keys
            assert not extra, f"Locale '{locale}' namespace '{namespace}' has extra keys: {extra}"


# ---------------------------------------------------------------------------
# Supported locales count
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify i18n constants are correct."""

    def test_eighteen_supported_locales(self) -> None:
        assert len(SUPPORTED_LOCALES) == 18

    def test_two_namespaces(self) -> None:
        assert len(NAMESPACES) == 2

    def test_default_locale_is_english(self) -> None:
        assert DEFAULT_LOCALE == "en"

    def test_locales_dir_exists(self) -> None:
        assert LOCALES_DIR.is_dir()
