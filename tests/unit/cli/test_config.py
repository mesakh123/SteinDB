"""Tests for ConfigManager — load, save, get, set, list, delete."""

import pytest
import yaml
from steindb.cli.config_manager import ConfigManager


@pytest.fixture()
def config_dir(tmp_path):
    """Provide a temporary config directory."""
    return tmp_path / ".steindb"


@pytest.fixture()
def manager(config_dir):
    """Provide a ConfigManager using a temp directory."""
    return ConfigManager(config_dir=config_dir)


class TestConfigManagerInit:
    def test_creates_config_dir_on_save(self, manager, config_dir):
        manager.set("foo", "bar")
        assert config_dir.exists()

    def test_creates_config_file_on_save(self, manager, config_dir):
        manager.set("foo", "bar")
        assert (config_dir / "config.yml").exists()


class TestConfigDefaults:
    def test_default_telemetry_opted_in(self, manager):
        assert manager.get("telemetry_opted_in") is False

    def test_default_output_format(self, manager):
        assert manager.get("default_output_format") == "html"

    def test_default_model(self, manager):
        assert manager.get("default_model") is None


class TestConfigGetSet:
    def test_set_and_get(self, manager):
        manager.set("api_key", "sk-test-123")
        assert manager.get("api_key") == "sk-test-123"

    def test_get_missing_key_returns_none(self, manager):
        assert manager.get("nonexistent") is None

    def test_get_missing_key_with_default(self, manager):
        assert manager.get("nonexistent", default="fallback") == "fallback"

    def test_overwrite_existing_key(self, manager):
        manager.set("api_key", "old")
        manager.set("api_key", "new")
        assert manager.get("api_key") == "new"

    def test_set_persists_to_disk(self, manager, config_dir):
        manager.set("api_key", "sk-persist")
        # Create a new manager reading from the same dir
        manager2 = ConfigManager(config_dir=config_dir)
        assert manager2.get("api_key") == "sk-persist"


class TestConfigList:
    def test_list_all_returns_dict(self, manager):
        result = manager.list_all()
        assert isinstance(result, dict)

    def test_list_all_includes_defaults(self, manager):
        result = manager.list_all()
        assert "telemetry_opted_in" in result
        assert "default_output_format" in result

    def test_list_all_includes_custom_keys(self, manager):
        manager.set("custom_key", "custom_value")
        result = manager.list_all()
        assert result["custom_key"] == "custom_value"


class TestConfigDelete:
    def test_delete_existing_key(self, manager):
        manager.set("api_key", "sk-delete-me")
        manager.delete("api_key")
        assert manager.get("api_key") is None

    def test_delete_nonexistent_key_no_error(self, manager):
        # Should not raise
        manager.delete("nonexistent")


class TestConfigLoadSave:
    def test_load_empty_dir(self, config_dir):
        """Loading from non-existent dir returns defaults."""
        mgr = ConfigManager(config_dir=config_dir)
        assert mgr.get("default_output_format") == "html"

    def test_load_corrupt_yaml(self, config_dir):
        """Loading a corrupt YAML file falls back to defaults."""
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yml").write_text(": : : invalid yaml [[[")
        mgr = ConfigManager(config_dir=config_dir)
        # Should not crash, should have defaults
        assert mgr.get("default_output_format") == "html"

    def test_save_creates_valid_yaml(self, manager, config_dir):
        manager.set("api_key", "test")
        content = (config_dir / "config.yml").read_text()
        parsed = yaml.safe_load(content)
        # API key should be stored encoded, not plaintext
        assert parsed["api_key"] != "test"
        assert parsed["api_key"].startswith("enc:")


class TestConfigAPIKeyEncoding:
    """API keys are stored encoded on disk but decoded on read."""

    def test_api_key_stored_encoded(self, manager, config_dir):
        manager.set("api_key", "sk-secret-123")
        content = (config_dir / "config.yml").read_text()
        parsed = yaml.safe_load(content)
        assert parsed["api_key"].startswith("enc:")
        assert "sk-secret-123" not in content

    def test_api_key_decoded_on_read(self, manager):
        manager.set("api_key", "sk-secret-123")
        assert manager.get("api_key") == "sk-secret-123"

    def test_api_key_persists_encoded_across_instances(self, manager, config_dir):
        manager.set("api_key", "sk-persist-key")
        manager2 = ConfigManager(config_dir=config_dir)
        assert manager2.get("api_key") == "sk-persist-key"

    def test_backward_compat_plaintext_key(self, config_dir):
        """Old plaintext keys still work (backward compatibility)."""
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yml").write_text(
            yaml.safe_dump({"api_key": "sk-old-plaintext"}),
            encoding="utf-8",
        )
        mgr = ConfigManager(config_dir=config_dir)
        assert mgr.get("api_key") == "sk-old-plaintext"

    def test_non_sensitive_keys_stored_plaintext(self, manager, config_dir):
        manager.set("default_model", "gpt-4o")
        content = (config_dir / "config.yml").read_text()
        parsed = yaml.safe_load(content)
        assert parsed["default_model"] == "gpt-4o"
