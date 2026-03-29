"""Tests for cloud CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from steindb.cli.main import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------


class TestProvidersCommand:
    def test_providers_lists_services(self) -> None:
        result = runner.invoke(app, ["cloud", "providers"])
        assert result.exit_code == 0
        assert "rds_oracle" in result.output
        assert "aurora_postgresql" in result.output
        assert "alloydb" in result.output
        assert "azure_postgresql" in result.output


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


class TestConnectCommand:
    def test_connect_aws_rds_postgresql(self) -> None:
        result = runner.invoke(
            app,
            [
                "cloud",
                "connect",
                "--provider",
                "aws",
                "--service",
                "rds_postgresql",
                "--host",
                "mydb.us-east-1.rds.amazonaws.com",
                "--port",
                "5432",
                "--database",
                "mydb",
                "--username",
                "admin",
            ],
        )
        assert result.exit_code == 0
        assert "postgresql://" in result.output

    def test_connect_invalid_provider(self) -> None:
        result = runner.invoke(
            app,
            [
                "cloud",
                "connect",
                "--provider",
                "invalid",
                "--service",
                "rds_postgresql",
                "--host",
                "host",
            ],
        )
        assert result.exit_code == 1

    def test_connect_invalid_service(self) -> None:
        result = runner.invoke(
            app,
            [
                "cloud",
                "connect",
                "--provider",
                "aws",
                "--service",
                "nonexistent_service",
                "--host",
                "host",
            ],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


_SOURCE_YAML = """\
provider: aws
service: rds_oracle
host: mydb.xxxx.us-east-1.rds.amazonaws.com
port: 1521
database: ORCL
username: admin
ssl_mode: require
region: us-east-1
"""

_TARGET_YAML = """\
provider: aws
service: aurora_postgresql
host: cluster.xxxx.us-east-1.rds.amazonaws.com
port: 5432
database: mydb
username: pgadmin
ssl_mode: require
region: us-east-1
"""


class TestPlanCommand:
    def test_plan_aws_oracle_to_aurora(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        tgt = tmp_path / "target.yml"
        src.write_text(_SOURCE_YAML)
        tgt.write_text(_TARGET_YAML)

        result = runner.invoke(
            app,
            ["cloud", "plan", "--source", str(src), "--target", str(tgt)],
        )
        assert result.exit_code == 0
        assert "O2P" in result.output
        assert "Aurora" in result.output or "aurora" in result.output.lower()

    def test_plan_missing_source(self, tmp_path: Path) -> None:
        tgt = tmp_path / "target.yml"
        tgt.write_text(_TARGET_YAML)

        result = runner.invoke(
            app,
            [
                "cloud",
                "plan",
                "--source",
                str(tmp_path / "nope.yml"),
                "--target",
                str(tgt),
            ],
        )
        assert result.exit_code == 1

    def test_plan_missing_target(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        src.write_text(_SOURCE_YAML)

        result = runner.invoke(
            app,
            [
                "cloud",
                "plan",
                "--source",
                str(src),
                "--target",
                str(tmp_path / "nope.yml"),
            ],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# migrate (dry-run)
# ---------------------------------------------------------------------------


class TestMigrateCommand:
    def test_migrate_dry_run(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        tgt = tmp_path / "target.yml"
        src.write_text(_SOURCE_YAML)
        tgt.write_text(_TARGET_YAML)

        result = runner.invoke(
            app,
            [
                "cloud",
                "migrate",
                "--source-config",
                str(src),
                "--target-config",
                str(tgt),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output or "dry run" in result.output.lower()

    def test_migrate_not_implemented(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        tgt = tmp_path / "target.yml"
        src.write_text(_SOURCE_YAML)
        tgt.write_text(_TARGET_YAML)

        result = runner.invoke(
            app,
            [
                "cloud",
                "migrate",
                "--source-config",
                str(src),
                "--target-config",
                str(tgt),
            ],
        )
        assert result.exit_code == 0
        assert "not yet implemented" in result.output.lower()
