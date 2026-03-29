"""Cloud provider models for managed database connections and migration plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CloudProvider(StrEnum):
    """Supported cloud providers."""

    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    LOCAL = "local"


class ManagedService(StrEnum):
    """Supported managed database services."""

    # AWS
    RDS_ORACLE = "rds_oracle"
    RDS_POSTGRESQL = "rds_postgresql"
    AURORA_POSTGRESQL = "aurora_postgresql"
    # GCP
    CLOUD_SQL_POSTGRESQL = "cloud_sql_postgresql"
    ALLOYDB = "alloydb"
    # Azure
    AZURE_POSTGRESQL = "azure_postgresql"
    AZURE_POSTGRESQL_FLEX = "azure_postgresql_flex"
    # Local
    LOCAL_ORACLE = "local_oracle"
    LOCAL_POSTGRESQL = "local_postgresql"


#: Services that are Oracle-based (source for O2P migrations).
ORACLE_SERVICES: frozenset[ManagedService] = frozenset(
    {ManagedService.RDS_ORACLE, ManagedService.LOCAL_ORACLE}
)

#: Services that are PostgreSQL-based (source for P2O migrations).
POSTGRESQL_SERVICES: frozenset[ManagedService] = frozenset(
    {
        ManagedService.RDS_POSTGRESQL,
        ManagedService.AURORA_POSTGRESQL,
        ManagedService.CLOUD_SQL_POSTGRESQL,
        ManagedService.ALLOYDB,
        ManagedService.AZURE_POSTGRESQL,
        ManagedService.AZURE_POSTGRESQL_FLEX,
        ManagedService.LOCAL_POSTGRESQL,
    }
)


@dataclass
class CloudConnection:
    """Connection details for a cloud-managed database instance."""

    provider: CloudProvider
    service: ManagedService
    host: str
    port: int
    database: str
    username: str
    password: str = ""
    ssl_mode: str = "require"
    region: str = ""
    # AWS-specific
    aws_access_key: str = ""
    aws_secret_key: str = ""
    rds_instance_id: str = ""
    # GCP-specific
    gcp_project: str = ""
    gcp_instance: str = ""
    # Azure-specific
    azure_subscription: str = ""
    azure_resource_group: str = ""

    def is_oracle(self) -> bool:
        """Return True if this connection targets an Oracle service."""
        return self.service in ORACLE_SERVICES

    def is_postgresql(self) -> bool:
        """Return True if this connection targets a PostgreSQL service."""
        return self.service in POSTGRESQL_SERVICES


@dataclass
class CloudMigrationPlan:
    """A migration plan between two cloud database connections."""

    source: CloudConnection
    target: CloudConnection
    direction: str  # "o2p" or "p2o"
    estimated_objects: int = 0
    estimated_duration_minutes: int = 0
    warnings: list[str] = field(default_factory=list)
