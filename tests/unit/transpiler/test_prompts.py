# tests/unit/transpiler/test_prompts.py
"""Tests for prompt engineering."""

from __future__ import annotations

from steindb.transpiler.prompts import (
    SYSTEM_PROMPT,
    FewShotExample,
    build_few_shot_examples,
    build_user_prompt,
)


class TestSystemPrompt:
    def test_contains_role(self) -> None:
        assert "Oracle-to-PostgreSQL" in SYSTEM_PROMPT

    def test_contains_output_format(self) -> None:
        assert '"postgresql"' in SYSTEM_PROMPT
        assert '"confidence"' in SYSTEM_PROMPT
        assert '"changes"' in SYSTEM_PROMPT
        assert '"warnings"' in SYSTEM_PROMPT

    def test_contains_conversion_rules(self) -> None:
        for keyword in [
            "CONNECT BY",
            "COALESCE",
            "CURRENT_TIMESTAMP",
            "CASE WHEN",
            "WITH RECURSIVE",
        ]:
            assert keyword in SYSTEM_PROMPT

    def test_structured_json_output_requested(self) -> None:
        assert "JSON" in SYSTEM_PROMPT

    def test_contains_plsql_rules(self) -> None:
        assert "RAISE NOTICE" in SYSTEM_PROMPT
        assert "RAISE EXCEPTION" in SYSTEM_PROMPT

    def test_contains_trigger_rules(self) -> None:
        assert ":NEW/:OLD" in SYSTEM_PROMPT or "NEW/OLD" in SYSTEM_PROMPT


class TestBuildUserPrompt:
    def test_includes_oracle_source(self) -> None:
        prompt = build_user_prompt(
            oracle_sql="SELECT NVL(x, 0) FROM DUAL",
            object_name="test_query",
            object_type="VIEW",
        )
        assert "NVL(x, 0)" in prompt
        assert "test_query" in prompt

    def test_includes_few_shot_examples(self) -> None:
        examples = [
            FewShotExample(
                oracle="SELECT SYSDATE FROM DUAL",
                postgresql="SELECT CURRENT_TIMESTAMP",
                explanation="SYSDATE -> CURRENT_TIMESTAMP, remove FROM DUAL",
            )
        ]
        prompt = build_user_prompt(
            oracle_sql="SELECT SYSTIMESTAMP FROM DUAL",
            object_name="q",
            object_type="VIEW",
            few_shot_examples=examples,
        )
        assert "SYSDATE" in prompt
        assert "CURRENT_TIMESTAMP" in prompt

    def test_includes_context(self) -> None:
        prompt = build_user_prompt(
            oracle_sql="SELECT get_total(100) FROM DUAL",
            object_name="q",
            object_type="VIEW",
            context={"schema": "HR", "dependencies": ["get_total"]},
        )
        assert "HR" in prompt
        assert "get_total" in prompt

    def test_no_context_no_examples(self) -> None:
        prompt = build_user_prompt(
            oracle_sql="SELECT 1 FROM DUAL",
            object_name="simple",
            object_type="VIEW",
        )
        assert "SELECT 1 FROM DUAL" in prompt
        assert "## Context" not in prompt
        assert "## Examples" not in prompt

    def test_returns_string(self) -> None:
        prompt = build_user_prompt(
            oracle_sql="SELECT 1",
            object_name="t",
            object_type="TABLE",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestBuildFewShotExamples:
    def test_selects_relevant_examples(self) -> None:
        examples = build_few_shot_examples(
            oracle_sql="SELECT * CONNECT BY PRIOR id = mgr",
            max_examples=3,
        )
        # Should return examples relevant to CONNECT BY
        assert len(examples) <= 3
        assert all(isinstance(e, FewShotExample) for e in examples)

    def test_returns_empty_for_simple_sql(self) -> None:
        examples = build_few_shot_examples(
            oracle_sql="SELECT 1 FROM DUAL",
            max_examples=3,
        )
        # May or may not return examples, but should not crash
        assert isinstance(examples, list)

    def test_dbms_output_match(self) -> None:
        examples = build_few_shot_examples(
            oracle_sql="DBMS_OUTPUT.PUT_LINE('hello')",
            max_examples=3,
        )
        assert len(examples) >= 1

    def test_autonomous_transaction_match(self) -> None:
        examples = build_few_shot_examples(
            oracle_sql="PRAGMA AUTONOMOUS_TRANSACTION;",
            max_examples=3,
        )
        assert len(examples) >= 1

    def test_bulk_collect_match(self) -> None:
        examples = build_few_shot_examples(
            oracle_sql="SELECT id BULK COLLECT INTO v_ids FROM t",
            max_examples=3,
        )
        assert len(examples) >= 1

    def test_max_examples_respected(self) -> None:
        examples = build_few_shot_examples(
            oracle_sql="CONNECT BY DBMS_OUTPUT AUTONOMOUS_TRANSACTION BULK COLLECT",
            max_examples=2,
        )
        assert len(examples) <= 2
