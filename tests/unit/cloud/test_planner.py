"""Tests for cloud migration planner."""

from __future__ import annotations

from steindb.cloud.models import CloudConnection, CloudProvider, ManagedService
from steindb.cloud.planner import CloudMigrationPlanner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aws_oracle(**overrides: object) -> CloudConnection:
    defaults: dict[str, object] = {
        "provider": CloudProvider.AWS,
        "service": ManagedService.RDS_ORACLE,
        "host": "mydb.xxxx.us-east-1.rds.amazonaws.com",
        "port": 1521,
        "database": "ORCL",
        "username": "admin",
    }
    defaults.update(overrides)
    return CloudConnection(**defaults)  # type: ignore[arg-type]


def _aws_aurora(**overrides: object) -> CloudConnection:
    defaults: dict[str, object] = {
        "provider": CloudProvider.AWS,
        "service": ManagedService.AURORA_POSTGRESQL,
        "host": "cluster.xxxx.us-east-1.rds.amazonaws.com",
        "port": 5432,
        "database": "mydb",
        "username": "pgadmin",
    }
    defaults.update(overrides)
    return CloudConnection(**defaults)  # type: ignore[arg-type]


def _gcp_alloydb(**overrides: object) -> CloudConnection:
    defaults: dict[str, object] = {
        "provider": CloudProvider.GCP,
        "service": ManagedService.ALLOYDB,
        "host": "10.0.0.5",
        "port": 5432,
        "database": "mydb",
        "username": "alloyuser",
    }
    defaults.update(overrides)
    return CloudConnection(**defaults)  # type: ignore[arg-type]


def _azure_flex(**overrides: object) -> CloudConnection:
    defaults: dict[str, object] = {
        "provider": CloudProvider.AZURE,
        "service": ManagedService.AZURE_POSTGRESQL_FLEX,
        "host": "myflex.postgres.database.azure.com",
        "port": 5432,
        "database": "flexdb",
        "username": "flexadmin",
    }
    defaults.update(overrides)
    return CloudConnection(**defaults)  # type: ignore[arg-type]


def _local_oracle() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.LOCAL,
        service=ManagedService.LOCAL_ORACLE,
        host="localhost",
        port=1521,
        database="XE",
        username="system",
    )


def _local_pg() -> CloudConnection:
    return CloudConnection(
        provider=CloudProvider.LOCAL,
        service=ManagedService.LOCAL_POSTGRESQL,
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

planner = CloudMigrationPlanner()


class TestDirection:
    def test_oracle_to_pg_is_o2p(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert plan.direction == "o2p"

    def test_pg_to_oracle_is_p2o(self) -> None:
        plan = planner.plan(_aws_aurora(), _aws_oracle())
        assert plan.direction == "p2o"

    def test_local_oracle_to_aurora(self) -> None:
        plan = planner.plan(_local_oracle(), _aws_aurora())
        assert plan.direction == "o2p"


class TestCrossCloudWarning:
    def test_aws_to_gcp_warns(self) -> None:
        plan = planner.plan(_aws_oracle(), _gcp_alloydb())
        assert any("Cross-cloud" in w for w in plan.warnings)

    def test_aws_to_aws_no_cross_cloud_warning(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert not any("Cross-cloud" in w for w in plan.warnings)

    def test_local_to_cloud_no_cross_cloud_warning(self) -> None:
        plan = planner.plan(_local_oracle(), _aws_aurora())
        assert not any("Cross-cloud" in w for w in plan.warnings)


class TestSSLWarnings:
    def test_source_ssl_disabled(self) -> None:
        plan = planner.plan(_aws_oracle(ssl_mode="disable"), _aws_aurora())
        assert any("Source connection SSL disabled" in w for w in plan.warnings)

    def test_target_ssl_disabled(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora(ssl_mode="disable"))
        assert any("Target connection SSL disabled" in w for w in plan.warnings)

    def test_ssl_require_no_warning(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert not any("SSL disabled" in w for w in plan.warnings)


class TestServiceWarnings:
    def test_rds_oracle_warning(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert any("Oracle RDS" in w for w in plan.warnings)

    def test_aurora_target_warning(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert any("Aurora PostgreSQL" in w for w in plan.warnings)

    def test_alloydb_target_warning(self) -> None:
        plan = planner.plan(_aws_oracle(), _gcp_alloydb())
        assert any("AlloyDB" in w for w in plan.warnings)

    def test_azure_flex_target_warning(self) -> None:
        plan = planner.plan(_aws_oracle(), _azure_flex())
        assert any("Flexible Server" in w for w in plan.warnings)

    def test_local_pg_no_service_warning(self) -> None:
        plan = planner.plan(_local_oracle(), _local_pg())
        # Local has no service-specific warnings
        assert not any("Aurora" in w for w in plan.warnings)
        assert not any("AlloyDB" in w for w in plan.warnings)


class TestPlanDefaults:
    def test_estimated_objects_zero(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert plan.estimated_objects == 0

    def test_estimated_duration_zero(self) -> None:
        plan = planner.plan(_aws_oracle(), _aws_aurora())
        assert plan.estimated_duration_minutes == 0

    def test_source_and_target_set(self) -> None:
        src = _aws_oracle()
        tgt = _aws_aurora()
        plan = planner.plan(src, tgt)
        assert plan.source is src
        assert plan.target is tgt
