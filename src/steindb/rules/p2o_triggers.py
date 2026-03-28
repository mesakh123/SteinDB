# src/steindb/rules/p2o_triggers.py
"""P2O trigger rewrite rules: PostgreSQL trigger function + trigger -> Oracle single trigger.

Handles simple cases; complex trigger patterns are forwarded to the LLM Transpiler.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class PGNewOldToColonRule(Rule):
    """NEW.col -> :NEW.col, OLD.col -> :OLD.col in trigger context."""

    name = "p2o_new_old_colon"
    category = RuleCategory.P2O_TRIGGERS
    priority = 10
    description = "Add colon prefix to NEW/OLD trigger references for Oracle"

    _PATTERN = re.compile(
        r"(?<!:)\b(?P<ref>NEW|OLD)\.(?P<col>\w+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        # Only match in trigger context
        if not re.search(r"\bTRIGGER\b", sql, re.IGNORECASE):
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            ref = m.group("ref").upper()
            col = m.group("col")
            return f":{ref}.{col}"

        return self._PATTERN.sub(_replace, sql)


class TriggerFunctionMergeRule(Rule):
    """Merge CREATE FUNCTION ... RETURNS TRIGGER + CREATE TRIGGER into single Oracle trigger.

    PostgreSQL pattern:
        CREATE OR REPLACE FUNCTION trg_func() RETURNS TRIGGER AS $$
        BEGIN
            ...body...
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_name BEFORE INSERT ON table_name
        FOR EACH ROW EXECUTE FUNCTION trg_func();

    Oracle pattern:
        CREATE OR REPLACE TRIGGER trg_name
        BEFORE INSERT ON table_name
        FOR EACH ROW
        BEGIN
            ...body...
        END;

    Only handles simple cases where the function and trigger are in the same SQL block.
    Complex patterns (multiple triggers sharing one function, dynamic SQL in trigger body,
    etc.) are forwarded to the LLM Transpiler.
    """

    name = "p2o_trigger_function_merge"
    category = RuleCategory.P2O_TRIGGERS
    priority = 100  # Runs last -- other trigger rules clean up body first
    description = "Merge PG trigger function + trigger into single Oracle trigger"

    # Match the function definition
    _FUNC_RE = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?P<func_name>\w+)\s*\(\s*\)\s+"
        r"RETURNS\s+TRIGGER\s+AS\s+\$\$\s*"
        r"(?:DECLARE\s+(?P<declare>.*?))?"
        r"BEGIN\s+(?P<body>.*?)"
        r"END;\s*\$\$\s*LANGUAGE\s+plpgsql\s*;?",
        re.IGNORECASE | re.DOTALL,
    )

    # Match the trigger definition referencing the function
    _TRIGGER_RE = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?P<trg_name>\w+)\s+"
        r"(?P<timing>BEFORE|AFTER|INSTEAD\s+OF)\s+"
        r"(?P<events>(?:INSERT|UPDATE|DELETE)(?:\s+OR\s+(?:INSERT|UPDATE|DELETE))*)\s+"
        r"ON\s+(?P<table>\w+(?:\.\w+)?)\s*"
        r"(?:FOR\s+EACH\s+ROW\s+)?"
        r"EXECUTE\s+(?:FUNCTION|PROCEDURE)\s+(?P<func_name>\w+)\s*\(\s*\)\s*;?",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        func_match = self._FUNC_RE.search(sql)
        trigger_match = self._TRIGGER_RE.search(sql)
        if not func_match or not trigger_match:
            return False
        # Check that the trigger references the function
        func_name = func_match.group("func_name").lower()
        trigger_func = trigger_match.group("func_name").lower()
        return func_name == trigger_func

    def apply(self, sql: str) -> str:
        func_match = self._FUNC_RE.search(sql)
        trigger_match = self._TRIGGER_RE.search(sql)
        if not func_match or not trigger_match:
            return sql

        # Verify function names match
        func_name = func_match.group("func_name").lower()
        trigger_func = trigger_match.group("func_name").lower()
        if func_name != trigger_func:
            return sql

        trg_name = trigger_match.group("trg_name")
        timing = trigger_match.group("timing").upper()
        events = trigger_match.group("events").upper()
        table = trigger_match.group("table")
        declare = func_match.group("declare") or ""
        body = func_match.group("body").strip()

        # Remove ALL RETURN NEW; / RETURN OLD; / RETURN NULL; from body
        # (Oracle triggers don't have explicit return — PG trigger functions
        # use RETURN NEW/OLD/NULL to control row visibility, but Oracle triggers
        # achieve this through BEFORE/AFTER timing and :NEW/:OLD references)
        body = re.sub(
            r"\s*RETURN\s+(?:NEW|OLD|NULL)\s*;",
            "",
            body,
            flags=re.IGNORECASE,
        )

        declare_block = ""
        if declare.strip():
            declare_block = f"\nDECLARE\n    {declare.strip()}"

        lines = [
            f"CREATE OR REPLACE TRIGGER {trg_name}",
            f"{timing} {events} ON {table}",
            f"FOR EACH ROW{declare_block}",
            "BEGIN",
            f"    {body.strip()}",
            f"END {trg_name};",
        ]
        return "\n".join(lines)


class SimpleTriggerBodyRule(Rule):
    """Handle standalone Oracle-style trigger body cleanup for simple cases.

    When a PG trigger function body is already extracted but contains PG-specific
    constructs, this rule marks complex triggers for LLM forwarding.
    """

    name = "p2o_complex_trigger_marker"
    category = RuleCategory.P2O_TRIGGERS
    priority = 50
    description = "Mark complex trigger patterns for LLM forwarding"

    # Detect PG-specific trigger constructs that need LLM
    _COMPLEX_PATTERNS = [
        re.compile(r"\bTG_OP\b", re.IGNORECASE),  # trigger operation variable
        re.compile(r"\bTG_TABLE_NAME\b", re.IGNORECASE),  # table name variable
        re.compile(r"\bTG_NARGS\b", re.IGNORECASE),  # trigger args count
        re.compile(r"\bTG_ARGV\b", re.IGNORECASE),  # trigger arguments
        re.compile(r"\bPERFORM\b", re.IGNORECASE),  # PG-specific PERFORM
    ]

    _TRIGGER_CONTEXT_RE = re.compile(r"RETURNS\s+TRIGGER", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        if not self._TRIGGER_CONTEXT_RE.search(sql):
            return False
        return any(pat.search(sql) for pat in self._COMPLEX_PATTERNS)

    def apply(self, sql: str) -> str:
        detected = []
        for pat in self._COMPLEX_PATTERNS:
            if pat.search(sql):
                detected.append(pat.pattern.replace(r"\b", ""))
        features = ", ".join(detected)
        comment = (
            f"/* LLM_FORWARD: Complex trigger detected ({features}). "
            f"Requires manual review or LLM Transpiler. */\n"
        )
        return comment + sql
