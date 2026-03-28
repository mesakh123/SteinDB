"""Cross-agent Pydantic contract models for SteinDB."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MigrationDirection(StrEnum):
    """Direction of migration between Oracle and PostgreSQL."""

    ORACLE_TO_PG = "oracle_to_pg"
    PG_TO_ORACLE = "pg_to_oracle"


class SourceDatabase(StrEnum):
    """Source database type for scanned objects."""

    ORACLE = "oracle"
    POSTGRESQL = "postgresql"


class ObjectType(StrEnum):
    """Database object types (shared across Oracle and PostgreSQL)."""

    TABLE = "TABLE"
    VIEW = "VIEW"
    INDEX = "INDEX"
    SEQUENCE = "SEQUENCE"
    TRIGGER = "TRIGGER"
    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"
    PACKAGE = "PACKAGE"
    PACKAGE_BODY = "PACKAGE_BODY"
    TYPE = "TYPE"
    SYNONYM = "SYNONYM"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW"


class VerifyStatus(StrEnum):
    """Verification traffic-light status."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ScannedObject(BaseModel):
    """A database object discovered by the Scanner agent.

    Supports both Oracle and PostgreSQL source databases for bidirectional
    migration.
    """

    name: str
    schema: str  # noqa: A003 — database schema name, intentional
    object_type: ObjectType
    source_sql: str = Field(min_length=1)
    line_count: int
    source_database: SourceDatabase = SourceDatabase.ORACLE
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    """Output of the Scanner agent for a complete scan job."""

    job_id: str
    customer_id: str
    objects: list[ScannedObject]
    total_objects: int
    scan_duration_seconds: float
    direction: MigrationDirection = MigrationDirection.ORACLE_TO_PG


class ConvertedObject(BaseModel):
    """An object successfully converted by the Rule Engine."""

    name: str
    schema: str  # noqa: A003 — database schema name, intentional
    object_type: ObjectType
    source_sql: str
    target_sql: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: str
    rules_applied: list[str]


class ForwardedObject(BaseModel):
    """An object forwarded to the LLM Transpiler by the Rule Engine."""

    name: str
    schema: str  # noqa: A003 — database schema name, intentional
    object_type: ObjectType
    source_sql: str
    forward_reason: str


class RuleOutput(BaseModel):
    """Output of the Rule Engine agent."""

    job_id: str
    customer_id: str
    converted: list[ConvertedObject]
    forwarded: list[ForwardedObject]
    rules_converted_count: int
    forwarded_to_llm_count: int
    direction: MigrationDirection = MigrationDirection.ORACLE_TO_PG


class TranspileResult(BaseModel):
    """Output of the LLM Transpiler agent for a single object.

    For O2P direction, ``postgresql`` holds the target SQL.
    For P2O direction, ``oracle`` holds the target SQL.
    """

    postgresql: str = Field(min_length=1)
    oracle: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    changes: list[str]
    warnings: list[str]
    test_hints: list[str]
    direction: MigrationDirection = MigrationDirection.ORACLE_TO_PG

    @property
    def target_sql(self) -> str:
        """Return the target SQL based on migration direction."""
        if self.direction == MigrationDirection.PG_TO_ORACLE:
            return self.oracle or ""
        return self.postgresql


class Issue(BaseModel):
    """A single verification issue."""

    code: str
    message: str
    severity: str
    line: int | None = None


class VerifyResult(BaseModel):
    """Output of the Verifier agent for a single object."""

    object_name: str
    object_type: str
    status: VerifyStatus
    confidence: float = Field(ge=0.0, le=1.0)
    parse_valid: bool
    explain_valid: bool
    issues: list[Issue]
    llm_confidence: float | None = None
    complexity_score: float | None = None


class GoldenTestCase(BaseModel):
    """A golden test case pairing Oracle input with expected PostgreSQL output.

    Used for Oracle-to-PostgreSQL (O2P) tests. For bidirectional tests that
    support both directions, use BidirectionalTestCase instead.
    """

    name: str
    category: str
    oracle: str
    expected_postgresql: str | None = None
    complexity: int = Field(default=1, ge=1, le=15)
    constructs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    test_data: dict[str, Any] | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


class BidirectionalTestCase(BaseModel):
    """A bidirectional golden test case supporting both O2P and P2O directions.

    Uses direction-agnostic ``source`` and ``expected`` fields instead of
    ``oracle`` / ``expected_postgresql``, making it suitable for tests in
    either migration direction.
    """

    name: str
    category: str
    direction: MigrationDirection
    source: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    complexity: int = Field(default=1, ge=1, le=15)
    constructs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    test_data: dict[str, Any] | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
