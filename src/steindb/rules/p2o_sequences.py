# src/steindb/rules/p2o_sequences.py
"""P2O Sequence rules: PostgreSQL sequence syntax -> Oracle.

Handles nextval()/currval() function calls to dot-notation,
CREATE SEQUENCE cleanup, and GENERATED ALWAYS AS IDENTITY conversion.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2ONextvalRule(Rule):
    """nextval('seq_name') -> seq_name.NEXTVAL.

    PostgreSQL uses the nextval() function; Oracle uses dot notation.
    """

    name = "p2o_nextval"
    category = RuleCategory.P2O_SEQUENCES
    priority = 10
    description = "Convert nextval('seq') to seq.NEXTVAL"

    _PATTERN = re.compile(
        r"\bnextval\s*\(\s*'([^']+)'\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"\1.NEXTVAL", sql)


class P2OCurrvalRule(Rule):
    """currval('seq_name') -> seq_name.CURRVAL."""

    name = "p2o_currval"
    category = RuleCategory.P2O_SEQUENCES
    priority = 20
    description = "Convert currval('seq') to seq.CURRVAL"

    _PATTERN = re.compile(
        r"\bcurrval\s*\(\s*'([^']+)'\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"\1.CURRVAL", sql)


class P2OSequenceNoCycleRule(Rule):
    """NO CYCLE -> NOCYCLE in CREATE SEQUENCE.

    PostgreSQL uses NO CYCLE (two words); Oracle uses NOCYCLE (one word).
    """

    name = "p2o_sequence_no_cycle"
    category = RuleCategory.P2O_SEQUENCES
    priority = 30
    description = "Convert NO CYCLE to NOCYCLE"

    _PATTERN = re.compile(r"\bNO\s+CYCLE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "SEQUENCE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("NOCYCLE", sql)


class P2OSequenceCache1Rule(Rule):
    """CACHE 1 -> NOCACHE in CREATE SEQUENCE.

    PostgreSQL CACHE 1 means no caching; Oracle equivalent is NOCACHE.
    """

    name = "p2o_sequence_cache_1"
    category = RuleCategory.P2O_SEQUENCES
    priority = 40
    description = "Convert CACHE 1 to NOCACHE"

    _PATTERN = re.compile(r"\bCACHE\s+1\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "SEQUENCE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("NOCACHE", sql)


class P2OSequenceNoMinvalueRule(Rule):
    """NO MINVALUE -> NOMINVALUE in CREATE SEQUENCE."""

    name = "p2o_sequence_no_minvalue"
    category = RuleCategory.P2O_SEQUENCES
    priority = 50
    description = "Convert NO MINVALUE to NOMINVALUE"

    _PATTERN = re.compile(r"\bNO\s+MINVALUE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "SEQUENCE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("NOMINVALUE", sql)


class P2OSequenceNoMaxvalueRule(Rule):
    """NO MAXVALUE -> NOMAXVALUE in CREATE SEQUENCE."""

    name = "p2o_sequence_no_maxvalue"
    category = RuleCategory.P2O_SEQUENCES
    priority = 60
    description = "Convert NO MAXVALUE to NOMAXVALUE"

    _PATTERN = re.compile(r"\bNO\s+MAXVALUE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "SEQUENCE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("NOMAXVALUE", sql)


# All rules in this module, for easy registration
P2O_SEQUENCES_RULES: list[type[Rule]] = [
    P2ONextvalRule,
    P2OCurrvalRule,
    P2OSequenceNoCycleRule,
    P2OSequenceCache1Rule,
    P2OSequenceNoMinvalueRule,
    P2OSequenceNoMaxvalueRule,
]
