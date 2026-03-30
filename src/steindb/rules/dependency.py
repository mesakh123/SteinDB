"""Dependency analyzer -- DAG builder with topological sort and cross-object pattern detection."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisResult:
    """Result of dependency analysis on a multi-object SQL file."""

    objects: list[str] = field(default_factory=list)
    object_types: dict[str, str] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)
    topological_order: list[str] = field(default_factory=list)
    circular: list[list[str]] = field(default_factory=list)


# Regex for CREATE statements (handles CREATE OR REPLACE)
_CREATE_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?"
    r"(?:GLOBAL\s+TEMPORARY\s+)?"
    r"(TABLE|VIEW|INDEX|SEQUENCE|TRIGGER|PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?|SYNONYM|MATERIALIZED\s+VIEW)"
    r"\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)

# Regex for REFERENCES clause (FK)
_FK_RE = re.compile(
    r"REFERENCES\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s*\(",
    re.IGNORECASE,
)

# Regex for trigger ON clause
_TRIGGER_ON_RE = re.compile(
    r"(?:BEFORE|AFTER|INSTEAD\s+OF)\s+\w+(?:\s+OR\s+\w+)*\s+ON\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)

# Regex for sequence NEXTVAL usage
_NEXTVAL_RE = re.compile(
    r"\"?(\w+)\"?\s*\.\s*NEXTVAL",
    re.IGNORECASE,
)

# Regex for FROM/JOIN table references in views
_FROM_RE = re.compile(
    r"(?:FROM|JOIN)\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)


class DependencyAnalyzer:
    """Builds a dependency DAG from multi-object SQL, performs topological sort,
    and detects cross-object patterns like sequence+trigger identity columns."""

    def analyze(self, sql: str) -> AnalysisResult:
        """Analyze SQL text and return dependency graph with topological ordering."""
        if not sql or not sql.strip():
            return AnalysisResult()

        statements = self._split_statements(sql)
        objects, object_types, stmt_map = self._parse_objects(statements)

        if not objects:
            return AnalysisResult()

        edges = self._find_edges(objects, object_types, stmt_map)
        patterns = self._detect_patterns(objects, object_types, stmt_map)
        topo_order, circular = self._topological_sort(objects, edges)

        return AnalysisResult(
            objects=objects,
            object_types=object_types,
            edges=edges,
            patterns=patterns,
            topological_order=topo_order,
            circular=circular,
        )

    def _split_statements(self, sql: str) -> list[str]:
        """Split SQL into statements, handling PL/SQL blocks delimited by /."""
        # First split on \n/\n to separate PL/SQL blocks
        blocks = re.split(r"\n/\s*\n", sql)
        statements: list[str] = []
        for block in blocks:
            # Split remaining blocks on semicolons
            parts = block.split(";")
            for part in parts:
                stripped = part.strip()
                if stripped:
                    statements.append(stripped)
        return statements

    def _parse_objects(
        self, statements: list[str]
    ) -> tuple[list[str], dict[str, str], dict[str, str]]:
        """Extract object names and types from CREATE statements."""
        objects: list[str] = []
        object_types: dict[str, str] = {}
        stmt_map: dict[str, str] = {}

        for stmt in statements:
            match = _CREATE_RE.search(stmt)
            if match:
                obj_type = match.group(1).upper()
                # Normalize MATERIALIZED VIEW
                obj_type = re.sub(r"\s+", "_", obj_type)
                obj_name = match.group(3).lower()

                if obj_name not in object_types:
                    objects.append(obj_name)
                object_types[obj_name] = obj_type
                stmt_map[obj_name] = stmt

        return objects, object_types, stmt_map

    def _find_edges(
        self,
        objects: list[str],
        object_types: dict[str, str],
        stmt_map: dict[str, str],
    ) -> list[tuple[str, str]]:
        """Find dependency edges between objects."""
        edges: list[tuple[str, str]] = []
        object_set = set(objects)

        for obj_name, stmt in stmt_map.items():
            obj_type = object_types.get(obj_name, "")

            # FK references (TABLE -> referenced TABLE)
            if obj_type == "TABLE":
                for fk_match in _FK_RE.finditer(stmt):
                    ref_table = fk_match.group(2).lower()
                    if ref_table in object_set and ref_table != obj_name:
                        # Edge: ref_table -> obj_name (parent before child)
                        edge = (ref_table, obj_name)
                        if edge not in edges:
                            edges.append(edge)

            # Trigger depends on its target table
            if obj_type == "TRIGGER":
                for trg_match in _TRIGGER_ON_RE.finditer(stmt):
                    target_table = trg_match.group(2).lower()
                    if target_table in object_set:
                        edge = (target_table, obj_name)
                        if edge not in edges:
                            edges.append(edge)

                # Trigger also depends on sequences it references
                for seq_match in _NEXTVAL_RE.finditer(stmt):
                    seq_name = seq_match.group(1).lower()
                    if seq_name in object_set:
                        edge = (seq_name, obj_name)
                        if edge not in edges:
                            edges.append(edge)

            # View depends on tables/views it references
            if obj_type == "VIEW":
                # Extract the part after AS
                as_pos = re.search(r"\bAS\b", stmt, re.IGNORECASE)
                if as_pos:
                    query_part = stmt[as_pos.end() :]
                    for from_match in _FROM_RE.finditer(query_part):
                        ref_name = from_match.group(2).lower()
                        if ref_name in object_set and ref_name != obj_name:
                            edge = (ref_name, obj_name)
                            if edge not in edges:
                                edges.append(edge)

        return edges

    def _detect_patterns(
        self,
        objects: list[str],
        object_types: dict[str, str],
        stmt_map: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Detect cross-object patterns like sequence+trigger identity columns."""
        patterns: list[dict[str, Any]] = []

        # Find triggers that use NEXTVAL (sequence + BEFORE INSERT trigger = identity)
        triggers = [o for o in objects if object_types.get(o) == "TRIGGER"]

        for trg_name in triggers:
            stmt = stmt_map.get(trg_name, "")
            stmt_upper = stmt.upper()

            # Check if it's a BEFORE INSERT trigger
            if "BEFORE" not in stmt_upper or "INSERT" not in stmt_upper:
                continue

            # Find the target table
            trg_on_match = _TRIGGER_ON_RE.search(stmt)
            if not trg_on_match:
                continue
            target_table = trg_on_match.group(2).lower()

            # Find NEXTVAL references
            seq_matches = _NEXTVAL_RE.findall(stmt)
            if not seq_matches:
                continue

            for seq_name_raw in seq_matches:
                seq_name = seq_name_raw.lower()
                patterns.append(
                    {
                        "type": "sequence_trigger_identity",
                        "table": target_table,
                        "sequence": seq_name,
                        "trigger": trg_name,
                    }
                )

        return patterns

    def _topological_sort(
        self,
        objects: list[str],
        edges: list[tuple[str, str]],
    ) -> tuple[list[str], list[list[str]]]:
        """Kahn's algorithm for topological sort with cycle detection."""
        # Build adjacency list and in-degree map
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = dict.fromkeys(objects, 0)

        for src, dst in edges:
            adj[src].append(dst)
            in_degree[dst] = in_degree.get(dst, 0) + 1

        # Start with nodes that have no incoming edges
        queue: deque[str] = deque()
        for obj in objects:
            if in_degree[obj] == 0:
                queue.append(obj)

        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Detect cycles: any nodes not in result are part of cycles
        circular: list[list[str]] = []
        remaining = [obj for obj in objects if obj not in result]
        if remaining:
            # Find cycle members - group them
            circular.append(remaining)
            # Add cycle members to result at the end (best-effort ordering)
            result.extend(remaining)

        return result, circular
