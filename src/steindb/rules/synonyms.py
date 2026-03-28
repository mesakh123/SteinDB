# src/steindb/rules/synonyms.py
"""Synonym resolution rules: Oracle synonyms -> PostgreSQL views."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class PublicSynonymRule(Rule):
    """CREATE PUBLIC SYNONYM syn FOR table -> CREATE VIEW syn AS SELECT * FROM table."""

    name = "public_synonym"
    category = RuleCategory.SYNONYMS
    priority = 10
    description = "Convert public synonym to view"

    _PATTERN = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?PUBLIC\s+SYNONYM\s+(?P<syn>\w+)\s+"
        r"FOR\s+(?P<target>\w+(?:\.\w+)?)\s*;?",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            syn = m.group("syn")
            target = m.group("target")
            return f"CREATE OR REPLACE VIEW {syn} AS SELECT * FROM {target};"

        return self._PATTERN.sub(_replace, sql)


class PrivateSynonymRule(Rule):
    """CREATE SYNONYM syn FOR table -> CREATE VIEW syn AS SELECT * FROM table."""

    name = "private_synonym"
    category = RuleCategory.SYNONYMS
    priority = 20
    description = "Convert private synonym to view"

    _PATTERN = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?SYNONYM\s+(?P<syn>\w+)\s+"
        r"FOR\s+(?P<target>\w+(?:\.\w+)?)\s*;?",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        # Avoid matching public synonyms (handled by PublicSynonymRule)
        if re.search(r"\bPUBLIC\s+SYNONYM\b", sql, re.IGNORECASE):
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            syn = m.group("syn")
            target = m.group("target")
            return f"CREATE OR REPLACE VIEW {syn} AS SELECT * FROM {target};"

        return self._PATTERN.sub(_replace, sql)


class DropSynonymRule(Rule):
    """DROP SYNONYM syn -> DROP VIEW IF EXISTS syn."""

    name = "drop_synonym"
    category = RuleCategory.SYNONYMS
    priority = 30
    description = "Convert DROP SYNONYM to DROP VIEW IF EXISTS"

    _PATTERN = re.compile(
        r"DROP\s+(?:PUBLIC\s+)?SYNONYM\s+(?P<syn>\w+)\s*;?",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            syn = m.group("syn")
            return f"DROP VIEW IF EXISTS {syn};"

        return self._PATTERN.sub(_replace, sql)
