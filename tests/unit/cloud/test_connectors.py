"""Tests for cloud connection string builders."""

from __future__ import annotations

import pytest
from steindb.cloud.connectors import (
    AWSConnector,
    AzureConnector,
    GCPConnector,
    build_dsn,
)
from steindb.cloud.models import CloudConnection, CloudProvider, ManagedService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _aws_oracle() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AWS,
        service=ManagedService.RDS_ORACLE,
        host="mydb.xxxx.us-east-1.rds.amazonaws.com",
        port=1521,
        database="ORCL",
        username="admin",
        password="secret",
    )


def _aws_pg() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AWS,
        service=ManagedService.RDS_POSTGRESQL,
        host="mydb.xxxx.us-east-1.rds.amazonaws.com",
        port=5432,
        database="mydb",
        username="pgadmin",
        password="s3cret",
        ssl_mode="require",
    )


def _aws_aurora() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AWS,
        service=ManagedService.AURORA_POSTGRESQL,
        host="cluster.xxxx.us-east-1.rds.amazonaws.com",
        port=5432,
        database="mydb",
        username="pgadmin",
        password="s3cret",
    )


def _gcp_cloudsql() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.GCP,
        service=ManagedService.CLOUD_SQL_POSTGRESQL,
        host="10.0.0.5",
        port=5432,
        database="mydb",
        username="gcpuser",
        password="pass",
        ssl_mode="verify-ca",
    )


def _gcp_alloydb() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.GCP,
        service=ManagedService.ALLOYDB,
        host="10.0.0.6",
        port=5432,
        database="alloydb",
        username="alloyuser",
        password="pass",
    )


def _azure_pg() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AZURE,
        service=ManagedService.AZURE_POSTGRESQL,
        host="myserver.postgres.database.azure.com",
        port=5432,
        database="mydb",
        username="adminuser",
        password="P@ss",
    )


def _azure_flex() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AZURE,
        service=ManagedService.AZURE_POSTGRESQL_FLEX,
        host="myflex.postgres.database.azure.com",
        port=5432,
        database="flexdb",
        username="flexadmin",
        password="P@ss",
    )


# ---------------------------------------------------------------------------
# AWS
# ---------------------------------------------------------------------------


class TestAWSConnector:
    def test_rds_oracle_dsn(self) -> None:
        dsn = AWSConnector.rds_oracle_dsn(_aws_oracle())
        assert dsn == "mydb.xxxx.us-east-1.rds.amazonaws.com:1521/ORCL"

    def test_rds_postgresql_dsn(self) -> None:
        dsn = AWSConnector.rds_postgresql_dsn(_aws_pg())
        assert dsn.startswith("postgresql://")
        assert "pgadmin:s3cret@" in dsn
        assert "sslmode=require" in dsn

    def test_aurora_dsn(self) -> None:
        dsn = AWSConnector.aurora_dsn(_aws_aurora())
        assert dsn.startswith("postgresql://")
        assert "cluster.xxxx" in dsn


# ---------------------------------------------------------------------------
# GCP
# ---------------------------------------------------------------------------


class TestGCPConnector:
    def test_cloud_sql_dsn(self) -> None:
        dsn = GCPConnector.cloud_sql_dsn(_gcp_cloudsql())
        assert "gcpuser:pass@10.0.0.5:5432/mydb" in dsn
        assert "sslmode=verify-ca" in dsn

    def test_alloydb_dsn(self) -> None:
        dsn = GCPConnector.alloydb_dsn(_gcp_alloydb())
        assert "alloyuser:pass@10.0.0.6:5432/alloydb" in dsn


# ---------------------------------------------------------------------------
# Azure
# ---------------------------------------------------------------------------


class TestAzureConnector:
    def test_azure_postgresql_dsn_username_format(self) -> None:
        dsn = AzureConnector.azure_postgresql_dsn(_azure_pg())
        # Azure format: username@short_host
        assert "adminuser@myserver:" in dsn
        assert "myserver.postgres.database.azure.com" in dsn

    def test_azure_flex_dsn(self) -> None:
        dsn = AzureConnector.azure_postgresql_dsn(_azure_flex())
        assert "flexadmin@myflex:" in dsn


# ---------------------------------------------------------------------------
# build_dsn dispatcher
# ---------------------------------------------------------------------------


class TestBuildDsn:
    def test_rds_oracle(self) -> None:
        dsn = build_dsn(_aws_oracle())
        assert "1521/ORCL" in dsn

    def test_rds_postgresql(self) -> None:
        dsn = build_dsn(_aws_pg())
        assert dsn.startswith("postgresql://")

    def test_aurora(self) -> None:
        dsn = build_dsn(_aws_aurora())
        assert dsn.startswith("postgresql://")

    def test_cloud_sql(self) -> None:
        dsn = build_dsn(_gcp_cloudsql())
        assert dsn.startswith("postgresql://")

    def test_alloydb(self) -> None:
        dsn = build_dsn(_gcp_alloydb())
        assert dsn.startswith("postgresql://")

    def test_azure_pg(self) -> None:
        dsn = build_dsn(_azure_pg())
        assert "adminuser@myserver" in dsn

    def test_azure_flex(self) -> None:
        dsn = build_dsn(_azure_flex())
        assert dsn.startswith("postgresql://")

    def test_local_oracle_raises(self) -> None:
        conn = CloudConnection(
            provider=CloudProvider.LOCAL,
            service=ManagedService.LOCAL_ORACLE,
            host="localhost",
            port=1521,
            database="XE",
            username="system",
        )
        with pytest.raises(ValueError, match="No DSN builder"):
            build_dsn(conn)

    def test_local_postgresql_raises(self) -> None:
        conn = CloudConnection(
            provider=CloudProvider.LOCAL,
            service=ManagedService.LOCAL_POSTGRESQL,
            host="localhost",
            port=5432,
            database="mydb",
            username="postgres",
        )
        with pytest.raises(ValueError, match="No DSN builder"):
            build_dsn(conn)
