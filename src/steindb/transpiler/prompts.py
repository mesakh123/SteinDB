# src/steindb/transpiler/prompts.py
"""Prompt engineering for Oracle-to-PostgreSQL LLM conversion.

Strategy:
1. System prompt: expert role + conversion rules + output format
2. Few-shot examples: drawn from golden tests, matched by construct
3. User prompt: Oracle SQL + context + object metadata
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SYSTEM_PROMPT = """\
You are an expert Oracle-to-PostgreSQL migration engineer with 20 years of experience.

Your task is to convert Oracle PL/SQL and SQL code to \
native PostgreSQL syntax. Follow these rules precisely:

## Conversion Rules
1. CONNECT BY / START WITH -> WITH RECURSIVE (recursive CTE)
2. SYS_CONNECT_BY_PATH -> String concatenation in recursive CTE
3. NVL(a, b) -> COALESCE(a, b)
4. NVL2(a, b, c) -> CASE WHEN a IS NOT NULL THEN b ELSE c END
5. DECODE(expr, s1, r1, ..., default) -> CASE WHEN expr = s1 THEN r1 ... ELSE default END
6. SYSDATE / SYSTIMESTAMP -> CURRENT_TIMESTAMP
7. ROWNUM -> ROW_NUMBER() OVER() or LIMIT
8. FROM DUAL -> remove entirely
9. VARCHAR2->VARCHAR/TEXT, NUMBER->INTEGER/BIGINT/NUMERIC, DATE->TIMESTAMP, CLOB->TEXT, BLOB->BYTEA
10. :NEW/:OLD in triggers -> NEW/OLD
11. DBMS_OUTPUT.PUT_LINE -> RAISE NOTICE
12. RAISE_APPLICATION_ERROR -> RAISE EXCEPTION
13. Oracle packages -> PostgreSQL schemas with functions
14. Sequences: seq.NEXTVAL -> nextval('seq'), seq.CURRVAL -> currval('seq')
15. AUTONOMOUS_TRANSACTION -> Separate transaction via dblink or pg_background
16. BULK COLLECT ... INTO -> Array aggregation or cursor-based approach
17. FORALL -> Standard INSERT/UPDATE/DELETE with arrays

## Output Format
Return ONLY a JSON object with this exact structure:
{
  "postgresql": "<converted PostgreSQL code>",
  "confidence": <0.0-1.0 float>,
  "changes": ["list of changes made"],
  "warnings": ["potential issues requiring human review"],
  "test_hints": ["suggested test scenarios"]
}

## Quality Requirements
- Use native PostgreSQL syntax only (no Oracle compatibility extensions)
- Preserve the original logic and behavior exactly
- Add comments for non-obvious conversions
- Set confidence lower for complex/uncertain conversions
- List all warnings for anything that might behave differently
"""


@dataclass(frozen=True)
class FewShotExample:
    """A single Oracle->PostgreSQL example for few-shot prompting."""

    oracle: str
    postgresql: str
    explanation: str


# Built-in few-shot examples organized by construct
_BUILTIN_EXAMPLES: dict[str, list[FewShotExample]] = {
    "CONNECT BY": [
        FewShotExample(
            oracle=(
                "SELECT employee_id, manager_id, LEVEL as depth\n"
                "FROM employees\n"
                "START WITH manager_id IS NULL\n"
                "CONNECT BY PRIOR employee_id = manager_id"
            ),
            postgresql=(
                "WITH RECURSIVE emp_tree AS (\n"
                "  SELECT employee_id, manager_id, 1 AS depth\n"
                "  FROM employees WHERE manager_id IS NULL\n"
                "  UNION ALL\n"
                "  SELECT e.employee_id, e.manager_id, t.depth + 1\n"
                "  FROM employees e JOIN emp_tree t ON e.manager_id = t.employee_id\n"
                ")\n"
                "SELECT employee_id, manager_id, depth FROM emp_tree"
            ),
            explanation="CONNECT BY -> WITH RECURSIVE, LEVEL -> recursive depth counter",
        ),
    ],
    "DBMS_OUTPUT": [
        FewShotExample(
            oracle="DBMS_OUTPUT.PUT_LINE('Order processed: ' || v_id);",
            postgresql="RAISE NOTICE 'Order processed: %', v_id;",
            explanation="DBMS_OUTPUT.PUT_LINE -> RAISE NOTICE with % placeholder",
        ),
    ],
    "AUTONOMOUS_TRANSACTION": [
        FewShotExample(
            oracle=(
                "CREATE OR REPLACE PROCEDURE log_error(p_msg VARCHAR2) IS\n"
                "  PRAGMA AUTONOMOUS_TRANSACTION;\n"
                "BEGIN\n"
                "  INSERT INTO error_log (message, logged_at) VALUES (p_msg, SYSDATE);\n"
                "  COMMIT;\n"
                "END;"
            ),
            postgresql=(
                "CREATE OR REPLACE PROCEDURE log_error(p_msg VARCHAR)\n"
                "LANGUAGE plpgsql AS $$\n"
                "BEGIN\n"
                "  -- AUTONOMOUS_TRANSACTION: use dblink for independent transaction\n"
                "  PERFORM dblink_exec('dbname=' || current_database(),\n"
                "    'INSERT INTO error_log (message, logged_at) VALUES (' ||\n"
                "    quote_literal(p_msg) || ', CURRENT_TIMESTAMP)');\n"
                "END;\n"
                "$$;"
            ),
            explanation="AUTONOMOUS_TRANSACTION -> dblink for independent transaction commit",
        ),
    ],
    "BULK COLLECT": [
        FewShotExample(
            oracle="SELECT id BULK COLLECT INTO v_ids FROM employees WHERE dept = 10;",
            postgresql="SELECT array_agg(id) INTO v_ids FROM employees WHERE dept = 10;",
            explanation="BULK COLLECT INTO -> array_agg() or ARRAY() constructor",
        ),
    ],
}


def build_few_shot_examples(
    oracle_sql: str,
    max_examples: int = 3,
) -> list[FewShotExample]:
    """Select relevant few-shot examples based on constructs in the input SQL."""
    sql_upper = oracle_sql.upper()
    examples: list[FewShotExample] = []

    for construct, exs in _BUILTIN_EXAMPLES.items():
        if construct in sql_upper:
            examples.extend(exs[: max_examples - len(examples)])
        if len(examples) >= max_examples:
            break

    return examples[:max_examples]


def build_user_prompt(
    oracle_sql: str,
    object_name: str,
    object_type: str,
    few_shot_examples: list[FewShotExample] | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Build the user prompt with Oracle SQL, examples, and context."""
    parts: list[str] = []

    # Context section
    if context:
        parts.append("## Context")
        for key, value in context.items():
            parts.append(f"- {key}: {value}")
        parts.append("")

    # Few-shot examples
    if few_shot_examples:
        parts.append("## Examples of similar conversions")
        for i, ex in enumerate(few_shot_examples, 1):
            parts.append(f"### Example {i}")
            parts.append(f"Oracle:\n```sql\n{ex.oracle}\n```")
            parts.append(f"PostgreSQL:\n```sql\n{ex.postgresql}\n```")
            parts.append(f"Explanation: {ex.explanation}")
            parts.append("")

    # The actual conversion request
    parts.append(f"## Convert this {object_type}: {object_name}")
    parts.append(f"```sql\n{oracle_sql}\n```")
    parts.append("")
    parts.append("Return the JSON result.")

    return "\n".join(parts)
