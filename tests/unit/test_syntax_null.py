"""Tests for syntax_null rules."""

from __future__ import annotations

from steindb.rules.syntax_null import ConcatNullSafeRule, EmptyStringComparisonRule


class TestConcatNullSafeRule:
    rule = ConcatNullSafeRule()

    def test_matches_column_concat(self) -> None:
        assert self.rule.matches("SELECT col1 || col2 FROM t")

    def test_matches_mixed_literal_column(self) -> None:
        assert self.rule.matches("SELECT first_name || ' ' || last_name FROM emp")

    def test_no_match_no_concat(self) -> None:
        assert not self.rule.matches("SELECT col1, col2 FROM t")

    def test_apply_two_columns(self) -> None:
        result = self.rule.apply("SELECT col1 || col2 FROM t")
        assert "concat(col1, col2)" in result
        assert "||" not in result

    def test_apply_chain_with_literals(self) -> None:
        result = self.rule.apply("SELECT first_name || ' ' || last_name FROM employees")
        assert "concat(first_name, ' ', last_name)" in result

    def test_apply_preserves_pure_literal_concat(self) -> None:
        # Two pure string literals — no column, leave as-is
        sql = "SELECT 'hello' || 'world' FROM t"
        result = self.rule.apply(sql)
        # Pure literals have no column reference, so should stay as ||
        assert "||" in result


class TestEmptyStringComparisonRule:
    rule = EmptyStringComparisonRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT * FROM employees WHERE name = ''")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT * FROM employees WHERE name = 'John'")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT * FROM employees WHERE name = ''")
        assert "(name = '' OR name IS NULL)" in result

    def test_apply_with_alias(self) -> None:
        result = self.rule.apply("SELECT * FROM t WHERE t.col = ''")
        assert "(t.col = '' OR t.col IS NULL)" in result


class TestHelpers:
    """Tests for helper functions to cover edge cases and branches."""

    def test_is_inside_string_returns_true(self) -> None:
        """Cover line 26: _is_inside_string returns True when pos is inside a string."""
        from steindb.rules.syntax_null import _is_inside_string, _string_ranges

        sql = "SELECT 'hello world' FROM t"
        ranges = _string_ranges(sql)
        # Position inside the string literal
        assert _is_inside_string(8, ranges) is True

    def test_replace_outside_strings_with_string_repl(self) -> None:
        """Cover line 49: _replace_outside_strings with a string (not callable) replacement."""
        import re

        from steindb.rules.syntax_null import _replace_outside_strings

        pattern = re.compile(r"\bFOO\b")
        result = _replace_outside_strings(pattern, "BAR", "SELECT FOO FROM t")
        assert result == "SELECT BAR FROM t"

    def test_has_column_concat_no_columns(self) -> None:
        """Cover line 97 (continue) and 108 (return False):
        _has_column_concat with no || at all returns False."""
        from steindb.rules.syntax_null import _has_column_concat

        # No || operator at all — should return False
        assert _has_column_concat("SELECT col1 FROM t") is False

    def test_matches_outside_strings_all_inside(self) -> None:
        """Cover branch where all matches are inside strings (line 33->32 exit)."""
        import re

        from steindb.rules.syntax_null import _matches_outside_strings

        pattern = re.compile(r"\|\|")
        # || only appears inside a string literal
        assert _matches_outside_strings(pattern, "SELECT 'a || b' FROM t") is False

    def test_concat_no_match_pure_string_concat(self) -> None:
        """ConcatNullSafeRule does not match when || is only inside string literals."""
        from steindb.rules.syntax_null import ConcatNullSafeRule

        rule = ConcatNullSafeRule()
        assert not rule.matches("SELECT 'a || b' FROM t")

    def test_has_column_concat_single_segment(self) -> None:
        """Cover line 97: continue when a non-literal part has fewer than 2 concat segments."""
        from steindb.rules.syntax_null import _has_column_concat

        # No || at all
        assert _has_column_concat("SELECT col1, col2 FROM t") is False

    def test_replace_outside_strings_inside_string_skipped(self) -> None:
        """Cover branch: match inside string is skipped by _replace_outside_strings."""
        import re

        from steindb.rules.syntax_null import _replace_outside_strings

        pattern = re.compile(r"FOO")
        # FOO inside the string should not be replaced
        result = _replace_outside_strings(pattern, "BAR", "SELECT 'FOO' FROM t")
        assert result == "SELECT 'FOO' FROM t"
