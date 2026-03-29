"""Configuration manager — YAML config at ~/.steindb/config.yml."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import yaml

# Keys whose values should be stored encoded (not plaintext).
_SENSITIVE_KEYS: frozenset[str] = frozenset({"api_key"})


def _encode_key(key: str) -> str:
    """Encode a sensitive value for storage (prevents casual viewing)."""
    return "enc:" + base64.b64encode(key.encode()).decode()


def _decode_key(stored: str) -> str:
    """Decode a stored sensitive value. Supports legacy plaintext values."""
    if isinstance(stored, str) and stored.startswith("enc:"):
        return base64.b64decode(stored[4:]).decode()
    return stored  # backward compat for old plaintext keys


_DEFAULTS: dict[str, Any] = {
    "api_key": None,
    "default_model": None,
    "default_output_format": "html",
    "telemetry_opted_in": False,
}


class ConfigManager:
    """Manages SteinDB CLI configuration stored as YAML."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or Path.home() / ".steindb"
        self._config_path = self._config_dir / "config.yml"
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        """Load config from disk, merging with defaults."""
        if self._config_path.exists():
            try:
                raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data.update(raw)
            except yaml.YAMLError:
                # Corrupt file — fall back to defaults
                pass

    def _save(self) -> None:
        """Persist current config to disk."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        # Only save keys that differ from None-defaults or are explicitly set
        self._config_path.write_text(
            yaml.safe_dump(self._data, default_flow_style=False),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        value = self._data.get(key)
        if value is None:
            return default
        if key in _SENSITIVE_KEYS and isinstance(value, str):
            return _decode_key(value)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist."""
        if key in _SENSITIVE_KEYS and isinstance(value, str):
            self._data[key] = _encode_key(value)
        else:
            self._data[key] = value
        self._save()

    def delete(self, key: str) -> None:
        """Delete a config key and persist."""
        if key in self._data:
            self._data[key] = None
            self._save()

    def list_all(self) -> dict[str, Any]:
        """Return all config values."""
        return dict(self._data)
