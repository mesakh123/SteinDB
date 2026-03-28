"""Tests for syntax_functions rules."""

from __future__ import annotations

from steindb.rules.syntax_functions import (
    DECODERule,
    INSTRRule,
    LENGTHBRule,
    LISTAGGRule,
    NVL2Rule,
    NVLRule,
    RAWTOHEXRule,
    REGEXPLIKERule,
    REGEXPSUBSTRRule,
    SUBSTRRule,
    TONUMBERRule,
)


class TestNVLRule:
    rule = NVLRule()

    def test_matches_basic(self) -> None:
        assert self.rule.matches("SELECT NVL(name, 'Unknown') FROM emp")

    def test_matches_case_insensitive(self) -> None:
        assert self.rule.matches("SELECT nvl(a, b) FROM t")

    def test_no_match_inside_string(self) -> None:
        assert not self.rule.matches("SELECT 'NVL(a,b)' FROM t")

    def test_no_match_nvl2(self) -> None:
        # NVL2 should NOT be matched by NVLRule (the regex uses \bNVL\b with parens)
        assert not self.rule.matches("SELECT NVL2(a, b, c) FROM t")

    def test_apply_basic(self) -> None:
        result = self.rule.apply("SELECT NVL(name, 'Unknown') FROM employees")
        assert result == "SELECT COALESCE(name, 'Unknown') FROM employees"

    def test_apply_multiple(self) -> None:
        sql = "SELECT NVL(a, 0), NVL(b, '') FROM t"
        result = self.rule.apply(sql)
        assert "COALESCE(a, 0)" in result
        assert "COALESCE(b, '')" in result

    def test_preserves_string_literals(self) -> None:
        sql = "SELECT 'NVL(a,b)' AS label, NVL(x, 0) FROM t"
        result = self.rule.apply(sql)
        assert "'NVL(a,b)'" in result
        assert "COALESCE(x, 0)" in result


class TestNVL2Rule:
    rule = NVL2Rule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT NVL2(comm, salary + comm, salary) FROM emp")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT name FROM emp")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT NVL2(comm, salary + comm, salary) FROM emp")
        assert "CASE WHEN comm IS NOT NULL THEN salary + comm ELSE salary END" in result

    def test_apply_preserves_rest(self) -> None:
        sql = "SELECT NVL2(email, 'Has email', 'No email') FROM employees"
        result = self.rule.apply(sql)
        assert "CASE WHEN email IS NOT NULL THEN 'Has email' ELSE 'No email' END" in result


class TestDECODERule:
    rule = DECODERule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT DECODE(status, 1, 'Active', 'Unknown') FROM t")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT status FROM t")

    def test_apply_basic(self) -> None:
        sql = "SELECT DECODE(status, 1, 'Active', 2, 'Inactive', 'Unknown') FROM t"
        result = self.rule.apply(sql)
        assert "CASE status" in result
        assert "WHEN 1 THEN 'Active'" in result
        assert "WHEN 2 THEN 'Inactive'" in result
        assert "ELSE 'Unknown'" in result
        assert "END" in result

    def test_apply_no_default(self) -> None:
        sql = "SELECT DECODE(x, 1, 'A', 2, 'B') FROM t"
        result = self.rule.apply(sql)
        assert "CASE x WHEN 1 THEN 'A' WHEN 2 THEN 'B' END" in result

    def test_apply_null_comparison(self) -> None:
        sql = "SELECT DECODE(status, NULL, 'Missing', status) FROM t"
        result = self.rule.apply(sql)
        assert "WHEN status IS NULL THEN 'Missing'" in result


class TestSUBSTRRule:
    rule = SUBSTRRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT SUBSTR(name, 1, 3) FROM t")

    def test_apply_3arg(self) -> None:
        result = self.rule.apply("SELECT SUBSTR(name, 1, 3) FROM t")
        assert "SUBSTRING(name FROM 1 FOR 3)" in result

    def test_apply_2arg(self) -> None:
        result = self.rule.apply("SELECT SUBSTR(name, 2) FROM t")
        assert "SUBSTRING(name FROM 2)" in result


class TestINSTRRule:
    rule = INSTRRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT INSTR(name, 'a') FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT INSTR(name, 'a') FROM t")
        assert "POSITION('a' IN name)" in result


class TestTONUMBERRule:
    rule = TONUMBERRule()

    def test_matches_single_arg(self) -> None:
        assert self.rule.matches("SELECT TO_NUMBER(val) FROM t")

    def test_no_match_two_arg(self) -> None:
        # 2-arg form should not be matched by the single-arg pattern
        assert not self.rule.matches("SELECT TO_NUMBER(val, '999.99') FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT TO_NUMBER(val) FROM t")
        assert "CAST(val AS NUMERIC)" in result


class TestLISTAGGRule:
    rule = LISTAGGRule()

    def test_matches(self) -> None:
        sql = "SELECT LISTAGG(name, ', ') WITHIN GROUP (ORDER BY name) FROM t"
        assert self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "SELECT LISTAGG(name, ', ') WITHIN GROUP (ORDER BY name) FROM t"
        result = self.rule.apply(sql)
        assert "STRING_AGG(name, ', ' ORDER BY name)" in result


class TestREGEXPLIKERule:
    rule = REGEXPLIKERule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT * FROM t WHERE REGEXP_LIKE(col, '^[A-Z]')")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT * FROM t WHERE REGEXP_LIKE(col, '^[A-Z]')")
        assert "col ~ '^[A-Z]'" in result


class TestREGEXPSUBSTRRule:
    rule = REGEXPSUBSTRRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT REGEXP_SUBSTR(name, '[A-Z]+') FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT REGEXP_SUBSTR(name, '[A-Z]+') FROM t")
        assert "SUBSTRING(name FROM '[A-Z]+')" in result


class TestLENGTHBRule:
    rule = LENGTHBRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT LENGTHB(col) FROM t")

    def test_no_match_length(self) -> None:
        assert not self.rule.matches("SELECT LENGTH(col) FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT LENGTHB(col) FROM t")
        assert "OCTET_LENGTH(col)" in result


class TestRAWTOHEXRule:
    rule = RAWTOHEXRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT RAWTOHEX(data) FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT RAWTOHEX(data) FROM t")
        assert "ENCODE(data, 'hex')" in result


class TestSplitArgs:
    """Tests for _split_args to cover nested parens and quote handling."""

    def test_split_args_with_nested_parens(self) -> None:
        """Cover lines 405-406, 408-409: parentheses depth tracking in _split_args."""
        from steindb.rules.syntax_functions import _split_args

        result = _split_args("a, FUNC(b, c), d")
        assert result == ["a", " FUNC(b, c)", " d"]

    def test_split_args_with_quotes(self) -> None:
        """Cover quote handling paths in _split_args."""
        from steindb.rules.syntax_functions import _split_args

        result = _split_args("'hello, world', b")
        assert result == ["'hello, world'", " b"]


class TestReplaceOutsideStringsWithStringRepl:
    """Cover line 59: _replace_outside_strings with a plain string replacement."""

    def test_string_repl(self) -> None:
        import re

        from steindb.rules.syntax_functions import _replace_outside_strings

        pattern = re.compile(r"\bFOO\b")
        result = _replace_outside_strings(pattern, "BAR", "SELECT FOO FROM t")
        assert result == "SELECT BAR FROM t"


class TestNVL2BadArgs:
    """Cover line 108: NVL2 with wrong number of args returns unchanged."""

    def test_nvl2_two_args_unchanged(self) -> None:
        rule = NVL2Rule()
        sql = "SELECT NVL2(a, b) FROM t"
        result = rule.apply(sql)
        assert "NVL2(a, b)" in result


class TestDECODEEdgeCases:
    """Cover lines 134 and 165: DECODE edge cases."""

    def test_decode_too_few_args(self) -> None:
        """Cover line 134: DECODE with fewer than 3 args returns unchanged."""
        rule = DECODERule()
        sql = "SELECT DECODE(x, 1) FROM t"
        result = rule.apply(sql)
        assert "DECODE(x, 1)" in result

    def test_decode_null_with_default(self) -> None:
        """Cover line 165/167-168: DECODE with NULL search and a default value."""
        rule = DECODERule()
        sql = "SELECT DECODE(status, NULL, 'Missing', 'A', 'Active', 'Other') FROM t"
        result = rule.apply(sql)
        assert "WHEN status IS NULL THEN 'Missing'" in result
        assert "WHEN status = 'A' THEN 'Active'" in result
        assert "ELSE 'Other'" in result
