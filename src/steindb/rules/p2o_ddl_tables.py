# src/steindb/rules/p2o_ddl_tables.py
"""P2O DDL Table rules: PostgreSQL CREATE TABLE -> Oracle CREATE TABLE.

Handles structural DDL transformations for table creation including
temp tables, unlogged tables, identity columns, and PG-specific defaults.
Data type conversions are handled by P2O datatype rules that run earlier.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2OCreateTempTableRule(Rule):
    """CREATE TEMP TABLE -> CREATE GLOBAL TEMPORARY TABLE ... ON COMMIT DELETE ROWS.

    PostgreSQL TEMP / TEMPORARY tables become Oracle GLOBAL TEMPORARY TABLEs.
    If no ON COMMIT clause is present, Oracle defaults to ON COMMIT DELETE ROWS.
    """

    name = "p2o_create_temp_table"
    category = RuleCategory.P2O_DDL_TABLES
    priority = 10
    description = "Convert CREATE TEMP TABLE to CREATE GLOBAL TEMPORARY TABLE"

    _TEMP_TABLE = re.compile(
        r"\bCREATE\s+(?:TEMP|TEMPORARY)\s+TABLE\b",
        re.IGNORECASE,
    )
    _ON_COMMIT = re.compile(r"\bON\s+COMMIT\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._TEMP_TABLE.search(sql))

    def apply(self, sql: str) -> str:
        sql = self._TEMP_TABLE.sub("CREATE GLOBAL TEMPORARY TABLE", sql)
        # If there is no ON COMMIT clause, add the Oracle default
        if not self._ON_COMMIT.search(sql):
            # Append before trailing semicolon or at end
            sql = re.sub(
                r"(\s*;?\s*)$",
                r" ON COMMIT DELETE ROWS\1",
                sql,
                count=1,
            )
        return sql


class P2OCreateUnloggedTableRule(Rule):
    """CREATE UNLOGGED TABLE -> CREATE TABLE (remove UNLOGGED, add comment).

    Oracle has no UNLOGGED concept. We strip the keyword and leave a comment.
    """

    name = "p2o_create_unlogged_table"
    category = RuleCategory.P2O_DDL_TABLES
    priority = 20
    description = "Remove UNLOGGED from CREATE TABLE (Oracle has no equivalent)"

    _UNLOGGED = re.compile(
        r"\bCREATE\s+UNLOGGED\s+TABLE\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._UNLOGGED.search(sql))

    def apply(self, sql: str) -> str:
        sql = self._UNLOGGED.sub("CREATE TABLE", sql)
        sql = "/* SteinDB: UNLOGGED removed (no Oracle equivalent) */\n" + sql
        return sql


class P2OIfNotExistsRule(Rule):
    """Remove IF NOT EXISTS from CREATE TABLE (Oracle < 23c doesn't support it)."""

    name = "p2o_if_not_exists"
    category = RuleCategory.P2O_DDL_TABLES
    priority = 30
    description = "Remove IF NOT EXISTS (not supported in Oracle < 23c)"

    _IF_NOT_EXISTS = re.compile(
        r"\bIF\s+NOT\s+EXISTS\s+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "CREATE" not in upper:
            return False
        return bool(self._IF_NOT_EXISTS.search(sql))

    def apply(self, sql: str) -> str:
        return self._IF_NOT_EXISTS.sub("", sql)


class P2ODefaultCurrentTimestampRule(Rule):
    """DEFAULT CURRENT_TIMESTAMP -> DEFAULT SYSDATE.

    Also handles DEFAULT NOW().
    """

    name = "p2o_default_current_timestamp"
    category = RuleCategory.P2O_DDL_TABLES
    priority = 40
    description = "Convert DEFAULT CURRENT_TIMESTAMP/NOW() to DEFAULT SYSDATE"

    _CURRENT_TS = re.compile(
        r"\bDEFAULT\s+CURRENT_TIMESTAMP\b",
        re.IGNORECASE,
    )
    _NOW = re.compile(
        r"\bDEFAULT\s+NOW\s*\(\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._CURRENT_TS.search(sql) or self._NOW.search(sql))

    def apply(self, sql: str) -> str:
        sql = self._CURRENT_TS.sub("DEFAULT SYSDATE", sql)
        sql = self._NOW.sub("DEFAULT SYSDATE", sql)
        return sql


class P2OGeneratedAlwaysAsIdentityRule(Rule):
    """GENERATED ALWAYS AS IDENTITY -> NUMBER + SEQUENCE + TRIGGER.

    Converts PostgreSQL identity columns to Oracle-compatible sequence+trigger
    pattern for pre-12c compatibility.

    Example input:
        CREATE TABLE t (id INTEGER GENERATED ALWAYS AS IDENTITY, name VARCHAR(100));
    Example output:
        CREATE TABLE t (id NUMBER NOT NULL, name VARCHAR(100));
        CREATE SEQUENCE t_id_seq START WITH 1 INCREMENT BY 1;
        CREATE OR REPLACE TRIGGER t_id_trg BEFORE INSERT ON t FOR EACH ROW BEGIN
          SELECT t_id_seq.NEXTVAL INTO :NEW.id FROM DUAL; END;
    """

    name = "p2o_generated_always_as_identity"
    category = RuleCategory.P2O_DDL_TABLES
    priority = 50
    description = "Convert GENERATED ALWAYS AS IDENTITY to NUMBER + SEQUENCE + TRIGGER"

    _IDENTITY = re.compile(
        r"(\b(\w+)\s+\w+)\s+GENERATED\s+(?:ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY"
        r"(?:\s*\([^)]*\))?",
        re.IGNORECASE,
    )
    _CREATE_TABLE_NAME = re.compile(
        r"\bCREATE\s+TABLE\s+(\S+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._IDENTITY.search(sql))

    def apply(self, sql: str) -> str:
        table_match = self._CREATE_TABLE_NAME.search(sql)
        if not table_match:
            return sql

        table_name = table_match.group(1)
        extra_statements: list[str] = []

        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(2)
            seq_name = f"{table_name}_{col_name}_seq"
            trg_name = f"{table_name}_{col_name}_trg"
            extra_statements.append(f"CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1")
            extra_statements.append(
                f"CREATE OR REPLACE TRIGGER {trg_name} "
                f"BEFORE INSERT ON {table_name} FOR EACH ROW BEGIN "
                f"SELECT {seq_name}.NEXTVAL INTO :NEW.{col_name} FROM DUAL; END"
            )
            return f"{col_name} NUMBER NOT NULL"

        sql = self._IDENTITY.sub(_replace, sql)

        if extra_statements:
            sql = sql.rstrip().rstrip(";")
            sql = sql + ";\n" + ";\n".join(extra_statements) + ";"

        return sql


# All rules in this module, for easy registration
P2O_DDL_TABLES_RULES: list[type[Rule]] = [
    P2OCreateTempTableRule,
    P2OCreateUnloggedTableRule,
    P2OIfNotExistsRule,
    P2ODefaultCurrentTimestampRule,
    P2OGeneratedAlwaysAsIdentityRule,
]
