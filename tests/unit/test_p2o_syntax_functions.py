"""Tests for P2O syntax_functions rules."""

from __future__ import annotations

from steindb.rules.p2o_syntax_functions import (
    CastNumericToToNumberRule,
    CoalesceToNVLRule,
    EncodeHexToRawtohexRule,
    OctetLengthToLengthbRule,
    PositionToInstrRule,
    StringAggToListaggRule,
    SubstringToSubstrRule,
    TildeToRegexpLikeRule,
)


class TestCoalesceToNVLRule:
    rule = CoalesceToNVLRule()

    def test_matches_two_args(self) -> None:
        assert self.rule.matches("SELECT COALESCE(name, 'Unknown') FROM emp")

    def test_matches_case_insensitive(self) -> None:
        assert self.rule.matches("SELECT coalesce(a, b) FROM t")

    def test_no_match_three_args(self) -> None:
        assert not self.rule.matches("SELECT COALESCE(a, b, c) FROM t")

    def test_no_match_inside_string(self) -> None:
        assert not self.rule.matches("SELECT 'COALESCE(a,b)' FROM t")

    def test_apply_basic(self) -> None:
        result = self.rule.apply("SELECT COALESCE(name, 'Unknown') FROM employees")
        assert "NVL(name, 'Unknown')" in result
        assert "NOTE: NVL evaluates both args" in result

    def test_apply_keeps_three_args(self) -> None:
        sql = "SELECT COALESCE(a, b, c) FROM t"
        result = self.rule.apply(sql)
        assert "COALESCE(a, b, c)" in result
        assert "NVL" not in result

    def test_apply_multiple(self) -> None:
        sql = "SELECT COALESCE(a, 0), COALESCE(b, '') FROM t"
        result = self.rule.apply(sql)
        assert "NVL(a, 0)" in result
        assert "NVL(b, '')" in result
        assert result.count("NOTE: NVL evaluates both args") == 2

    def test_preserves_string_literals(self) -> None:
        sql = "SELECT 'COALESCE(a,b)' AS label, COALESCE(x, 0) FROM t"
        result = self.rule.apply(sql)
        assert "'COALESCE(a,b)'" in result
        assert "NVL(x, 0)" in result
        assert "NOTE:" in result

    def test_apply_nvl_semantic_warning_present(self) -> None:
        """NVL evaluates both args unlike COALESCE; warning must be emitted."""
        result = self.rule.apply("SELECT COALESCE(x, y) FROM t")
        assert "NVL(x, y)" in result
        assert "NOTE: NVL evaluates both args" in result


class TestSubstringToSubstrRule:
    rule = SubstringToSubstrRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT SUBSTRING(name FROM 1 FOR 3) FROM t")

    def test_apply_from_for(self) -> None:
        result = self.rule.apply("SELECT SUBSTRING(name FROM 1 FOR 3) FROM t")
        assert "SUBSTR(name, 1, 3)" in result

    def test_apply_from_only(self) -> None:
        result = self.rule.apply("SELECT SUBSTRING(name FROM 2) FROM t")
        assert "SUBSTR(name, 2)" in result


class TestPositionToInstrRule:
    rule = PositionToInstrRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT POSITION('a' IN name) FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT POSITION('a' IN name) FROM t")
        assert "INSTR(name, 'a')" in result


class TestStringAggToListaggRule:
    rule = StringAggToListaggRule()

    def test_matches(self) -> None:
        sql = "SELECT STRING_AGG(name, ', ' ORDER BY name) FROM t"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT name FROM t")

    def test_apply(self) -> None:
        sql = "SELECT STRING_AGG(name, ', ' ORDER BY name) FROM t"
        result = self.rule.apply(sql)
        assert "LISTAGG(name, ', ') WITHIN GROUP (ORDER BY name)" in result


class TestTildeToRegexpLikeRule:
    rule = TildeToRegexpLikeRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT * FROM t WHERE col ~ '^[A-Z]'")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT * FROM t WHERE col = 'a'")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT * FROM t WHERE col ~ '^[A-Z]'")
        assert "REGEXP_LIKE(col, '^[A-Z]')" in result


class TestCastNumericToToNumberRule:
    rule = CastNumericToToNumberRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT CAST(val AS NUMERIC) FROM t")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT CAST(val AS INTEGER) FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT CAST(val AS NUMERIC) FROM t")
        assert "TO_NUMBER(val)" in result


class TestOctetLengthToLengthbRule:
    rule = OctetLengthToLengthbRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT OCTET_LENGTH(col) FROM t")

    def test_no_match_length(self) -> None:
        assert not self.rule.matches("SELECT LENGTH(col) FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT OCTET_LENGTH(col) FROM t")
        assert "LENGTHB(col)" in result


class TestEncodeHexToRawtohexRule:
    rule = EncodeHexToRawtohexRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT ENCODE(data, 'hex') FROM t")

    def test_no_match_base64(self) -> None:
        assert not self.rule.matches("SELECT ENCODE(data, 'base64') FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT ENCODE(data, 'hex') FROM t")
        assert "RAWTOHEX(data)" in result
