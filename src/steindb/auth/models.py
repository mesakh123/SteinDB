# src/steindb/auth/models.py
"""Token and account models for authentication."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class AccountTier(StrEnum):
    """Subscription tier for an account."""

    FREE = "free"  # No token needed
    REGISTERED = "registered"  # Free token
    SOLO = "solo"  # $99/mo
    TEAM = "team"  # $499/mo
    ENTERPRISE = "enterprise"  # Custom


TOKEN_PREFIX_MAP: dict[str, AccountTier] = {
    "stdb_free_": AccountTier.REGISTERED,
    "stdb_solo_": AccountTier.SOLO,
    "stdb_team_": AccountTier.TEAM,
    "stdb_ent_": AccountTier.ENTERPRISE,
}


def generate_token(tier: AccountTier = AccountTier.REGISTERED) -> str:
    """Generate a new opaque token. Format: stdb_{tier}_{40 hex chars}. (SteinDB token prefix)"""
    prefix = {
        AccountTier.REGISTERED: "stdb_free_",
        AccountTier.SOLO: "stdb_solo_",
        AccountTier.TEAM: "stdb_team_",
        AccountTier.ENTERPRISE: "stdb_ent_",
    }[tier]
    return prefix + secrets.token_hex(20)


def hash_token(raw_token: str) -> str:
    """SHA-256 hash a token for storage. Raw token is never stored."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def get_tier_from_token(token: str) -> AccountTier:
    """Determine tier from token prefix."""
    for prefix, tier in TOKEN_PREFIX_MAP.items():
        if token.startswith(prefix):
            return tier
    return AccountTier.REGISTERED  # default for unknown prefix


@dataclass
class Account:
    """User account."""

    id: str
    email: str
    tier: AccountTier = AccountTier.REGISTERED
    token_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True


@dataclass
class TokenValidation:
    """Result of validating a token."""

    valid: bool
    tier: AccountTier = AccountTier.FREE
    account_id: str | None = None
    error: str | None = None
