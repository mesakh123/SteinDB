# src/steindb/rules/sequences.py
"""Sequence conversion rules: Oracle sequence syntax to PostgreSQL.

Named sequences.py — was sequences_mod.py to avoid conflict with Python's sequences module.
Handles NEXTVAL/CURRVAL syntax and CREATE SEQUENCE cleanup.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class NEXTVALRule(Rule):
    """seq_name.NEXTVAL -> nextval('seq_name').

    Oracle uses dot notation (schema.seq.NEXTVAL or seq.NEXTVAL);
    PostgreSQL uses the nextval() function.
    """

    name = "nextval"
    category = RuleCategory.SEQUENCES
    priority = 10
    description = "Convert .NEXTVAL to nextval()"

    _PATTERN = re.compile(
        r"(\b[\w.]*\w)\.NEXTVAL\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"nextval('\1')", sql)


class CURRVALRule(Rule):
    """seq_name.CURRVAL -> currval('seq_name')."""

    name = "currval"
    category = RuleCategory.SEQUENCES
    priority = 20
    description = "Convert .CURRVAL to currval()"

    _PATTERN = re.compile(
        r"(\b[\w.]*\w)\.CURRVAL\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"currval('\1')", sql)


class NOCACHERemovalRule(Rule):
    """Remove NOCACHE from CREATE SEQUENCE.

    PostgreSQL does not have a NOCACHE keyword for sequences.
    Note: CACHE <n> IS valid in PostgreSQL and should be kept.
    """

    name = "sequence_nocache_removal"
    category = RuleCategory.SEQUENCES
    priority = 30
    description = "Remove NOCACHE from CREATE SEQUENCE"

    _PATTERN = re.compile(r"\s*\bNOCACHE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "SEQUENCE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class CreateSequenceCleanupRule(Rule):
    """Remove Oracle-specific options from CREATE SEQUENCE.

    Removes: NOORDER, NOMINVALUE, NOMAXVALUE, NOCYCLE
    (PostgreSQL defaults match these semantics, so they can be dropped.)
    Note: NOMAXVALUE and NOCYCLE are not needed because PG defaults are the same.
    """

    name = "sequence_cleanup"
    category = RuleCategory.SEQUENCES
    priority = 40
    description = "Remove Oracle-specific sequence options"

    _PATTERN = re.compile(
        r"\s*\b(?:NOORDER|NOMINVALUE|NOMAXVALUE|NOCYCLE)\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "SEQUENCE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


# All rules in this module, for easy registration
SEQUENCES_RULES: list[type[Rule]] = [
    NEXTVALRule,
    CURRVALRule,
    NOCACHERemovalRule,
    CreateSequenceCleanupRule,
]
