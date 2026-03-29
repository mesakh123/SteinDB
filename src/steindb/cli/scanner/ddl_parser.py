"""Parse Oracle DDL files into individual ScannedObject instances."""

from __future__ import annotations

import re
from pathlib import Path  # noqa: TCH003

from steindb.contracts import ObjectType, ScannedObject

# Patterns for extracting object type and name from CREATE statements.
# Order matters: more specific patterns first.
_OBJECT_PATTERNS: list[tuple[re.Pattern[str], ObjectType]] = [
    # MATERIALIZED VIEW must come before VIEW
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?MATERIALIZED\s+VIEW\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.MATERIALIZED_VIEW,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+BODY\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.PACKAGE_BODY,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.PACKAGE,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.PROCEDURE,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.FUNCTION,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.TRIGGER,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.VIEW,
    ),
    (
        re.compile(
            r"CREATE\s+TABLE\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.TABLE,
    ),
    (
        re.compile(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.INDEX,
    ),
    (
        re.compile(
            r"CREATE\s+SEQUENCE\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.SEQUENCE,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:PUBLIC\s+)?SYNONYM\s+"
            r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.SYNONYM,
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?TYPE\s+" r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
            re.IGNORECASE,
        ),
        ObjectType.TYPE,
    ),
]


class DDLParser:
    """Parse Oracle DDL files into individual ScannedObject instances."""

    def parse_file(self, file_path: Path) -> list[ScannedObject]:
        """Parse a single .sql file into objects."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return self.parse_string(text)

    def parse_directory(self, dir_path: Path) -> list[ScannedObject]:
        """Parse all .sql files in a directory into objects."""
        objects: list[ScannedObject] = []
        for sql_file in sorted(dir_path.glob("*.sql")):
            objects.extend(self.parse_file(sql_file))
        return objects

    def parse_string(self, sql: str) -> list[ScannedObject]:
        """Parse a SQL string into objects."""
        statements = self._split_statements(sql)
        objects: list[ScannedObject] = []
        for stmt in statements:
            classified = self._classify_object(stmt)
            if classified is not None:
                name, schema, obj_type = classified
                obj = ScannedObject(
                    name=name,
                    schema=schema,
                    object_type=obj_type,
                    source_sql=stmt.strip(),
                    line_count=stmt.strip().count("\n") + 1,
                )
                objects.append(obj)
        return objects

    def _split_statements(self, sql: str) -> list[str]:
        """Split SQL into individual statements.

        Handles:
        - Semicolon-delimited simple DDL
        - Forward-slash delimited PL/SQL blocks (``/`` on its own line)

        Strategy: first split on standalone ``/`` lines to isolate PL/SQL
        blocks, then split remaining text on ``;`` for simple DDL.  Within
        each ``/``-delimited segment we further split by ``;`` and
        reassemble any PL/SQL block that spans multiple semicolons.
        """
        results: list[str] = []

        # Split on lines that contain only `/` (with optional whitespace)
        slash_parts = re.split(r"\n\s*/\s*\n|\n\s*/\s*$", "\n" + sql)

        for part in slash_parts:
            part = part.strip()
            if not part:
                continue

            # Split on semicolons, then reassemble PL/SQL blocks.
            semi_parts = part.split(";")
            plsql_buf: list[str] = []
            in_plsql = False

            for sp in semi_parts:
                sp_stripped = sp.strip()
                if not sp_stripped:
                    if in_plsql:
                        plsql_buf.append(";")
                    continue

                if in_plsql:
                    plsql_buf.append(";")
                    plsql_buf.append(sp)
                    # Check if this semicolon-terminated segment ends the block
                    if self._ends_plsql_block(sp_stripped):
                        results.append("".join(plsql_buf).strip())
                        plsql_buf = []
                        in_plsql = False
                elif self._starts_plsql_block(sp_stripped):
                    # This starts a PL/SQL block -- if it also ends, emit it
                    if self._ends_plsql_block(sp_stripped):
                        results.append(sp_stripped)
                    else:
                        in_plsql = True
                        plsql_buf = [sp]
                else:
                    if sp_stripped:
                        results.append(sp_stripped)

            # Flush any remaining PL/SQL buffer
            if plsql_buf:
                results.append("".join(plsql_buf).strip())

        return results

    @staticmethod
    def _starts_plsql_block(text: str) -> bool:
        """Does this text look like the start of a PL/SQL block?"""
        upper = text.upper()
        return bool(
            re.search(
                r"CREATE\s+(?:OR\s+REPLACE\s+)?"
                r"(?:PROCEDURE|FUNCTION|PACKAGE\s+BODY|PACKAGE|TRIGGER)\b",
                upper,
            )
        )

    @staticmethod
    def _ends_plsql_block(text: str) -> bool:
        """Does this text end with END or END <name>?"""
        upper = text.strip().rstrip(";").strip().upper()
        # Ends with END or END <identifier>
        return bool(re.search(r"\bEND(?:\s+\w+)?\s*$", upper))

    @staticmethod
    def _classify_object(stmt: str) -> tuple[str, str, ObjectType] | None:
        """Extract (name, schema, type) from a SQL statement.

        Returns None if the statement is not a recognized CREATE statement.
        """
        for pattern, obj_type in _OBJECT_PATTERNS:
            match = pattern.search(stmt)
            if match:
                schema_raw = match.group(1)
                name_raw = match.group(2)
                schema = schema_raw.upper() if schema_raw else "PUBLIC"
                name = name_raw.upper()
                return name, schema, obj_type
        return None
