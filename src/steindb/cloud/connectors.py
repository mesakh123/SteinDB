"""Cloud connection string builders for AWS, GCP, and Azure managed databases."""

from __future__ import annotations

import typing

from steindb.cloud.models import CloudConnection, ManagedService


class AWSConnector:
    """Build connection strings for AWS RDS and Aurora."""

    @staticmethod
    def rds_oracle_dsn(conn: CloudConnection) -> str:
        """Build an Oracle DSN for AWS RDS Oracle.

        Returns the ``host:port/service`` format used by oracledb / cx_Oracle.
        """
        return f"{conn.host}:{conn.port}/{conn.database}"

    @staticmethod
    def rds_postgresql_dsn(conn: CloudConnection) -> str:
        """Build a PostgreSQL DSN for AWS RDS PostgreSQL."""
        return (
            f"postgresql://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
            f"?sslmode={conn.ssl_mode}"
        )

    @staticmethod
    def aurora_dsn(conn: CloudConnection) -> str:
        """Build a PostgreSQL DSN for AWS Aurora PostgreSQL."""
        return (
            f"postgresql://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
            f"?sslmode={conn.ssl_mode}"
        )


class GCPConnector:
    """Build connection strings for GCP Cloud SQL and AlloyDB."""

    @staticmethod
    def cloud_sql_dsn(conn: CloudConnection) -> str:
        """Build a PostgreSQL DSN for GCP Cloud SQL PostgreSQL.

        Works with both direct connections and Cloud SQL Proxy.
        """
        return (
            f"postgresql://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
            f"?sslmode={conn.ssl_mode}"
        )

    @staticmethod
    def alloydb_dsn(conn: CloudConnection) -> str:
        """Build a PostgreSQL DSN for GCP AlloyDB."""
        return (
            f"postgresql://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
            f"?sslmode={conn.ssl_mode}"
        )


class AzureConnector:
    """Build connection strings for Azure Database for PostgreSQL."""

    @staticmethod
    def azure_postgresql_dsn(conn: CloudConnection) -> str:
        """Build a PostgreSQL DSN for Azure Database for PostgreSQL.

        Azure requires the ``username@hostname`` format for the user field.
        """
        short_host = conn.host.split(".")[0]
        user = f"{conn.username}@{short_host}"
        return (
            f"postgresql://{user}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
            f"?sslmode={conn.ssl_mode}"
        )


def build_dsn(conn: CloudConnection) -> str:
    """Automatically select the correct connector and build a DSN string.

    Raises ``ValueError`` if the service is not recognised.
    """
    service_dsn_map: dict[ManagedService, typing.Callable[[CloudConnection], str]] = {
        ManagedService.RDS_ORACLE: AWSConnector.rds_oracle_dsn,
        ManagedService.RDS_POSTGRESQL: AWSConnector.rds_postgresql_dsn,
        ManagedService.AURORA_POSTGRESQL: AWSConnector.aurora_dsn,
        ManagedService.CLOUD_SQL_POSTGRESQL: GCPConnector.cloud_sql_dsn,
        ManagedService.ALLOYDB: GCPConnector.alloydb_dsn,
        ManagedService.AZURE_POSTGRESQL: AzureConnector.azure_postgresql_dsn,
        ManagedService.AZURE_POSTGRESQL_FLEX: AzureConnector.azure_postgresql_dsn,
    }

    builder = service_dsn_map.get(conn.service)
    if builder is None:
        msg = f"No DSN builder for service: {conn.service}"
        raise ValueError(msg)
    return builder(conn)
