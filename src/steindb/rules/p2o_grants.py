# src/steindb/rules/p2o_grants.py
"""P2O Grant/revoke rules: PostgreSQL GRANT/REVOKE -> Oracle.

Most GRANT/REVOKE syntax is compatible. The main difference is that
PostgreSQL uses GRANT EXECUTE ON FUNCTION, while Oracle omits the
FUNCTION/PROCEDURE keyword.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2OGrantExecuteRule(Rule):
    """GRANT EXECUTE ON FUNCTION schema.func -> GRANT EXECUTE ON schema.func.

    PostgreSQL includes FUNCTION/PROCEDURE qualifier; Oracle omits it.
    """

    name = "p2o_grant_execute"
    category = RuleCategory.P2O_GRANTS
    priority = 10
    description = "Remove FUNCTION/PROCEDURE qualifier from GRANT EXECUTE"

    _PATTERN = re.compile(
        r"(GRANT\s+EXECUTE\s+ON\s+)(?:FUNCTION|PROCEDURE)\s+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"\1", sql)


class P2ORevokeExecuteRule(Rule):
    """REVOKE EXECUTE ON FUNCTION schema.func -> REVOKE EXECUTE ON schema.func.

    Same as GRANT but for REVOKE statements.
    """

    name = "p2o_revoke_execute"
    category = RuleCategory.P2O_GRANTS
    priority = 20
    description = "Remove FUNCTION/PROCEDURE qualifier from REVOKE EXECUTE"

    _PATTERN = re.compile(
        r"(REVOKE\s+EXECUTE\s+ON\s+)(?:FUNCTION|PROCEDURE)\s+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"\1", sql)


class P2OGrantPassthroughRule(Rule):
    """Most GRANT/REVOKE syntax is compatible -- pass through.

    This rule matches GRANT/REVOKE statements and passes them through unchanged.
    It exists to register that the statement was processed.
    """

    name = "p2o_grant_passthrough"
    category = RuleCategory.P2O_GRANTS
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


# All rules in this module, for easy registration
P2O_GRANTS_RULES: list[type[Rule]] = [
    P2OGrantExecuteRule,
    P2ORevokeExecuteRule,
    P2OGrantPassthroughRule,
]
