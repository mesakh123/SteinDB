# src/steindb/verifier/warnings.py
"""Non-blocking migration warnings for Oracle-to-PostgreSQL conversions.

These warnings do NOT block the migration pipeline. They are advisory
notices about architectural differences between Oracle and PostgreSQL
that may require manual tuning or design decisions post-migration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class WarningCategory(StrEnum):
    """Categories for migration warnings."""

    DATA_TYPE = "data_type"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    CONNECTION = "connection"


@dataclass(frozen=True)
class MigrationWarning:
    """A non-blocking advisory warning about a migration concern."""

    code: str
    category: WarningCategory
    message: str
    recommendation: str


# ---------------------------------------------------------------------------
# Warning definitions
# ---------------------------------------------------------------------------

W_DATE_TO_TIMESTAMP = MigrationWarning(
    code="W001",
    category=WarningCategory.DATA_TYPE,
    message=(
        "Oracle DATE was converted to TIMESTAMP. Consider TIMESTAMP(0) "
        "if you don't need sub-second precision."
    ),
    recommendation=(
        "Review columns migrated from Oracle DATE. If your application "
        "only needs second-level precision, use TIMESTAMP(0) to match "
        "Oracle DATE semantics exactly."
    ),
)

W_TIMESTAMPTZ_LOSES_TZ = MigrationWarning(
    code="W002",
    category=WarningCategory.DATA_TYPE,
    message=(
        "Oracle TIMESTAMP WITH TIME ZONE stores timezone info. PostgreSQL "
        "TIMESTAMPTZ converts to UTC and loses original timezone."
    ),
    recommendation=(
        "If your application relies on knowing the original timezone of "
        "historical events, add a separate column to store the timezone "
        "string (e.g., 'America/New_York')."
    ),
)

W_MVCC_AUTOVACUUM = MigrationWarning(
    code="W003",
    category=WarningCategory.ARCHITECTURE,
    message=(
        "Oracle uses UNDO segments for MVCC. PostgreSQL uses tuple "
        "versioning -- ensure autovacuum is properly tuned for this workload."
    ),
    recommendation=(
        "For heavy UPDATE workloads, tune autovacuum_vacuum_scale_factor, "
        "autovacuum_vacuum_cost_delay, and autovacuum_max_workers. "
        "Monitor pg_stat_user_tables.n_dead_tup for bloat."
    ),
)

W_CONNECTION_POOLER = MigrationWarning(
    code="W004",
    category=WarningCategory.CONNECTION,
    message=(
        "Oracle handles >1000 direct connections. PostgreSQL requires "
        "PgBouncer or similar connection pooler."
    ),
    recommendation=(
        "Deploy PgBouncer or Odyssey in front of PostgreSQL. "
        "Set max_connections conservatively (100-200) and let the "
        "pooler handle connection multiplexing."
    ),
)

W_NUMERIC_JOIN_PERFORMANCE = MigrationWarning(
    code="W005",
    category=WarningCategory.PERFORMANCE,
    message=(
        "NUMERIC joins are slower than INTEGER joins in PostgreSQL. "
        "Consider using INTEGER/BIGINT for join columns."
    ),
    recommendation=(
        "Review Oracle NUMBER columns used in JOINs. If they have "
        "zero scale (e.g., NUMBER(10,0)), convert to INTEGER or BIGINT "
        "instead of NUMERIC for better join performance."
    ),
)

# All warnings, indexed by code
ALL_WARNINGS: dict[str, MigrationWarning] = {
    w.code: w
    for w in [
        W_DATE_TO_TIMESTAMP,
        W_TIMESTAMPTZ_LOSES_TZ,
        W_MVCC_AUTOVACUUM,
        W_CONNECTION_POOLER,
        W_NUMERIC_JOIN_PERFORMANCE,
    ]
}

# ---------------------------------------------------------------------------
# Detection patterns: map SQL patterns to the warnings they trigger
# ---------------------------------------------------------------------------

_WARNING_PATTERNS: list[tuple[re.Pattern[str], MigrationWarning]] = [
    # Oracle DATE -> TIMESTAMP migration
    (
        re.compile(r"\bTIMESTAMP\b(?!\s*WITH)", re.I),
        W_DATE_TO_TIMESTAMP,
    ),
    # TIMESTAMPTZ / TIMESTAMP WITH TIME ZONE
    (
        re.compile(r"\bTIMESTAMP\s+WITH\s+TIME\s+ZONE\b|\bTIMESTAMPTZ\b", re.I),
        W_TIMESTAMPTZ_LOSES_TZ,
    ),
    # NUMERIC used in join contexts (heuristic: NUMERIC in column definition
    # near JOIN or foreign key)
    (
        re.compile(r"\bNUMERIC\s*\(\s*\d+\s*,\s*0\s*\)", re.I),
        W_NUMERIC_JOIN_PERFORMANCE,
    ),
]


@dataclass
class WarningReport:
    """Collection of warnings generated for a migration job."""

    warnings: list[MigrationWarning] = field(default_factory=list)

    def add(self, warning: MigrationWarning) -> None:
        """Add a warning if not already present."""
        if warning not in self.warnings:
            self.warnings.append(warning)

    @property
    def count(self) -> int:
        return len(self.warnings)

    def by_category(self, category: WarningCategory) -> list[MigrationWarning]:
        """Filter warnings by category."""
        return [w for w in self.warnings if w.category == category]

    def format_text(self) -> str:
        """Format all warnings as human-readable text."""
        if not self.warnings:
            return "No migration warnings."
        lines = [f"Migration Warnings ({self.count}):"]
        for w in self.warnings:
            lines.append(f"  [{w.code}] ({w.category}) {w.message}")
            lines.append(f"         Recommendation: {w.recommendation}")
        return "\n".join(lines)


def analyze_sql_for_warnings(sql: str) -> WarningReport:
    """Scan converted SQL for patterns that warrant migration warnings.

    Args:
        sql: The converted PostgreSQL SQL to analyze.

    Returns:
        A WarningReport with all applicable warnings.
    """
    report = WarningReport()
    for pattern, warning in _WARNING_PATTERNS:
        if pattern.search(sql):
            report.add(warning)
    return report


def generate_architecture_warnings(
    *,
    max_connections: int = 0,
    has_heavy_updates: bool = False,
) -> WarningReport:
    """Generate architecture-level warnings based on workload characteristics.

    Args:
        max_connections: Expected maximum concurrent connections.
        has_heavy_updates: Whether the workload has heavy UPDATE patterns.

    Returns:
        A WarningReport with applicable architecture warnings.
    """
    report = WarningReport()
    if max_connections > 100:
        report.add(W_CONNECTION_POOLER)
    if has_heavy_updates:
        report.add(W_MVCC_AUTOVACUUM)
    return report
