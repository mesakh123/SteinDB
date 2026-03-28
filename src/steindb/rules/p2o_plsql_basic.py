# src/steindb/rules/p2o_plsql_basic.py
"""P2O PL/pgSQL basic rules: reverse PL/pgSQL structure to PL/SQL equivalents."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory

# ---------------------------------------------------------------------------
# 1. RETURNS type -> RETURN type (in function declarations)
# ---------------------------------------------------------------------------


class ReturnsToReturnRule(Rule):
    """RETURNS type (PL/pgSQL) -> RETURN type (PL/SQL) in function declarations.

    Also detects RETURNS TABLE(...) and RETURNS SETOF which have no direct
    PL/SQL equivalent and marks them for LLM forwarding.
    """

    name = "returns_to_return"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 10
    description = "Convert RETURNS to RETURN in function declarations"

    _PATTERN = re.compile(
        r"(?<=\))\s+RETURNS\s+(?P<type>\w+)",
        re.IGNORECASE,
    )
    # Detect RETURNS TABLE(...) or RETURNS SETOF — these need LLM forwarding
    _RETURNS_TABLE_RE = re.compile(
        r"(?<=\))\s+RETURNS\s+TABLE\s*\(",
        re.IGNORECASE,
    )
    _RETURNS_SETOF_RE = re.compile(
        r"(?<=\))\s+RETURNS\s+SETOF\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # RETURNS TABLE(...) -> mark for LLM (Oracle uses pipelined functions or ref cursors)
        if self._RETURNS_TABLE_RE.search(sql):
            return (
                "/* LLM_FORWARD: RETURNS TABLE requires conversion to "
                "Oracle pipelined function or SYS_REFCURSOR. */\n" + sql
            )
        # RETURNS SETOF -> mark for LLM
        if self._RETURNS_SETOF_RE.search(sql):
            return (
                "/* LLM_FORWARD: RETURNS SETOF requires conversion to "
                "Oracle pipelined function or SYS_REFCURSOR. */\n" + sql
            )
        return self._PATTERN.sub(lambda m: f" RETURN {m.group('type')}", sql)


# ---------------------------------------------------------------------------
# 2. AS $$ ... $$ LANGUAGE plpgsql -> IS ... BEGIN...END;
# ---------------------------------------------------------------------------


class DollarQuoteToISRule(Rule):
    """Remove AS $$ wrapper and $$ LANGUAGE plpgsql; -> IS."""

    name = "dollar_quote_to_is"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 20
    description = "Convert AS $$ ... $$ LANGUAGE plpgsql to IS ... BEGIN...END"

    _AS_DOLLAR_RE = re.compile(r"\bAS\s+\$\$", re.IGNORECASE)
    _LANG_RE = re.compile(
        r"\$\$\s*LANGUAGE\s+plpgsql\s*;?",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._AS_DOLLAR_RE.search(sql))

    def apply(self, sql: str) -> str:
        result = self._AS_DOLLAR_RE.sub("IS", sql, count=1)
        result = self._LANG_RE.sub("", result)
        return result.rstrip()


# ---------------------------------------------------------------------------
# 3. RAISE NOTICE '%', msg -> DBMS_OUTPUT.PUT_LINE(msg)
# ---------------------------------------------------------------------------


class RaiseNoticeToDbmsOutputRule(Rule):
    """RAISE NOTICE '%', msg -> DBMS_OUTPUT.PUT_LINE(msg)."""

    name = "raise_notice_to_dbms_output"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 30
    description = "Convert RAISE NOTICE to DBMS_OUTPUT.PUT_LINE"

    _PATTERN = re.compile(
        r"RAISE\s+NOTICE\s+'%'\s*,\s*(?P<msg>[^;]+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            msg = m.group("msg").strip()
            return f"DBMS_OUTPUT.PUT_LINE({msg})"

        return self._PATTERN.sub(_replace, sql)


# ---------------------------------------------------------------------------
# 4. RAISE EXCEPTION '%', msg -> RAISE_APPLICATION_ERROR(-20001, msg)
# ---------------------------------------------------------------------------


class RaiseExceptionToRaiseAppErrorRule(Rule):
    """RAISE EXCEPTION '%', msg -> RAISE_APPLICATION_ERROR(-20001, msg)."""

    name = "raise_exception_to_raise_app_error"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 40
    description = "Convert RAISE EXCEPTION to RAISE_APPLICATION_ERROR"

    # Match both: RAISE EXCEPTION '%', expr  and  RAISE EXCEPTION 'literal msg'
    _PATTERN_FORMAT = re.compile(
        r"RAISE\s+EXCEPTION\s+'%'\s*,\s*(?P<msg>[^;]+)",
        re.IGNORECASE,
    )
    _PATTERN_LITERAL = re.compile(
        r"RAISE\s+EXCEPTION\s+(?P<msg>'(?:''|[^'])*')",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN_FORMAT.search(sql) or self._PATTERN_LITERAL.search(sql))

    def apply(self, sql: str) -> str:
        # First handle format-string form: RAISE EXCEPTION '%', expr
        def _replace_fmt(m: re.Match[str]) -> str:
            msg = m.group("msg").strip()
            return f"RAISE_APPLICATION_ERROR(-20001, {msg})"

        result = self._PATTERN_FORMAT.sub(_replace_fmt, sql)

        # Then handle literal form: RAISE EXCEPTION 'some message'
        def _replace_lit(m: re.Match[str]) -> str:
            msg = m.group("msg").strip()
            return f"RAISE_APPLICATION_ERROR(-20001, {msg})"

        result = self._PATTERN_LITERAL.sub(_replace_lit, result)
        return result


# ---------------------------------------------------------------------------
# 5. NEW.col -> :NEW.col (in triggers)
# ---------------------------------------------------------------------------


class NewOldToColonPrefixRule(Rule):
    """NEW.col -> :NEW.col, OLD.col -> :OLD.col (add colon prefix for triggers)."""

    name = "new_old_to_colon_prefix"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 50
    description = "Add colon prefix to NEW/OLD trigger references"

    # Match NEW.col or OLD.col that is NOT already prefixed with ':'
    _PATTERN = re.compile(
        r"(?<!:)\b(?P<ref>NEW|OLD)\.(?P<col>\w+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            ref = m.group("ref").upper()
            col = m.group("col")
            return f":{ref}.{col}"

        return self._PATTERN.sub(_replace, sql)


# ---------------------------------------------------------------------------
# 6. EXECUTE sql -> EXECUTE IMMEDIATE sql
# ---------------------------------------------------------------------------


class ExecuteToExecuteImmediateRule(Rule):
    """EXECUTE sql -> EXECUTE IMMEDIATE sql."""

    name = "execute_to_execute_immediate"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 60
    description = "Convert EXECUTE to EXECUTE IMMEDIATE"

    # Match EXECUTE that is NOT already followed by IMMEDIATE
    _PATTERN = re.compile(
        r"\bEXECUTE\b(?!\s+IMMEDIATE)\s+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("EXECUTE IMMEDIATE ", sql)


# ---------------------------------------------------------------------------
# 7. SELECT INTO STRICT -> SELECT INTO (remove STRICT)
# ---------------------------------------------------------------------------


class SelectIntoStrictRule(Rule):
    """SELECT INTO STRICT var -> SELECT INTO var (remove STRICT)."""

    name = "select_into_remove_strict"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 70
    description = "Remove STRICT from SELECT INTO (Oracle raises NO_DATA_FOUND natively)"

    _PATTERN = re.compile(r"\bINTO\s+STRICT\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("INTO", sql)


# ---------------------------------------------------------------------------
# 8. INTEGER -> NUMBER(10) (in variable declarations)
# ---------------------------------------------------------------------------


class IntegerToNumberRule(Rule):
    """INTEGER -> NUMBER(10) in variable declarations."""

    name = "integer_to_number"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 80
    description = "Convert INTEGER to NUMBER(10) in variable declarations"

    # Match INTEGER in declaration context: varname INTEGER or varname INTEGER :=
    # Must NOT match NUMBER(10) which already has it
    _PATTERN = re.compile(
        r"(\b\w+\s+)INTEGER\b(?!\s*\()",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"\1NUMBER(10)", sql)


# ---------------------------------------------------------------------------
# 9. REFCURSOR -> SYS_REFCURSOR
# ---------------------------------------------------------------------------


class RefcursorToSysRefcursorRule(Rule):
    """REFCURSOR -> SYS_REFCURSOR."""

    name = "refcursor_to_sys_refcursor"
    category = RuleCategory.P2O_PLPGSQL_BASIC
    priority = 90
    description = "Convert REFCURSOR to SYS_REFCURSOR"

    # Match REFCURSOR that is NOT already SYS_REFCURSOR
    _PATTERN = re.compile(r"(?<!\bSYS_)\bREFCURSOR\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("SYS_REFCURSOR", sql)
