"""Dependency analysis -- build a graph between Oracle objects."""

from __future__ import annotations

import re
from collections import defaultdict, deque

from steindb.contracts import ObjectType, ScannedObject


class DependencyGraph:
    """Directed graph of object dependencies."""

    def __init__(self) -> None:
        self.edges: dict[str, set[str]] = defaultdict(set)  # object -> depends_on
        self._nodes: set[str] = set()

    def add_node(self, name: str) -> None:
        """Register a node (even if it has no edges)."""
        self._nodes.add(name)

    def add_dependency(self, obj: str, depends_on: str) -> None:
        """Record that *obj* depends on *depends_on*."""
        self._nodes.add(obj)
        self._nodes.add(depends_on)
        if obj != depends_on:
            self.edges[obj].add(depends_on)

    @property
    def nodes(self) -> set[str]:
        return set(self._nodes)

    def get_dependencies(self, obj: str) -> set[str]:
        """Return the set of objects that *obj* directly depends on."""
        return set(self.edges.get(obj, set()))

    def topological_sort(self) -> list[str]:
        """Return nodes in dependency order (dependencies first).

        Uses Kahn's algorithm. If cycles exist, the remaining nodes
        are appended in arbitrary order (no crash).
        """
        in_degree: dict[str, int] = dict.fromkeys(self._nodes, 0)
        for obj, deps in self.edges.items():
            in_degree[obj] = in_degree.get(obj, 0) + len(deps)
            for dep in deps:
                in_degree.setdefault(dep, 0)

        queue: deque[str] = deque(sorted(n for n, d in in_degree.items() if d == 0))
        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for obj, deps in self.edges.items():
                if node in deps:
                    in_degree[obj] -= 1
                    if in_degree[obj] == 0:
                        queue.append(obj)

        remaining = sorted(n for n in self._nodes if n not in set(result))
        result.extend(remaining)
        return result

    def detect_cycles(self) -> list[list[str]]:
        """Detect cycles using DFS. Returns list of cycles found."""
        WHITE, GRAY, BLACK = 0, 1, 2  # noqa: N806
        color: dict[str, int] = dict.fromkeys(self._nodes, WHITE)
        parent: dict[str, str | None] = dict.fromkeys(self._nodes)
        cycles: list[list[str]] = []

        def dfs(u: str) -> None:
            color[u] = GRAY
            for v in self.edges.get(u, set()):
                if v not in color:
                    continue
                if color[v] == GRAY:
                    cycle = [v, u]
                    node = u
                    while parent.get(node) is not None and parent[node] != v:
                        node = parent[node]  # type: ignore[assignment]
                        cycle.append(node)
                    cycles.append(cycle)
                elif color[v] == WHITE:
                    parent[v] = u
                    dfs(v)
            color[u] = BLACK

        for node in sorted(self._nodes):
            if color[node] == WHITE:
                dfs(node)

        return cycles


# Regex patterns for extracting dependencies
_FK_PATTERN = re.compile(r'REFERENCES\s+(?:"?(\w+)"?\.)?"?(\w+)"?', re.IGNORECASE)

_FROM_PATTERN = re.compile(r'\bFROM\s+(?:"?(\w+)"?\.)?"?(\w+)"?', re.IGNORECASE)

_JOIN_PATTERN = re.compile(r'\bJOIN\s+(?:"?(\w+)"?\.)?"?(\w+)"?', re.IGNORECASE)

_TRIGGER_ON_PATTERN = re.compile(r'\bON\s+(?:"?(\w+)"?\.)?"?(\w+)"?', re.IGNORECASE)

_SYNONYM_FOR_PATTERN = re.compile(r'\bFOR\s+(?:"?(\w+)"?\.)?"?(\w+)"?', re.IGNORECASE)

# SQL keywords / noise that should not be treated as table names
_NOISE_WORDS = frozenset(
    {
        "DUAL",
        "DELETE",
        "UPDATE",
        "INSERT",
        "SET",
        "WHERE",
        "AND",
        "OR",
        "NOT",
        "NULL",
        "INTO",
        "VALUES",
        "SELECT",
        "AS",
        "IS",
        "IN",
        "ON",
        "BEGIN",
        "END",
        "EACH",
        "ROW",
        "BEFORE",
        "AFTER",
        "FOR",
        "LOOP",
        "IF",
        "THEN",
        "ELSE",
        "ELSIF",
        "RETURN",
        "DECLARE",
        "EXCEPTION",
        "WHEN",
        "OTHERS",
        "RAISE",
        "COMMIT",
        "ROLLBACK",
    }
)


def _qualified(schema: str | None, name: str) -> str:
    if schema:
        return f"{schema.upper()}.{name.upper()}"
    return name.upper()


def _extract_refs(pattern: re.Pattern[str], sql: str, *, skip_noise: bool = True) -> set[str]:
    refs: set[str] = set()
    for m in pattern.finditer(sql):
        schema_raw = m.group(1)
        name_raw = m.group(2)
        if skip_noise and name_raw.upper() in _NOISE_WORDS:
            continue
        refs.add(_qualified(schema_raw, name_raw))
    return refs


def build_dependency_graph(objects: list[ScannedObject]) -> DependencyGraph:
    """Analyze SQL to extract dependencies between objects."""
    graph = DependencyGraph()

    obj_key_map: dict[str, str] = {}
    for obj in objects:
        qname = f"{obj.schema}.{obj.name}"
        graph.add_node(qname)
        obj_key_map[obj.name] = qname
        obj_key_map[qname] = qname

    for obj in objects:
        qname = f"{obj.schema}.{obj.name}"
        sql = obj.source_sql.upper()
        refs: set[str] = set()

        if obj.object_type == ObjectType.TABLE:
            refs |= _extract_refs(_FK_PATTERN, sql)

        elif obj.object_type in (ObjectType.VIEW, ObjectType.MATERIALIZED_VIEW):
            refs |= _extract_refs(_FROM_PATTERN, sql)
            refs |= _extract_refs(_JOIN_PATTERN, sql)

        elif obj.object_type == ObjectType.TRIGGER:
            refs |= _extract_refs(_TRIGGER_ON_PATTERN, sql)

        elif obj.object_type == ObjectType.SYNONYM:
            refs |= _extract_refs(_SYNONYM_FOR_PATTERN, sql)

        elif obj.object_type in (
            ObjectType.PROCEDURE,
            ObjectType.FUNCTION,
            ObjectType.PACKAGE,
            ObjectType.PACKAGE_BODY,
        ):
            refs |= _extract_refs(_FROM_PATTERN, sql)
            refs |= _extract_refs(_JOIN_PATTERN, sql)

        for ref in refs:
            resolved = obj_key_map.get(ref)
            if resolved and resolved != qname:
                graph.add_dependency(qname, resolved)

    return graph
