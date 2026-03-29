# src/steindb/rules/grants.py
"""Grant/revoke rules: mostly pass-through with package -> function fixup."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class GrantExecuteRule(Rule):
    """GRANT EXECUTE ON pkg.func -> GRANT EXECUTE ON FUNCTION schema.func.

    Oracle grants execute on packages; PG needs explicit FUNCTION/PROCEDURE qualifier.
    """

    name = "grant_execute"
    category = RuleCategory.GRANTS
    priority = 10
    description = "Add FUNCTION qualifier to GRANT EXECUTE on schema-qualified objects"

    _PATTERN = re.compile(
        r"GRANT\s+EXECUTE\s+ON\s+(?!FUNCTION\b|PROCEDURE\b)"
        r"(?P<target>\w+\.\w+)\s+TO\s+(?P<grantee>\w+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            target = m.group("target")
            grantee = m.group("grantee")
            return f"GRANT EXECUTE ON FUNCTION {target} TO {grantee}"

        return self._PATTERN.sub(_replace, sql)


class GrantPassthroughRule(Rule):
    """Most GRANT/REVOKE syntax is compatible -- pass through.

    This rule matches GRANT/REVOKE statements and passes them through unchanged.
    It exists to register that the statement was processed.
    """

    name = "grant_passthrough"
    category = RuleCategory.GRANTS
    priority = 100  # Low priority: only if no other grant rule matched
    description = "Pass through compatible GRANT/REVOKE statements"

    _PATTERN = re.compile(
        r"\b(?:GRANT|REVOKE)\s+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return sql
