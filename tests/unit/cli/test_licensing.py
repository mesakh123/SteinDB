"""Tests for LicenseManager -- Model C: unlimited rules-only, AI requires token."""

import pytest
from steindb.auth.models import AccountTier
from steindb.cli.config_manager import ConfigManager
from steindb.cli.licensing import FREE_TIER_LIMIT, LicenseManager


@pytest.fixture()
def config_dir(tmp_path):
    return tmp_path / ".steindb"


@pytest.fixture()
def config(config_dir):
    return ConfigManager(config_dir=config_dir)


@pytest.fixture()
def manager(config):
    return LicenseManager(config)


class TestIsAuthenticated:
    def test_not_authenticated_by_default(self, manager):
        assert manager.is_authenticated() is False

    def test_authenticated_with_api_key(self, config, manager):
        config.set("api_key", "sk-test-123")
        assert manager.is_authenticated() is True

    def test_not_authenticated_with_empty_key(self, config, manager):
        config.set("api_key", "")
        assert manager.is_authenticated() is False

    def test_not_authenticated_after_logout(self, config, manager):
        config.set("api_key", "sk-test-123")
        config.delete("api_key")
        assert manager.is_authenticated() is False


class TestGetTier:
    def test_free_tier_by_default(self, manager):
        assert manager.get_tier() == AccountTier.FREE

    def test_registered_tier_with_free_key(self, config, manager):
        config.set("api_key", "exdb_free_abc123")
        assert manager.get_tier() == AccountTier.REGISTERED

    def test_solo_tier(self, config, manager):
        config.set("api_key", "exdb_solo_abc123")
        assert manager.get_tier() == AccountTier.SOLO

    def test_team_tier(self, config, manager):
        config.set("api_key", "exdb_team_abc123")
        assert manager.get_tier() == AccountTier.TEAM

    def test_enterprise_tier(self, config, manager):
        config.set("api_key", "exdb_ent_abc123")
        assert manager.get_tier() == AccountTier.ENTERPRISE

    def test_registered_tier_with_generic_key(self, config, manager):
        config.set("api_key", "sk-pro-key")
        assert manager.get_tier() == AccountTier.REGISTERED

    def test_free_tier_with_empty_key(self, config, manager):
        config.set("api_key", "")
        assert manager.get_tier() == AccountTier.FREE

    def test_get_tier_returns_account_tier_enum(self, manager):
        tier = manager.get_tier()
        assert isinstance(tier, AccountTier)


class TestCanUseAI:
    def test_cannot_use_ai_without_key(self, manager):
        assert manager.can_use_ai() is False

    def test_can_use_ai_with_registered(self, config, manager):
        config.set("api_key", "exdb_free_abc123")
        assert manager.can_use_ai() is True

    def test_can_use_ai_with_solo(self, config, manager):
        config.set("api_key", "exdb_solo_abc123")
        assert manager.can_use_ai() is True

    def test_can_use_ai_with_team(self, config, manager):
        config.set("api_key", "exdb_team_abc123")
        assert manager.can_use_ai() is True

    def test_can_use_ai_with_enterprise(self, config, manager):
        config.set("api_key", "exdb_ent_abc123")
        assert manager.can_use_ai() is True

    def test_cannot_use_ai_with_empty_key(self, config, manager):
        config.set("api_key", "")
        assert manager.can_use_ai() is False


class TestCanUseHostedInference:
    def test_cannot_use_hosted_inference_free(self, manager):
        assert manager.can_use_hosted_inference() is False

    def test_cannot_use_hosted_inference_registered(self, config, manager):
        config.set("api_key", "exdb_free_abc123")
        assert manager.can_use_hosted_inference() is False

    def test_can_use_hosted_inference_solo(self, config, manager):
        config.set("api_key", "exdb_solo_abc123")
        assert manager.can_use_hosted_inference() is True

    def test_can_use_hosted_inference_team(self, config, manager):
        config.set("api_key", "exdb_team_abc123")
        assert manager.can_use_hosted_inference() is True

    def test_can_use_hosted_inference_enterprise(self, config, manager):
        config.set("api_key", "exdb_ent_abc123")
        assert manager.can_use_hosted_inference() is True


class TestCheckObjectLimit:
    def test_always_allowed_any_count(self, manager):
        allowed, msg = manager.check_object_limit(5)
        assert allowed is True
        assert msg == ""

    def test_always_allowed_large_count(self, manager):
        allowed, msg = manager.check_object_limit(10000)
        assert allowed is True
        assert msg == ""

    def test_always_allowed_zero_objects(self, manager):
        allowed, msg = manager.check_object_limit(0)
        assert allowed is True

    def test_no_limit_without_authentication(self, manager):
        """Free tier has no object limit -- rules-only is unlimited."""
        allowed, msg = manager.check_object_limit(100)
        assert allowed is True
        assert msg == ""


class TestClampResults:
    def test_no_clamping_any_count(self, manager):
        count, clamped = manager.clamp_results(5)
        assert count == 5
        assert clamped is False

    def test_no_clamping_large_count(self, manager):
        count, clamped = manager.clamp_results(500)
        assert count == 500
        assert clamped is False


class TestFreeTierLimit:
    def test_free_tier_limit_is_none(self):
        """No object limit -- rules-only is unlimited."""
        assert FREE_TIER_LIMIT is None
