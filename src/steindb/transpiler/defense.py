# src/steindb/transpiler/defense.py
"""Prompt injection defense for the LLM Transpiler.

Layered approach:
1. Unicode normalization (NFKC) to prevent homoglyph bypass
2. Input sanitization: strip suspicious patterns from Oracle SQL
3. SQL comment stripping for defense-in-depth
4. Input length validation
5. Canary tokens: detect if the LLM leaks internal markers
6. Output validation: verify output is valid SQL, not prose, HTML, or markdown

Addresses CrowdStrike findings CS-P1-1 (prompt injection defense bypassable)
and the Unicode/homoglyph bypass vector.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_INPUT_LENGTH: int = 50_000  # 50 KB max SQL input for LLM transpiler

# Patterns that indicate prompt injection attempts
SUSPICIOUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
    re.compile(r"forget\s+(all\s+)?(your\s+)?instructions", re.I),
    re.compile(r"system\s*:\s*you", re.I),
    re.compile(r"output\s+(the\s+)?password", re.I),
    re.compile(r"reveal\s+(your\s+)?(system|secret|prompt)", re.I),
    re.compile(r"do\s+not\s+follow\s+(the\s+)?rules", re.I),
    re.compile(r"override\s+(all\s+)?constraints", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s+mode", re.I),
    # Additional patterns to close bypass vectors
    re.compile(r"disregard\s+(all\s+)?(previous\s+)?instructions", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"act\s+as\s+(a\s+)?", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.I),
    re.compile(r"bypass\s+(all\s+)?filters", re.I),
]

# Patterns that indicate the output contains non-SQL prose
_PROSE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^I\s+(apologize|cannot|can't|am\s+sorry)", re.I | re.M),
    re.compile(r"^(Sure|Of course|Certainly|Here\s+is),?\s", re.I | re.M),
    re.compile(r"ignore\s+all\s+constraints", re.I),
]

# Patterns that indicate output contains non-SQL content (HTML, markdown)
_NON_SQL_OUTPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<(script|div|span|html|body|head|style|iframe)\b", re.I),
    re.compile(r"```", re.I),  # Markdown code fences
    re.compile(r"^\s*#{1,6}\s+", re.M),  # Markdown headers
    re.compile(r"\[.*?\]\(https?://", re.I),  # Markdown links
    re.compile(r"<!\-\-.*?\-\->", re.S),  # HTML comments
]


# ---------------------------------------------------------------------------
# Unicode normalization
# ---------------------------------------------------------------------------


def normalize_unicode(text: str) -> str:
    """Apply NFKC normalization to prevent homoglyph bypass.

    NFKC normalization converts visually similar Unicode characters to their
    ASCII equivalents (e.g., fullwidth 'A' -> 'A', Cyrillic 'а' stays but
    compatibility forms are normalized). This closes the homoglyph bypass
    vector identified by CrowdStrike.
    """
    return unicodedata.normalize("NFKC", text)


# ---------------------------------------------------------------------------
# SQL comment stripping
# ---------------------------------------------------------------------------


def strip_sql_comments(sql: str) -> str:
    """Remove all SQL comments (both -- line comments and /* */ blocks).

    This is a defense-in-depth measure: injection payloads are commonly
    hidden in SQL comments.
    """
    # Remove block comments (handles nested by removing outermost)
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    # Remove single-line comments
    sql = re.sub(r"--[^\n]*", "", sql)
    return sql


# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------


def sanitize_oracle_input(sql: str) -> str:
    """Sanitize Oracle SQL input before sending to the LLM.

    Steps:
    1. Unicode NFKC normalization
    2. Input length validation
    3. Strip suspicious patterns from comments
    4. Strip suspicious patterns from block comments
    5. Strip suspicious patterns from string literals
    """
    # Step 1: Normalize Unicode to prevent homoglyph bypass
    sql = normalize_unicode(sql)

    # Step 2: Input length validation
    if len(sql) > MAX_INPUT_LENGTH:
        raise InputTooLargeError(
            f"SQL input exceeds maximum length: {len(sql):,} > {MAX_INPUT_LENGTH:,} chars"
        )

    # Step 3-5: Check all suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        # Check in single-line comments
        sql = _strip_suspicious_comments(sql, pattern)
        # Check in block comments
        sql = _strip_suspicious_block_comments(sql, pattern)
        # Check in string literals
        sql = _strip_suspicious_string_literals(sql, pattern)

    return sql


class InputTooLargeError(Exception):
    """Raised when SQL input exceeds the maximum allowed length."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_suspicious_comments(sql: str, pattern: re.Pattern[str]) -> str:
    """Strip single-line comments that match a suspicious pattern."""
    lines: list[str] = []
    for line in sql.split("\n"):
        comment_match = re.search(r"--(.*)$", line)
        if comment_match and pattern.search(comment_match.group(1)):
            # Remove only the comment, keep the SQL
            line = line[: comment_match.start()].rstrip()
        lines.append(line)
    return "\n".join(lines)


def _strip_suspicious_block_comments(sql: str, pattern: re.Pattern[str]) -> str:
    """Strip block comments that match a suspicious pattern."""

    def replace_if_suspicious(match: re.Match[str]) -> str:
        if pattern.search(match.group(0)):
            return ""
        return match.group(0)

    return re.sub(r"/\*[\s\S]*?\*/", replace_if_suspicious, sql)


def _strip_suspicious_string_literals(sql: str, pattern: re.Pattern[str]) -> str:
    """Strip string literals that contain suspicious injection patterns.

    Replaces the string content with a safe placeholder while preserving
    SQL structure. This closes the vector where injection payloads are
    embedded in INSERT/VALUES string literals.
    """

    def replace_if_suspicious(match: re.Match[str]) -> str:
        if pattern.search(match.group(0)):
            return "'[REDACTED]'"
        return match.group(0)

    return re.sub(r"'[^']*'", replace_if_suspicious, sql)


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyCheckResult:
    """Result of an output safety check."""

    is_safe: bool
    reason: str = ""


def validate_output_safety(output: str) -> SafetyCheckResult:
    """Check that LLM output looks like SQL, not injected instructions.

    Validates against:
    1. Prose patterns (LLM conversational responses)
    2. Suspicious injection patterns
    3. Non-SQL content (HTML, markdown)
    """
    # Check for prose patterns
    for pattern in _PROSE_PATTERNS:
        if pattern.search(output):
            return SafetyCheckResult(
                is_safe=False,
                reason=f"Output contains non-SQL prose: {pattern.pattern}",
            )

    # Check for suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(output):
            return SafetyCheckResult(
                is_safe=False,
                reason=f"Output contains suspicious pattern: {pattern.pattern}",
            )

    # Check for HTML/markdown content
    for pattern in _NON_SQL_OUTPUT_PATTERNS:
        if pattern.search(output):
            return SafetyCheckResult(
                is_safe=False,
                reason=f"Output contains non-SQL content: {pattern.pattern}",
            )

    return SafetyCheckResult(is_safe=True)


# ---------------------------------------------------------------------------
# Canary tokens
# ---------------------------------------------------------------------------


def generate_canary_token() -> str:
    """Generate a random canary token to embed in prompts."""
    return f"EXDB_{secrets.token_hex(12)}"


def check_canary_leakage(canary: str, output: str) -> bool:
    """Check if the canary token leaked into the LLM output."""
    return canary in output
