"""Cloud migration planner -- generates migration plans with compatibility warnings."""

from __future__ import annotations

from steindb.cloud.models import (
    CloudConnection,
    CloudMigrationPlan,
    CloudProvider,
    ManagedService,
)


class CloudMigrationPlanner:
    """Generate migration plans for cloud-to-cloud migrations.

    The planner inspects source and target connections and produces a
    ``CloudMigrationPlan`` that includes any relevant warnings about
    cross-cloud transfers, SSL, and service-specific limitations.
    """

    def plan(
        self,
        source: CloudConnection,
        target: CloudConnection,
    ) -> CloudMigrationPlan:
        """Analyse *source* and *target* and return a migration plan with warnings."""
        warnings: list[str] = []

        # Cross-cloud transfer cost warning
        if (
            source.provider != target.provider
            and source.provider != CloudProvider.LOCAL
            and target.provider != CloudProvider.LOCAL
        ):
            warnings.append("Cross-cloud migration: data transfer costs may apply")

        # SSL warnings
        if source.ssl_mode == "disable":
            warnings.append("Source connection SSL disabled — not recommended for production")
        if target.ssl_mode == "disable":
            warnings.append("Target connection SSL disabled — not recommended for production")

        # Oracle RDS limitations
        if source.service == ManagedService.RDS_ORACLE:
            warnings.append(
                "Oracle RDS does not support all PL/SQL features — check AWS RDS Oracle limitations"
            )

        # Aurora-specific
        if target.service == ManagedService.AURORA_POSTGRESQL:
            warnings.append(
                "Aurora PostgreSQL has minor differences from standard PostgreSQL — test thoroughly"
            )

        # AlloyDB-specific
        if target.service == ManagedService.ALLOYDB:
            warnings.append(
                "AlloyDB is PostgreSQL-compatible but has unique columnar engine features"
            )

        # Azure Flexible Server note
        if target.service == ManagedService.AZURE_POSTGRESQL_FLEX:
            warnings.append(
                "Azure PostgreSQL Flexible Server is recommended over "
                "Single Server for new workloads"
            )

        # Determine direction
        direction = "o2p" if source.is_oracle() else "p2o"

        return CloudMigrationPlan(
            source=source,
            target=target,
            direction=direction,
            warnings=warnings,
        )
