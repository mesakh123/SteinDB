# src/steindb/rules/triggers.py
"""Trigger rewrite rules: Oracle triggers -> PostgreSQL trigger functions."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class NewOldPrefixRule(Rule):
    """:NEW.col -> NEW.col, :OLD.col -> OLD.col (remove colon prefix)."""

    name = "new_old_prefix"
    category = RuleCategory.TRIGGERS
    priority = 10
    description = "Remove colon prefix from :NEW/:OLD trigger references"

    _PATTERN = re.compile(r":(?P<ref>NEW|OLD)\.(?P<col>\w+)", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            ref = m.group("ref").upper()
            col = m.group("col")
            return f"{ref}.{col}"

        return self._PATTERN.sub(_replace, sql)


class RaiseApplicationErrorRule(Rule):
    """RAISE_APPLICATION_ERROR(-nnnnn, 'msg') -> RAISE EXCEPTION '%', msg.

    Uses PL/pgSQL format-string syntax so that both literal strings and
    expressions (e.g. 'Error: ' || v_msg) produce valid output.
    """

    name = "raise_application_error"
    category = RuleCategory.TRIGGERS
    priority = 20
    description = "Convert RAISE_APPLICATION_ERROR to RAISE EXCEPTION"

    _PATTERN = re.compile(
        r"RAISE_APPLICATION_ERROR\s*\(\s*-?\d+\s*,\s*(?P<msg>[^)]+)\)",
        re.IGNORECASE,
    )

    # Simple string literal: 'some text' (possibly with escaped quotes)
    _SIMPLE_STRING_RE = re.compile(r"^'(?:''|[^'])*'$")

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            msg = m.group("msg").strip()
            # If msg is a simple string literal, use it directly as the format string
            if self._SIMPLE_STRING_RE.match(msg):
                return f"RAISE EXCEPTION {msg}"
            # Otherwise use format-string syntax: RAISE EXCEPTION '%', expr
            return f"RAISE EXCEPTION '%', {msg}"

        return self._PATTERN.sub(_replace, sql)


class AutoIncrementTriggerRule(Rule):
    """Detect sequence-based auto-increment triggers and suggest IDENTITY.

    Detects patterns like:
        SELECT seq.NEXTVAL INTO :NEW.id FROM DUAL;
    And converts to a comment suggesting GENERATED ALWAYS AS IDENTITY.
    """

    name = "auto_increment_trigger"
    category = RuleCategory.TRIGGERS
    priority = 30
    description = "Detect sequence-based auto-increment triggers -> IDENTITY suggestion"

    _PATTERN = re.compile(
        r"SELECT\s+\w+\.NEXTVAL\s+INTO\s+:?NEW\.(\w+)\s+FROM\s+DUAL",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        m = self._PATTERN.search(sql)
        if not m:
            return sql
        col = m.group(1)
        return (
            f"-- AUTO-INCREMENT DETECTED: Column '{col}' uses sequence-based trigger.\n"
            f"-- Recommendation: ALTER TABLE ... ALTER COLUMN {col} "
            f"ADD GENERATED ALWAYS AS IDENTITY;\n"
            f"-- Original trigger can be dropped after migration."
        )


class TriggerBodyExtractionRule(Rule):
    """Extract trigger body into CREATE FUNCTION + CREATE TRIGGER.

    Oracle:
        CREATE OR REPLACE TRIGGER trg
        BEFORE INSERT ON t FOR EACH ROW
        BEGIN ... END;

    PostgreSQL:
        CREATE OR REPLACE FUNCTION trg_func() RETURNS TRIGGER AS $$
        BEGIN ... END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg BEFORE INSERT ON t
        FOR EACH ROW EXECUTE FUNCTION trg_func();
    """

    name = "trigger_body_extraction"
    category = RuleCategory.TRIGGERS
    priority = 100  # Runs last -- other trigger rules clean up body first
    description = "Extract Oracle trigger body into PG function + trigger pair"

    _TRIGGER_PATTERN = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?P<name>\w+)\s+"
        r"(?P<timing>BEFORE|AFTER|INSTEAD\s+OF)\s+"
        r"(?P<events>(?:INSERT|UPDATE|DELETE)(?:\s+OR\s+(?:INSERT|UPDATE|DELETE))*)\s+"
        r"ON\s+(?P<table>\w+(?:\.\w+)?)\s*"
        r"(?:FOR\s+EACH\s+ROW\s*)?"
        r"(?:(?:DECLARE\s+(?P<declare>.*?))?BEGIN\s+(?P<body>.*?)\s*END\s*(?:\w+\s*)?;)",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._TRIGGER_PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        m = self._TRIGGER_PATTERN.search(sql)
        if not m:
            return sql

        trg_name = m.group("name")
        timing = m.group("timing").upper()
        events = m.group("events").upper()
        table = m.group("table")
        declare = m.group("declare") or ""
        body = m.group("body")

        func_name = f"{trg_name}_func"

        declare_block = ""
        if declare.strip():
            declare_block = f"DECLARE\n{declare.strip()}\n"

        # Determine correct RETURN value:
        # - DELETE-only BEFORE triggers must RETURN OLD (there is no NEW row)
        # - AFTER triggers: return value is ignored, but RETURN NULL is conventional
        # - All other BEFORE/INSTEAD OF triggers: RETURN NEW
        events_upper = events.upper().strip()
        is_delete_only = events_upper == "DELETE"
        is_after = timing.upper().strip() == "AFTER"

        if is_after:
            return_stmt = "RETURN NULL;"
        elif is_delete_only:
            return_stmt = "RETURN OLD;"
        else:
            return_stmt = "RETURN NEW;"

        # Normalize body indentation: strip each line and re-indent with 2 spaces
        body_lines = body.strip().splitlines()
        normalized_body = "\n".join(
            f"  {line.strip()}" if line.strip() else "" for line in body_lines
        )

        lines = [
            f"CREATE OR REPLACE FUNCTION {func_name}() RETURNS TRIGGER AS $$",
            declare_block + "BEGIN",
            normalized_body,
            f"  {return_stmt}",
            "END;",
            "$$ LANGUAGE plpgsql;",
            "",
            f"CREATE TRIGGER {trg_name} {timing} {events} ON {table}",
            f"FOR EACH ROW EXECUTE FUNCTION {func_name}();",
        ]
        return "\n".join(lines)
