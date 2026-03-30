# src/steindb/rules/plsql_basic.py
"""PL/SQL basic wrapper rules: structure, types, and built-in conversions."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class ReturnToReturnsRule(Rule):
    """RETURN type (in function declaration) -> RETURNS type."""

    name = "return_to_returns"
    category = RuleCategory.PLSQL_BASIC
    priority = 10
    description = "Convert RETURN to RETURNS in function declarations"

    _PATTERN = re.compile(
        r"\bRETURN\s+(?P<type>\w+)\s+(?=(?:IS|AS)\b)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(lambda m: f"RETURNS {m.group('type')} ", sql)


class IStoASRule(Rule):
    """IS/AS in function/procedure declarations -> AS $$."""

    name = "is_to_as_dollar"
    category = RuleCategory.PLSQL_BASIC
    priority = 20
    description = "Convert IS/AS keyword to AS $$ in PL/SQL declarations"

    _PATTERN = re.compile(
        r"(CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+\w+[^;]*?)"
        r"\b(?:IS|AS)\b(?!\s*\$\$)",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            prefix = m.group(1).rstrip()
            return f"{prefix} AS $$"

        return self._PATTERN.sub(_replace, sql, count=1)


class LanguageWrapperRule(Rule):
    """Add $$ LANGUAGE plpgsql; at end of function/procedure body.

    Converts END proc_name; -> END; $$ LANGUAGE plpgsql;
    """

    name = "language_wrapper"
    category = RuleCategory.PLSQL_BASIC
    priority = 30
    description = "Add $$ LANGUAGE plpgsql wrapper at end of PL/SQL body"

    _PATTERN = re.compile(
        r"\bEND\s*(?:\w+\s*)?;\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def matches(self, sql: str) -> bool:
        # Only match if there's a CREATE FUNCTION/PROCEDURE context
        has_create = re.search(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)",
            sql,
            re.IGNORECASE,
        )
        return bool(has_create and self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # Skip if $$ LANGUAGE plpgsql; already present (e.g. from trigger body extraction)
        if "$$ LANGUAGE plpgsql;" in sql:
            return sql
        # Replace the last END; with END; $$ LANGUAGE plpgsql;
        matches = list(self._PATTERN.finditer(sql))
        if not matches:
            return sql
        last = matches[-1]
        return sql[: last.start()] + "END;\n$$ LANGUAGE plpgsql;" + sql[last.end() :]


class DBMSOutputRule(Rule):
    """DBMS_OUTPUT.PUT_LINE(...) -> RAISE NOTICE '%', ..."""

    name = "dbms_output"
    category = RuleCategory.PLSQL_BASIC
    priority = 40
    description = "Convert DBMS_OUTPUT.PUT_LINE to RAISE NOTICE"

    _PATTERN = re.compile(
        r"DBMS_OUTPUT\.PUT_LINE\s*\(\s*(?P<arg>[^)]+)\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            arg = m.group("arg").strip()
            return f"RAISE NOTICE '%', {arg}"

        return self._PATTERN.sub(_replace, sql)


class ExecuteImmediateRule(Rule):
    """EXECUTE IMMEDIATE sql -> EXECUTE sql."""

    name = "execute_immediate"
    category = RuleCategory.PLSQL_BASIC
    priority = 50
    description = "Convert EXECUTE IMMEDIATE to EXECUTE"

    _PATTERN = re.compile(r"\bEXECUTE\s+IMMEDIATE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("EXECUTE", sql)


class PLSIntegerRule(Rule):
    """PLS_INTEGER -> INTEGER, BINARY_INTEGER -> INTEGER."""

    name = "pls_integer"
    category = RuleCategory.PLSQL_BASIC
    priority = 60
    description = "Convert PLS_INTEGER and BINARY_INTEGER to INTEGER"

    _PATTERN = re.compile(r"\b(?:PLS_INTEGER|BINARY_INTEGER)\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("INTEGER", sql)


class IntoStrictRule(Rule):
    """SELECT...INTO var -> SELECT...INTO STRICT var.

    CRITICAL for correctness: without STRICT, PL/pgSQL silently returns NULL
    when no rows found instead of raising NO_DATA_FOUND.

    Must NOT add STRICT when:
    - FETCH ... INTO (cursor fetch, not SELECT)
    - BULK COLLECT INTO (array fetch)
    - SELECT with aggregate functions (COUNT, SUM, AVG, MIN, MAX) that always
      return exactly one row, making STRICT unnecessary and potentially harmful
      if combined with GROUP BY HAVING that returns 0 rows.
    """

    name = "into_strict"
    category = RuleCategory.PLSQL_BASIC
    priority = 70
    description = "Add STRICT to SELECT INTO for NO_DATA_FOUND semantics"

    _PATTERN = re.compile(
        r"\bSELECT\b(?P<cols>.+?)\bINTO\s+(?!STRICT\b)(?P<vars>\w+)",
        re.IGNORECASE | re.DOTALL,
    )

    # Aggregates that guarantee exactly one row (without GROUP BY)
    _AGGREGATE_RE = re.compile(
        r"\b(?:COUNT|SUM|AVG|MIN|MAX)\s*\(",
        re.IGNORECASE,
    )

    # BULK COLLECT INTO should be excluded
    _BULK_COLLECT_RE = re.compile(
        r"\bBULK\s+COLLECT\s+INTO\b",
        re.IGNORECASE,
    )

    # FETCH ... INTO should be excluded
    _FETCH_INTO_RE = re.compile(
        r"\bFETCH\b.+?\bINTO\b",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        # Exclude FETCH...INTO and BULK COLLECT INTO
        if self._FETCH_INTO_RE.search(sql):
            return False
        if self._BULK_COLLECT_RE.search(sql):
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # Exclude FETCH...INTO and BULK COLLECT INTO
        if self._FETCH_INTO_RE.search(sql) or self._BULK_COLLECT_RE.search(sql):
            return sql

        def _replace(m: re.Match[str]) -> str:
            cols = m.group("cols")
            var = m.group("vars")
            # Skip STRICT for aggregate-only SELECTs (they always return one row)
            if self._AGGREGATE_RE.search(cols):
                return f"SELECT{cols}INTO {var}"
            return f"SELECT{cols}INTO STRICT {var}"

        return self._PATTERN.sub(_replace, sql)


class SysRefcursorRule(Rule):
    """SYS_REFCURSOR -> REFCURSOR."""

    name = "sys_refcursor"
    category = RuleCategory.PLSQL_BASIC
    priority = 80
    description = "Convert SYS_REFCURSOR to REFCURSOR"

    _PATTERN = re.compile(r"\bSYS_REFCURSOR\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("REFCURSOR", sql)
