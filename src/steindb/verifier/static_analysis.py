# src/steindb/verifier/static_analysis.py
"""Static analysis rules for detecting silent conversion errors.

These rules run on every converted PostgreSQL output (whether produced by the
Rule Engine or the LLM Transpiler) and detect patterns that are KNOWN to cause
silent bugs due to Oracle/PostgreSQL behavioral differences.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    """Issue severity levels for static analysis findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


@dataclass(frozen=True)
class StaticAnalysisIssue:
    """A single finding from a static analysis rule."""

    code: str
    name: str
    severity: Severity
    message: str
    suggestion: str
    line: int | None = None


@dataclass
class StaticAnalysisReport:
    """Aggregated report from running all static analysis rules."""

    issues: list[StaticAnalysisIssue] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.MEDIUM)

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    def by_severity(self, severity: Severity) -> list[StaticAnalysisIssue]:
        return [i for i in self.issues if i.severity == severity]


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class StaticAnalysisRule(ABC):
    """Base class for all static analysis rules."""

    code: str
    name: str
    severity: Severity

    @abstractmethod
    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        """Check the converted PostgreSQL for issues.

        Args:
            source_oracle: The original Oracle SQL.
            converted_pg: The converted PostgreSQL SQL.

        Returns:
            A list of issues found by this rule (empty if none).
        """
        ...


# ---------------------------------------------------------------------------
# SA-001: SELECT INTO without STRICT
# ---------------------------------------------------------------------------

_SA001_SELECT_INTO = re.compile(
    r"\bSELECT\b(.+?)\bINTO\b(?!\s+STRICT)\s+",
    re.IGNORECASE | re.DOTALL,
)

_AGGREGATE_FUNCTIONS = frozenset({"count", "sum", "avg", "min", "max", "array_agg", "string_agg"})


class SA001_SelectIntoWithoutStrict(StaticAnalysisRule):  # noqa: N801
    """CRITICAL: SELECT INTO missing STRICT keyword.

    Oracle raises NO_DATA_FOUND on 0 rows; PostgreSQL silently returns NULL.
    """

    code = "SA-001"
    name = "SELECT INTO without STRICT"
    severity = Severity.CRITICAL

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        for match in _SA001_SELECT_INTO.finditer(converted_pg):
            select_clause = match.group(1).lower()
            # Skip if the SELECT clause contains an aggregate function
            if any(fn in select_clause for fn in _AGGREGATE_FUNCTIONS):
                continue
            issues.append(
                StaticAnalysisIssue(
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    message=(
                        "SELECT INTO without STRICT: if zero rows are returned, "
                        "the variable will silently become NULL instead of raising "
                        "NO_DATA_FOUND as Oracle does."
                    ),
                    suggestion="Add STRICT keyword: SELECT ... INTO STRICT ...",
                )
            )
        return issues


# ---------------------------------------------------------------------------
# SA-002: Empty string equality comparison
# ---------------------------------------------------------------------------

_SA002_EMPTY_STRING = re.compile(
    r"(\w+)\s*(=|<>|!=)\s*''",
    re.IGNORECASE,
)


class SA002_EmptyStringEquality(StaticAnalysisRule):  # noqa: N801
    """CRITICAL: WHERE col = '' without NULL check.

    Oracle treats '' as NULL. PostgreSQL treats '' as a distinct empty string.
    """

    code = "SA-002"
    name = "Empty string equality without NULL check"
    severity = Severity.CRITICAL

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        for match in _SA002_EMPTY_STRING.finditer(converted_pg):
            col = match.group(1)
            op = match.group(2)
            if op == "=":
                suggestion = f"Rewrite: ({col} IS NULL OR {col} = '')"
            else:
                suggestion = f"Rewrite: ({col} IS NOT NULL AND {col} <> '')"
            issues.append(
                StaticAnalysisIssue(
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    message=(
                        f"Comparison {col} {op} '' is semantically different "
                        "between Oracle (treats '' as NULL) and PostgreSQL "
                        "(treats '' as empty string)."
                    ),
                    suggestion=suggestion,
                )
            )
        return issues


# ---------------------------------------------------------------------------
# SA-003: Concatenation with NULL risk
# ---------------------------------------------------------------------------

_SA003_CONCAT_CHAIN = re.compile(
    r"(\w+)\s*\|\|",
    re.IGNORECASE,
)

# Tokens that are clearly not nullable column references
_SA003_SAFE_PREFIXES = frozenset({"coalesce", "concat"})


class SA003_ConcatWithNull(StaticAnalysisRule):  # noqa: N801
    """HIGH: || concatenation without COALESCE.

    Oracle: 'a' || NULL || 'b' = 'ab'.
    PostgreSQL: 'a' || NULL || 'b' = NULL.
    """

    code = "SA-003"
    name = "Concatenation with potential NULL"
    severity = Severity.HIGH

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        # Only flag if the source had || (meaning this is an Oracle pattern)
        if "||" not in source_oracle:
            return issues
        for match in _SA003_CONCAT_CHAIN.finditer(converted_pg):
            operand = match.group(1).lower().strip()
            # Skip string literals (start with quote) and safe wrappers
            if operand.startswith("'") or operand in _SA003_SAFE_PREFIXES:
                continue
            # Skip if already wrapped in COALESCE by looking back
            prefix = converted_pg[: match.start()].lower()
            if prefix.rstrip().endswith("coalesce("):
                continue
            issues.append(
                StaticAnalysisIssue(
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    message=(
                        f"Column '{operand}' used in || concatenation may be NULL. "
                        "In PostgreSQL, NULL || anything = NULL (unlike Oracle)."
                    ),
                    suggestion=f"Wrap nullable operand: COALESCE({operand}, '')",
                )
            )
        return issues


# ---------------------------------------------------------------------------
# SA-004: CURRENT_TIMESTAMP in loop (returns same value)
# ---------------------------------------------------------------------------

_SA004_LOOP_PATTERN = re.compile(
    r"\b(?:FOR|WHILE)\b.*?\bLOOP\b(.*?)\bEND\s+LOOP\b",
    re.IGNORECASE | re.DOTALL,
)


class SA004_SysdateInLoop(StaticAnalysisRule):  # noqa: N801
    """HIGH: CURRENT_TIMESTAMP in loop returns transaction start time.

    Oracle SYSDATE returns wall-clock time. PostgreSQL CURRENT_TIMESTAMP
    returns the transaction start time (frozen within transaction).
    """

    code = "SA-004"
    name = "CURRENT_TIMESTAMP in loop"
    severity = Severity.HIGH

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        for match in _SA004_LOOP_PATTERN.finditer(converted_pg):
            loop_body = match.group(1)
            if re.search(r"\bCURRENT_TIMESTAMP\b", loop_body, re.IGNORECASE):
                issues.append(
                    StaticAnalysisIssue(
                        code=self.code,
                        name=self.name,
                        severity=self.severity,
                        message=(
                            "CURRENT_TIMESTAMP inside a loop returns the same "
                            "value (transaction start time). Oracle SYSDATE "
                            "advances with wall-clock time."
                        ),
                        suggestion="Use clock_timestamp() for wall-clock semantics.",
                    )
                )
        return issues


# ---------------------------------------------------------------------------
# SA-005: Implicit type cast in WHERE condition
# ---------------------------------------------------------------------------

_SA005_IMPLICIT_CAST = re.compile(
    r"(\w+)\s*=\s*'(\d+)'",
    re.IGNORECASE,
)


class SA005_ImplicitTypeCast(StaticAnalysisRule):  # noqa: N801
    """HIGH: Comparing a column to a numeric string literal.

    Oracle coerces freely. PostgreSQL may throw a type error at runtime.
    """

    code = "SA-005"
    name = "Implicit type cast in comparison"
    severity = Severity.HIGH

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        for match in _SA005_IMPLICIT_CAST.finditer(converted_pg):
            col = match.group(1)
            val = match.group(2)
            # Only flag if the original Oracle SQL also had this pattern
            if match.group(0) in source_oracle or f"{col} = '{val}'" in source_oracle:
                issues.append(
                    StaticAnalysisIssue(
                        code=self.code,
                        name=self.name,
                        severity=self.severity,
                        message=(
                            f"Column '{col}' compared to string literal '{val}' "
                            "which looks numeric. Oracle coerces implicitly; "
                            "PostgreSQL may throw a type error."
                        ),
                        suggestion=f"Use explicit CAST: {col} = CAST('{val}' AS INTEGER)",
                    )
                )
        return issues


# ---------------------------------------------------------------------------
# SA-006: TIMESTAMPTZ data loss warning
# ---------------------------------------------------------------------------

_SA006_TIMESTAMPTZ = re.compile(
    r"\bTIMESTAMPTZ\b|\bTIMESTAMP\s+WITH\s+TIME\s+ZONE\b",
    re.IGNORECASE,
)


class SA006_TimestamptzDataLoss(StaticAnalysisRule):  # noqa: N801
    """MEDIUM: TIMESTAMPTZ without timezone storage warning.

    Oracle stores the original timezone. PostgreSQL converts to UTC
    and discards the original timezone.
    """

    code = "SA-006"
    name = "TIMESTAMPTZ data loss"
    severity = Severity.MEDIUM

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        if _SA006_TIMESTAMPTZ.search(converted_pg):
            issues.append(
                StaticAnalysisIssue(
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    message=(
                        "TIMESTAMPTZ converts to UTC and discards the original "
                        "timezone. Oracle TIMESTAMP WITH TIME ZONE stores the "
                        "original timezone info."
                    ),
                    suggestion=(
                        "Add a separate column to store the original timezone "
                        "string if your application needs it."
                    ),
                )
            )
        return issues


# ---------------------------------------------------------------------------
# SA-007: Oracle remnants still present
# ---------------------------------------------------------------------------

_SA007_ORACLE_REMNANTS: list[tuple[str, re.Pattern[str]]] = [
    ("NVL", re.compile(r"\bNVL\s*\(", re.I)),
    ("NVL2", re.compile(r"\bNVL2\s*\(", re.I)),
    ("DECODE", re.compile(r"\bDECODE\s*\(", re.I)),
    ("SYSDATE", re.compile(r"\bSYSDATE\b", re.I)),
    ("VARCHAR2", re.compile(r"\bVARCHAR2\b", re.I)),
    ("NUMBER(", re.compile(r"\bNUMBER\s*\(", re.I)),
    ("ROWNUM", re.compile(r"\bROWNUM\b", re.I)),
    ("FROM DUAL", re.compile(r"\bFROM\s+DUAL\b", re.I)),
    ("CONNECT BY", re.compile(r"\bCONNECT\s+BY\b", re.I)),
]


class SA007_OracleRemnants(StaticAnalysisRule):  # noqa: N801
    """CRITICAL: Oracle syntax still present in PostgreSQL output."""

    code = "SA-007"
    name = "Oracle syntax remnant"
    severity = Severity.CRITICAL

    def check(self, source_oracle: str, converted_pg: str) -> list[StaticAnalysisIssue]:
        issues: list[StaticAnalysisIssue] = []
        for name, pattern in _SA007_ORACLE_REMNANTS:
            if pattern.search(converted_pg):
                issues.append(
                    StaticAnalysisIssue(
                        code=self.code,
                        name=self.name,
                        severity=self.severity,
                        message=f"Oracle syntax remnant detected: {name}",
                        suggestion=f"Replace Oracle-specific '{name}' with PostgreSQL equivalent.",
                    )
                )
        return issues


# ---------------------------------------------------------------------------
# Rule registry and runner
# ---------------------------------------------------------------------------

ALL_RULES: list[StaticAnalysisRule] = [
    SA001_SelectIntoWithoutStrict(),
    SA002_EmptyStringEquality(),
    SA003_ConcatWithNull(),
    SA004_SysdateInLoop(),
    SA005_ImplicitTypeCast(),
    SA006_TimestamptzDataLoss(),
    SA007_OracleRemnants(),
]


def run_static_analysis(
    source_oracle: str,
    converted_pg: str,
    rules: list[StaticAnalysisRule] | None = None,
) -> StaticAnalysisReport:
    """Run all static analysis rules on the converted PostgreSQL output.

    Args:
        source_oracle: The original Oracle SQL.
        converted_pg: The converted PostgreSQL SQL.
        rules: Optional list of rules to run (defaults to ALL_RULES).

    Returns:
        A StaticAnalysisReport with all findings.
    """
    active_rules = rules if rules is not None else ALL_RULES
    report = StaticAnalysisReport()
    for rule in active_rules:
        findings = rule.check(source_oracle, converted_pg)
        report.issues.extend(findings)
    return report
