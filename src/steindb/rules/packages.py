# src/steindb/rules/packages.py
"""Package decomposition rules: Oracle packages -> PostgreSQL schemas."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class PackageToSchemaRule(Rule):
    """Convert Oracle package to PostgreSQL schema with extracted functions.

    Simple packages (constants and functions only) are handled deterministically.
    Complex packages (global state, init blocks, cross-procedure state) are
    forwarded to the LLM.

    Oracle:
        CREATE OR REPLACE PACKAGE pkg AS
            FUNCTION func1(...) RETURN type;
            PROCEDURE proc1(...);
        END pkg;

    PostgreSQL:
        CREATE SCHEMA IF NOT EXISTS pkg;
        -- Functions/procedures extracted from package body
    """

    name = "package_to_schema"
    category = RuleCategory.PACKAGES
    priority = 10
    description = "Decompose Oracle package into PostgreSQL schema"

    _PACKAGE_SPEC = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+(?:BODY\s+)?(?P<name>\w+)"
        r"(?:\.\w+)?\s+(?:AS|IS)\s*(?P<body>.*)\bEND\s+\w+\s*;",
        re.IGNORECASE | re.DOTALL,
    )

    # Patterns that indicate complex package -> forward to LLM
    _COMPLEX_INDICATORS = [
        re.compile(r"\bTYPE\s+\w+\s+IS\s+(?:TABLE|RECORD)\b", re.IGNORECASE),
        re.compile(r"\bPRAGMA\b", re.IGNORECASE),
        re.compile(r"\b\w+\s+\w+\s*:=\s*", re.IGNORECASE),  # package-level variables with init
    ]

    _FUNC_PATTERN = re.compile(
        r"\b(?P<kind>FUNCTION|PROCEDURE)\s+(?P<fname>\w+)\s*"
        r"\((?P<params>[^)]*)\)"
        r"(?:\s+RETURN\s+(?P<rtype>\w+))?"
        r"\s+(?:IS|AS)\s+(?P<fbody>.*?)\bEND\s+(?:\w+\s*)?;",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PACKAGE_SPEC.search(sql))

    def _is_complex(self, body: str) -> bool:
        """Check if the package body has complex constructs requiring LLM."""
        return any(pat.search(body) for pat in self._COMPLEX_INDICATORS)

    def apply(self, sql: str) -> str:
        m = self._PACKAGE_SPEC.search(sql)
        if not m:
            return sql

        pkg_name = m.group("name")
        body = m.group("body")

        if self._is_complex(body):
            return (
                f"-- FORWARD TO LLM: Package '{pkg_name}' contains complex constructs\n"
                f"-- (global state, type declarations, or pragma directives)\n"
                f"-- Original:\n"
                f"{sql}"
            )

        result_parts = [f"CREATE SCHEMA IF NOT EXISTS {pkg_name};"]

        # Extract functions and procedures from body
        for fm in self._FUNC_PATTERN.finditer(body):
            kind = fm.group("kind").upper()
            fname = fm.group("fname")
            params = fm.group("params").strip()
            rtype = fm.group("rtype")
            fbody = fm.group("fbody").strip()

            if kind == "FUNCTION" and rtype:
                result_parts.append(
                    f"\nCREATE OR REPLACE FUNCTION {pkg_name}.{fname}({params}) "
                    f"RETURNS {rtype} AS $$\n"
                    f"BEGIN\n{fbody}\nEND;\n$$ LANGUAGE plpgsql;"
                )
            else:
                result_parts.append(
                    f"\nCREATE OR REPLACE PROCEDURE {pkg_name}.{fname}({params}) "
                    f"AS $$\n"
                    f"BEGIN\n{fbody}\nEND;\n$$ LANGUAGE plpgsql;"
                )

        # If no functions were extracted, just create the schema
        if len(result_parts) == 1:
            result_parts.append(
                f"\n-- Package '{pkg_name}' spec only; implement body functions separately."
            )

        return "\n".join(result_parts)
