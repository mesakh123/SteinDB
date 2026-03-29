"""License management for SteinDB CLI.

Model C: unlimited free CLI (rules-only), registration required for AI/cloud
features, payment for hosted inference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from steindb.auth.models import AccountTier, get_tier_from_token

if TYPE_CHECKING:
    from steindb.cli.config_manager import ConfigManager

FREE_TIER_LIMIT = None  # No object limit -- rules-only is unlimited


class LicenseManager:
    """Manages tier detection and AI feature gating.

    Tiers:
    - FREE: no token, unlimited rules-only, no AI
    - REGISTERED: free token, BYOK AI mode unlocked
    - SOLO: paid token, hosted inference + monitoring
    - TEAM: paid token, hosted inference + monitoring + team features
    - ENTERPRISE: custom token, full feature set
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config = config_manager

    def is_authenticated(self) -> bool:
        """Check if user has a valid API key."""
        api_key = self.config.get("api_key")
        return api_key is not None and len(api_key) > 0

    def get_tier(self) -> AccountTier:
        """Return the account tier based on stored token."""
        key = self.config.get("api_key")
        if key is None or len(key) == 0:
            return AccountTier.FREE
        return get_tier_from_token(key)

    def can_use_ai(self) -> bool:
        """Return True if the user can use AI-assisted conversion.

        Requires authentication (free registration minimum).
        """
        return self.get_tier() != AccountTier.FREE

    def can_use_hosted_inference(self) -> bool:
        """Return True if the user can use hosted inference (paid tiers only)."""
        return self.get_tier() in (AccountTier.SOLO, AccountTier.TEAM, AccountTier.ENTERPRISE)

    def check_object_limit(self, object_count: int) -> tuple[bool, str]:
        """Check if within object limit.

        Returns:
            A tuple of (allowed, message). Always allowed -- no object limit.
        """
        return True, ""

    def clamp_results(self, total_count: int) -> tuple[int, bool]:
        """Return (display_count, was_clamped).

        No clamping -- all results are always shown.
        """
        return total_count, False
