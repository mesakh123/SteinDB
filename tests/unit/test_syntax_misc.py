"""Tests for syntax_misc rules."""

from __future__ import annotations

from steindb.rules.syntax_misc import (
    CaseFoldingWarningRule,
    DUALRemovalRule,
    MERGEIntoRule,
    MINUSRule,
    ROWNUMRule,
    SubselectAliasRule,
    USERPseudocolumnRule,
)


class TestDUALRemovalRule:
    rule = DUALRemovalRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT 1 FROM DUAL")

    def test_matches_sys_dual(self) -> None:
        assert self.rule.matches("SELECT SYSDATE FROM SYS.DUAL")

    def test_matches_case_insensitive(self) -> None:
        assert self.rule.matches("SELECT 1 FROM dual")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT 1 FROM employees")

    def test_no_match_in_string(self) -> None:
        assert not self.rule.matches("SELECT 'FROM DUAL' FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT 1 FROM DUAL")
        assert result == "SELECT 1"

    def test_apply_sys_dual(self) -> None:
        result = self.rule.apply("SELECT SYSDATE FROM SYS.DUAL")
        assert "DUAL" not in result
        assert "SYS." not in result


class TestROWNUMRule:
    rule = ROWNUMRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT * FROM employees WHERE ROWNUM <= 10")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT * FROM employees WHERE id = 1")

    def test_apply_le(self) -> None:
        result = self.rule.apply("SELECT * FROM employees WHERE ROWNUM <= 10")
        assert "LIMIT 10" in result
        assert "ROWNUM" not in result

    def test_apply_lt(self) -> None:
        result = self.rule.apply("SELECT * FROM employees WHERE ROWNUM < 5")
        assert "LIMIT 4" in result

    def test_apply_eq_1(self) -> None:
        result = self.rule.apply("SELECT * FROM employees WHERE ROWNUM = 1")
        assert "LIMIT 1" in result

    def test_apply_and_rownum(self) -> None:
        sql = "SELECT * FROM employees WHERE status = 'A' AND ROWNUM <= 5"
        result = self.rule.apply(sql)
        assert "LIMIT 5" in result
        assert "ROWNUM" not in result


class TestMINUSRule:
    rule = MINUSRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT id FROM active MINUS SELECT id FROM banned")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT id FROM active EXCEPT SELECT id FROM banned")

    def test_apply(self) -> None:
        sql = "SELECT id FROM active_users MINUS SELECT id FROM banned_users"
        result = self.rule.apply(sql)
        assert "EXCEPT" in result
        assert "MINUS" not in result


class TestSubselectAliasRule:
    rule = SubselectAliasRule()

    def test_matches_no_alias(self) -> None:
        assert self.rule.matches("SELECT * FROM (SELECT 1)")

    def test_no_match_has_alias(self) -> None:
        assert not self.rule.matches("SELECT * FROM (SELECT 1) AS subq")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT * FROM (SELECT 1)")
        assert "AS subq" in result


class TestUSERPseudocolumnRule:
    rule = USERPseudocolumnRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT USER FROM DUAL")

    def test_no_match_current_user(self) -> None:
        assert not self.rule.matches("SELECT CURRENT_USER FROM t")

    def test_no_match_create_user(self) -> None:
        assert not self.rule.matches("CREATE USER admin IDENTIFIED BY pass")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT USER FROM DUAL")
        assert "CURRENT_USER" in result

    def test_apply_in_insert(self) -> None:
        result = self.rule.apply("INSERT INTO audit_log (created_by) VALUES (USER)")
        assert "CURRENT_USER" in result


class TestHelpersMisc:
    """Tests for helper functions to cover edge cases."""

    def test_is_inside_string_returns_true(self) -> None:
        """Cover line 22: _is_inside_string returns True."""
        from steindb.rules.syntax_misc import _is_inside_string, _string_ranges

        sql = "SELECT 'ROWNUM' FROM t"
        ranges = _string_ranges(sql)
        # Position inside the string literal 'ROWNUM'
        assert _is_inside_string(9, ranges) is True

    def test_matches_outside_strings_no_match_outside(self) -> None:
        """Cover branch 29->28: pattern found only inside string, loop exhausts."""
        import re

        from steindb.rules.syntax_misc import _matches_outside_strings

        pattern = re.compile(r"\bMINUS\b")
        assert _matches_outside_strings(pattern, "SELECT 'MINUS' FROM t") is False

    def test_replace_outside_strings_skips_inside_string(self) -> None:
        """Cover branch 41->40: match inside string is skipped."""
        import re

        from steindb.rules.syntax_misc import _replace_outside_strings

        pattern = re.compile(r"\bMINUS\b")
        result = _replace_outside_strings(pattern, "EXCEPT", "SELECT 'MINUS' FROM t")
        assert result == "SELECT 'MINUS' FROM t"


class TestROWNUMAndLtRule:
    """Additional ROWNUM tests for uncovered lines 139-146 (AND ROWNUM < N)."""

    rule = ROWNUMRule()

    def test_apply_and_rownum_lt(self) -> None:
        """Cover lines 139-146: AND ROWNUM < N branch."""
        sql = "SELECT * FROM employees WHERE status = 'A' AND ROWNUM < 10"
        result = self.rule.apply(sql)
        assert "LIMIT 9" in result
        assert "ROWNUM" not in result

    def test_apply_rownum_no_simple_pattern(self) -> None:
        """Cover line 146: fallthrough when ROWNUM appears but no simple pattern matches."""
        # ROWNUM used in a complex way that doesn't match any specific pattern
        sql = "SELECT ROWNUM AS rn FROM employees"
        result = self.rule.apply(sql)
        # Should return unchanged since no WHERE/AND pattern matches
        assert "ROWNUM" in result


class TestCaseFoldingWarningRule:
    rule = CaseFoldingWarningRule()

    def test_matches_uppercase_identifier(self) -> None:
        sql = 'CREATE TABLE "MY_TABLE" (id INTEGER)'
        assert self.rule.matches(sql)

    def test_matches_multiple_uppercase_identifiers(self) -> None:
        sql = 'SELECT "EMPLOYEE_ID", "FIRST_NAME" FROM "EMPLOYEES"'
        assert self.rule.matches(sql)

    def test_no_match_lowercase(self) -> None:
        sql = 'CREATE TABLE "my_table" (id INTEGER)'
        assert not self.rule.matches(sql)

    def test_no_match_unquoted(self) -> None:
        sql = "CREATE TABLE my_table (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_adds_warning_comment(self) -> None:
        sql = 'CREATE TABLE "MY_TABLE" ("COL1" INTEGER)'
        result = self.rule.apply(sql)
        assert "WARNING: Uppercase identifiers detected" in result
        assert '"MY_TABLE"' in result
        assert '"COL1"' in result
        assert "Consider converting to lowercase" in result

    def test_apply_preserves_original_sql(self) -> None:
        sql = 'SELECT "EMPLOYEE_ID" FROM "EMPLOYEES"'
        result = self.rule.apply(sql)
        assert result.endswith(sql)

    def test_apply_deduplicates_identifiers(self) -> None:
        sql = 'SELECT "ID" FROM "T" WHERE "ID" > 0'
        result = self.rule.apply(sql)
        # "ID" should appear only once in the warning list
        warning_line = result.split("\n")[0]
        assert warning_line.count('"ID"') == 1


class TestMERGEIntoRule:
    rule = MERGEIntoRule()

    def test_matches_basic_merge(self) -> None:
        sql = (
            "MERGE INTO target t USING source s ON (t.id = s.id) "
            "WHEN MATCHED THEN UPDATE SET t.val = s.val "
            "WHEN NOT MATCHED THEN INSERT (id, val) VALUES (s.id, s.val)"
        )
        assert self.rule.matches(sql)

    def test_no_match_insert(self) -> None:
        sql = "INSERT INTO target (id, val) VALUES (1, 'x')"
        assert not self.rule.matches(sql)

    def test_no_match_update(self) -> None:
        sql = "UPDATE target SET val = 'x' WHERE id = 1"
        assert not self.rule.matches(sql)

    def test_apply_basic_merge(self) -> None:
        sql = (
            "MERGE INTO target t USING source s ON (t.id = s.id) "
            "WHEN MATCHED THEN UPDATE SET t.val = s.val "
            "WHEN NOT MATCHED THEN INSERT (id, val) VALUES (s.id, s.val)"
        )
        result = self.rule.apply(sql)
        assert "INSERT INTO" in result
        assert "ON CONFLICT" in result
        assert "DO UPDATE SET" in result
        assert "MERGE" not in result

    def test_apply_produces_valid_structure(self) -> None:
        sql = (
            "MERGE INTO employees e USING new_employees n ON (e.emp_id = n.emp_id) "
            "WHEN MATCHED THEN UPDATE SET e.name = n.name, e.salary = n.salary "
            "WHEN NOT MATCHED THEN INSERT (emp_id, name, salary) VALUES (n.emp_id, n.name, n.salary)"  # noqa: E501
        )
        result = self.rule.apply(sql)
        assert "INSERT INTO employees" in result
        assert "VALUES" in result
        assert "ON CONFLICT" in result
        assert "DO UPDATE SET" in result
