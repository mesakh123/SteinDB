"""Tests for cloud provider models."""

from __future__ import annotations

from steindb.cloud.models import (
    ORACLE_SERVICES,
    POSTGRESQL_SERVICES,
    CloudConnection,
    CloudMigrationPlan,
    CloudProvider,
    ManagedService,
)

# ---------------------------------------------------------------------------
# CloudProvider enum
# ---------------------------------------------------------------------------


class TestCloudProvider:
    def test_values(self) -> None:
        assert CloudProvider.AWS == "aws"
        assert CloudProvider.GCP == "gcp"
        assert CloudProvider.AZURE == "azure"
        assert CloudProvider.LOCAL == "local"

    def test_from_string(self) -> None:
        assert CloudProvider("aws") is CloudProvider.AWS


# ---------------------------------------------------------------------------
# ManagedService enum
# ---------------------------------------------------------------------------


class TestManagedService:
    def test_aws_services(self) -> None:
        assert ManagedService.RDS_ORACLE == "rds_oracle"
        assert ManagedService.RDS_POSTGRESQL == "rds_postgresql"
        assert ManagedService.AURORA_POSTGRESQL == "aurora_postgresql"

    def test_gcp_services(self) -> None:
        assert ManagedService.CLOUD_SQL_POSTGRESQL == "cloud_sql_postgresql"
        assert ManagedService.ALLOYDB == "alloydb"

    def test_azure_services(self) -> None:
        assert ManagedService.AZURE_POSTGRESQL == "azure_postgresql"
        assert ManagedService.AZURE_POSTGRESQL_FLEX == "azure_postgresql_flex"

    def test_local_services(self) -> None:
        assert ManagedService.LOCAL_ORACLE == "local_oracle"
        assert ManagedService.LOCAL_POSTGRESQL == "local_postgresql"


# ---------------------------------------------------------------------------
# Service sets
# ---------------------------------------------------------------------------


class TestServiceSets:
    def test_oracle_services(self) -> None:
        assert ManagedService.RDS_ORACLE in ORACLE_SERVICES
        assert ManagedService.LOCAL_ORACLE in ORACLE_SERVICES
        assert ManagedService.RDS_POSTGRESQL not in ORACLE_SERVICES

    def test_postgresql_services(self) -> None:
        assert ManagedService.RDS_POSTGRESQL in POSTGRESQL_SERVICES
        assert ManagedService.AURORA_POSTGRESQL in POSTGRESQL_SERVICES
        assert ManagedService.ALLOYDB in POSTGRESQL_SERVICES
        assert ManagedService.RDS_ORACLE not in POSTGRESQL_SERVICES

    def test_no_overlap(self) -> None:
        assert ORACLE_SERVICES.isdisjoint(POSTGRESQL_SERVICES)


# ---------------------------------------------------------------------------
# CloudConnection
# ---------------------------------------------------------------------------


def _make_aws_oracle() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AWS,
        service=ManagedService.RDS_ORACLE,
        host="mydb.xxxx.us-east-1.rds.amazonaws.com",
        port=1521,
        database="ORCL",
        username="admin",
        password="secret",
        region="us-east-1",
    )


def _make_aws_aurora() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.AWS,
        service=ManagedService.AURORA_POSTGRESQL,
        host="mycluster.cluster-xxxx.us-east-1.rds.amazonaws.com",
        port=5432,
        database="mydb",
        username="pgadmin",
        password="secret",
        region="us-east-1",
    )


class TestCloudConnection:
    def test_defaults(self) -> None:
        conn = _make_aws_oracle()
        assert conn.ssl_mode == "require"
        assert conn.aws_access_key == ""
        assert conn.gcp_project == ""
        assert conn.azure_subscription == ""

    def test_is_oracle(self) -> None:
        assert _make_aws_oracle().is_oracle() is True
        assert _make_aws_aurora().is_oracle() is False

    def test_is_postgresql(self) -> None:
        assert _make_aws_aurora().is_postgresql() is True
        assert _make_aws_oracle().is_postgresql() is False

    def test_local_oracle(self) -> None:
        conn = CloudConnection(
            provider=CloudProvider.LOCAL,
            service=ManagedService.LOCAL_ORACLE,
            host="localhost",
            port=1521,
            database="XE",
            username="system",
        )
        assert conn.is_oracle() is True
        assert conn.is_postgresql() is False

    def test_gcp_alloydb(self) -> None:
        conn = CloudConnection(
            provider=CloudProvider.GCP,
            service=ManagedService.ALLOYDB,
            host="10.0.0.5",
            port=5432,
            database="mydb",
            username="alloyuser",
            gcp_project="my-project",
        )
        assert conn.is_postgresql() is True
        assert conn.gcp_project == "my-project"


# ---------------------------------------------------------------------------
# CloudMigrationPlan
# ---------------------------------------------------------------------------


class TestCloudMigrationPlan:
    def test_default_warnings_empty(self) -> None:
        plan = CloudMigrationPlan(
            source=_make_aws_oracle(),
            target=_make_aws_aurora(),
            direction="o2p",
        )
        assert plan.warnings == []
        assert plan.estimated_objects == 0
        assert plan.estimated_duration_minutes == 0

    def test_with_warnings(self) -> None:
        plan = CloudMigrationPlan(
            source=_make_aws_oracle(),
            target=_make_aws_aurora(),
            direction="o2p",
            warnings=["test warning"],
        )
        assert plan.warnings == ["test warning"]

    def test_direction_field(self) -> None:
        plan = CloudMigrationPlan(
            source=_make_aws_oracle(),
            target=_make_aws_aurora(),
            direction="o2p",
        )
        assert plan.direction == "o2p"

    def test_p2o_direction(self) -> None:
        plan = CloudMigrationPlan(
            source=_make_aws_aurora(),
            target=_make_aws_oracle(),
            direction="p2o",
        )
        assert plan.direction == "p2o"
