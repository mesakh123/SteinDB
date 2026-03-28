"""24-factor Oracle-to-PostgreSQL complexity scoring engine.

Each Oracle-specific construct gets a weight based on how difficult
it is to convert to PostgreSQL. The total is normalized to a 1-10 scale.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from steindb.contracts import ScannedObject

COMPLEXITY_FACTORS: dict[str, float] = {
    # Hierarchical queries
    "CONNECT BY": 3.0,
    # Transaction control
    "AUTONOMOUS_TRANSACTION": 4.0,
    # DBMS package calls (generic)
    "DBMS_": 2.0,
    # MODEL clause (spreadsheet-style queries)
    "MODEL": 5.0,
    # XML handling
    "XMLTYPE": 3.0,
    # Cursor types
    "REF CURSOR": 2.0,
    # Bulk operations
    "BULK COLLECT": 1.0,
    "FORALL": 1.0,
    # Pipelined functions
    "PIPE ROW": 3.0,
    # Session context
    "SYS_CONTEXT": 2.0,
    # Legacy pagination
    "ROWNUM": 1.0,
    # Legacy conditionals
    "DECODE": 1.0,
    "NVL2": 1.0,
    # Locking
    "DBMS_LOCK": 3.0,
    # File I/O
    "UTL_FILE": 3.0,
    # Scheduler
    "DBMS_SCHEDULER": 2.5,
    # Advanced Queuing
    "DBMS_AQ": 4.0,
    # Temp tables
    "GLOBAL TEMPORARY": 2.0,
    # Materialized views
    "MATERIALIZED VIEW": 1.5,
    # Bitmap indexes
    "BITMAP INDEX": 2.0,
    # Clusters
    "CLUSTER": 2.5,
    # Result cache
    "RESULT_CACHE": 1.5,
    # Parallel execution
    "PARALLEL": 1.0,
    # Flashback queries
    "FLASHBACK": 3.0,
}

# Precompile patterns for performance — longest patterns first so e.g.
# "DBMS_LOCK" is matched before the generic "DBMS_".
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(re.escape(pattern), re.IGNORECASE), weight)
    for pattern, weight in sorted(COMPLEXITY_FACTORS.items(), key=lambda x: -len(x[0]))
]


def score_complexity(source_code: str | None) -> float:
    """Score Oracle source code complexity on a 0-10 scale.

    Returns 0.0 for None or empty strings.
    """
    if not source_code:
        return 0.0

    total = 0.0
    for pattern, weight in _COMPILED_PATTERNS:
        count = len(pattern.findall(source_code))
        total += min(count * weight, 10.0)  # Cap per-pattern contribution

    # The raw total is already on a reasonable scale (each factor contributes
    # its weight, and most objects will trigger a few factors). Cap at 10.
    return min(total, 10.0)


class ComplexityScorer:
    """Wrapper around score_complexity for object-level scoring."""

    def score(self, obj: ScannedObject) -> tuple[float, list[str]]:
        """Return (score 1-10, list of detected factors).

        Score is clamped to [0, 10].
        """
        source = obj.source_sql
        if not source:
            return 0.0, []

        detected: list[str] = []
        for pattern, _weight in _COMPILED_PATTERNS:
            if pattern.search(source):
                detected.append(pattern.pattern.replace("\\", ""))

        return score_complexity(source), detected
