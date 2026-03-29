# src/steindb/rules/partitioning.py
"""Partitioning rules: Oracle partition syntax -> PostgreSQL PARTITION BY.

Regex patterns in this module are designed to avoid catastrophic backtracking.
Key techniques:
- Match column-definition blocks with a non-backtracking helper that counts
  parenthesis depth instead of using nested alternations like ``([^()]*|\\([^()]*\\))*``
  which cause exponential time on non-partition DDL.
- Use possessive-style matching via atomic-group workarounds or bounded patterns.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


def _match_balanced_parens(text: str, start: int) -> int | None:
    """Return index past the closing ')' for the '(' at *start*, or None.

    Linear-time parenthesis matcher -- avoids regex backtracking entirely
    for the column-definition / partition-list block.
    """
    if start >= len(text) or text[start] != "(":
        return None
    depth = 1
    i = start + 1
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


# Pre-compiled lightweight patterns (no nested quantifiers).
_CREATE_TABLE_PREFIX = re.compile(
    r"CREATE\s+TABLE\s+(\w+)\s*",
    re.IGNORECASE,
)


class RangePartitionRule(Rule):
    """Oracle range partition -> PG PARTITION BY RANGE.

    Oracle:
        CREATE TABLE t (...)
        PARTITION BY RANGE (col)
        (PARTITION p1 VALUES LESS THAN (100),
         PARTITION p2 VALUES LESS THAN (MAXVALUE));

    PG:
        CREATE TABLE t (...) PARTITION BY RANGE (col);
        CREATE TABLE p1 PARTITION OF t FOR VALUES FROM (MINVALUE) TO (100);
        CREATE TABLE p2 PARTITION OF t FOR VALUES FROM (100) TO (MAXVALUE);
    """

    name = "range_partition"
    category = RuleCategory.PARTITIONING
    priority = 10
    description = "Convert Oracle RANGE partitions to PG PARTITION BY RANGE"

    # Lightweight keyword check -- fast rejection for non-partition DDL.
    _QUICK_CHECK = re.compile(r"PARTITION\s+BY\s+RANGE", re.IGNORECASE)

    # Pattern for the PARTITION BY RANGE (col) clause after the CREATE TABLE block.
    _PARTITION_BY = re.compile(
        r"\s*PARTITION\s+BY\s+RANGE\s*\((?P<col>[^)]+)\)\s*",
        re.IGNORECASE,
    )

    _PART_PATTERN = re.compile(
        r"PARTITION\s+(?P<pname>\w+)\s+VALUES\s+LESS\s+THAN\s*\((?P<val>[^)]+)\)",
        re.IGNORECASE,
    )

    def _parse(self, sql: str) -> tuple[str, str, str, str] | None:
        """Parse CREATE TABLE ... PARTITION BY RANGE ... safely.

        Returns (create_block, table_name, col, parts_str) or None.
        """
        if not self._QUICK_CHECK.search(sql):
            return None

        ct = _CREATE_TABLE_PREFIX.search(sql)
        if not ct:
            return None

        table = ct.group(1)
        paren_start = sql.find("(", ct.end())
        if paren_start == -1:
            return None

        paren_end = _match_balanced_parens(sql, paren_start)
        if paren_end is None:
            return None

        create = sql[ct.start() : paren_end]
        rest = sql[paren_end:]

        pb = self._PARTITION_BY.match(rest)
        if not pb:
            return None

        col = pb.group("col").strip()
        after_pb = rest[pb.end() :]

        # Find the partition list block '( ... )'
        list_start = after_pb.find("(")
        if list_start == -1:
            return None
        list_end = _match_balanced_parens(after_pb, list_start)
        if list_end is None:
            return None

        parts_str = after_pb[list_start + 1 : list_end - 1]
        return create, table, col, parts_str

    def matches(self, sql: str) -> bool:
        return self._parse(sql) is not None

    def apply(self, sql: str) -> str:
        parsed = self._parse(sql)
        if parsed is None:
            return sql

        create, table, col, parts_str = parsed
        lines = [f"{create} PARTITION BY RANGE ({col});"]

        partitions = list(self._PART_PATTERN.finditer(parts_str))
        prev_val = "MINVALUE"

        for part in partitions:
            pname = part.group("pname")
            val = part.group("val").strip()
            upper = val if val.upper() != "MAXVALUE" else "MAXVALUE"
            lines.append(
                f"CREATE TABLE {pname} PARTITION OF {table} "
                f"FOR VALUES FROM ({prev_val}) TO ({upper});"
            )
            if val.upper() != "MAXVALUE":
                prev_val = val

        return "\n".join(lines)


class ListPartitionRule(Rule):
    """Oracle list partition -> PG PARTITION BY LIST.

    Oracle:
        PARTITION BY LIST (region)
        (PARTITION p_east VALUES ('NY','NJ'),
         PARTITION p_west VALUES ('CA','WA'));

    PG:
        CREATE TABLE t (...) PARTITION BY LIST (region);
        CREATE TABLE p_east PARTITION OF t FOR VALUES IN ('NY','NJ');
    """

    name = "list_partition"
    category = RuleCategory.PARTITIONING
    priority = 20
    description = "Convert Oracle LIST partitions to PG PARTITION BY LIST"

    _QUICK_CHECK = re.compile(r"PARTITION\s+BY\s+LIST", re.IGNORECASE)

    _PARTITION_BY = re.compile(
        r"\s*PARTITION\s+BY\s+LIST\s*\((?P<col>[^)]+)\)\s*",
        re.IGNORECASE,
    )

    _PART_PATTERN = re.compile(
        r"PARTITION\s+(?P<pname>\w+)\s+VALUES\s*\((?P<vals>[^)]+)\)",
        re.IGNORECASE,
    )

    def _parse(self, sql: str) -> tuple[str, str, str, str] | None:
        """Parse CREATE TABLE ... PARTITION BY LIST ... safely."""
        if not self._QUICK_CHECK.search(sql):
            return None

        ct = _CREATE_TABLE_PREFIX.search(sql)
        if not ct:
            return None

        table = ct.group(1)
        paren_start = sql.find("(", ct.end())
        if paren_start == -1:
            return None

        paren_end = _match_balanced_parens(sql, paren_start)
        if paren_end is None:
            return None

        create = sql[ct.start() : paren_end]
        rest = sql[paren_end:]

        pb = self._PARTITION_BY.match(rest)
        if not pb:
            return None

        col = pb.group("col").strip()
        after_pb = rest[pb.end() :]

        list_start = after_pb.find("(")
        if list_start == -1:
            return None
        list_end = _match_balanced_parens(after_pb, list_start)
        if list_end is None:
            return None

        parts_str = after_pb[list_start + 1 : list_end - 1]
        return create, table, col, parts_str

    def matches(self, sql: str) -> bool:
        return self._parse(sql) is not None

    def apply(self, sql: str) -> str:
        parsed = self._parse(sql)
        if parsed is None:
            return sql

        create, table, col, parts_str = parsed
        lines = [f"{create} PARTITION BY LIST ({col});"]

        for part in self._PART_PATTERN.finditer(parts_str):
            pname = part.group("pname")
            vals = part.group("vals").strip()
            lines.append(f"CREATE TABLE {pname} PARTITION OF {table} FOR VALUES IN ({vals});")

        return "\n".join(lines)


class HashPartitionRule(Rule):
    """Oracle hash partition -> PG PARTITION BY HASH.

    Oracle:
        PARTITION BY HASH (id) PARTITIONS 4;

    PG:
        CREATE TABLE t (...) PARTITION BY HASH (id);
        CREATE TABLE t_p0 PARTITION OF t FOR VALUES WITH (MODULUS 4, REMAINDER 0);
        ...
    """

    name = "hash_partition"
    category = RuleCategory.PARTITIONING
    priority = 30
    description = "Convert Oracle HASH partitions to PG PARTITION BY HASH"

    _QUICK_CHECK = re.compile(r"PARTITION\s+BY\s+HASH", re.IGNORECASE)

    _PARTITION_BY = re.compile(
        r"\s*PARTITION\s+BY\s+HASH\s*\((?P<col>[^)]+)\)\s*" r"PARTITIONS\s+(?P<num>\d+)\s*;?",
        re.IGNORECASE,
    )

    def _parse(self, sql: str) -> tuple[str, str, str, int] | None:
        """Parse CREATE TABLE ... PARTITION BY HASH ... safely."""
        if not self._QUICK_CHECK.search(sql):
            return None

        ct = _CREATE_TABLE_PREFIX.search(sql)
        if not ct:
            return None

        table = ct.group(1)
        paren_start = sql.find("(", ct.end())
        if paren_start == -1:
            return None

        paren_end = _match_balanced_parens(sql, paren_start)
        if paren_end is None:
            return None

        create = sql[ct.start() : paren_end]
        rest = sql[paren_end:]

        pb = self._PARTITION_BY.match(rest)
        if not pb:
            return None

        col = pb.group("col").strip()
        num = int(pb.group("num"))
        return create, table, col, num

    def matches(self, sql: str) -> bool:
        return self._parse(sql) is not None

    def apply(self, sql: str) -> str:
        parsed = self._parse(sql)
        if parsed is None:
            return sql

        create, table, col, num = parsed
        lines = [f"{create} PARTITION BY HASH ({col});"]

        for i in range(num):
            lines.append(
                f"CREATE TABLE {table}_p{i} PARTITION OF {table} "
                f"FOR VALUES WITH (MODULUS {num}, REMAINDER {i});"
            )

        return "\n".join(lines)


class SubpartitionRule(Rule):
    """Subpartition detection -> forward to LLM.

    Oracle subpartitions (composite partitioning) are too complex for
    deterministic rules.
    """

    name = "subpartition"
    category = RuleCategory.PARTITIONING
    priority = 40
    description = "Detect subpartitions and forward to LLM"

    _PATTERN = re.compile(
        r"\bSUBPARTITION\s+BY\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return (
            "-- FORWARD TO LLM: Subpartitioning (composite partitioning) detected.\n"
            "-- This requires LLM conversion due to complexity.\n"
            f"-- Original:\n{sql}"
        )
