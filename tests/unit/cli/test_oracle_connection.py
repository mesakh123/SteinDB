"""Tests for live Oracle database connection (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from steindb.cli.scanner.oracle_connection import OracleConnectionConfig, OracleScanner


class TestOracleConnectionConfig:
    def test_dsn_with_service_name(self) -> None:
        cfg = OracleConnectionConfig(host="db.example.com", port=1521, service_name="ORCL")
        assert cfg.dsn == "db.example.com:1521/ORCL"

    def test_dsn_with_sid(self) -> None:
        cfg = OracleConnectionConfig(host="db.example.com", port=1521, sid="ORCL")
        assert "SID=ORCL" in cfg.dsn
        assert "HOST=db.example.com" in cfg.dsn

    def test_dsn_raises_without_service_or_sid(self) -> None:
        cfg = OracleConnectionConfig(host="db.example.com")
        with pytest.raises(ValueError, match="service_name or sid"):
            _ = cfg.dsn

    def test_defaults(self) -> None:
        cfg = OracleConnectionConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 1521


class TestOracleScanner:
    def test_import_error_when_oracledb_missing(self) -> None:
        cfg = OracleConnectionConfig(host="x", service_name="X")
        scanner = OracleScanner(cfg)
        with (
            patch.dict("sys.modules", {"oracledb": None}),
            pytest.raises(ImportError, match="python-oracledb"),
        ):
            scanner.connect()

    def test_get_schemas(self) -> None:
        cfg = OracleConnectionConfig(host="x", service_name="X")
        scanner = OracleScanner(cfg)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter([("HR",), ("SALES",)]))
        mock_conn.cursor.return_value = mock_cursor
        scanner._connection = mock_conn
        schemas = scanner.get_schemas()
        assert schemas == ["HR", "SALES"]

    def test_get_objects(self) -> None:
        cfg = OracleConnectionConfig(host="x", service_name="X")
        scanner = OracleScanner(cfg)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter([("EMPLOYEES", "TABLE")]))
        mock_conn.cursor.return_value = mock_cursor
        scanner._connection = mock_conn
        scanner._get_ddl = MagicMock(return_value="CREATE TABLE EMPLOYEES (ID NUMBER)")
        objects = scanner.get_objects("HR")
        assert len(objects) == 1
        assert objects[0]["name"] == "EMPLOYEES"

    def test_disconnect(self) -> None:
        cfg = OracleConnectionConfig(host="x", service_name="X")
        scanner = OracleScanner(cfg)
        mock_conn = MagicMock()
        scanner._connection = mock_conn
        scanner.disconnect()
        mock_conn.close.assert_called_once()
        assert scanner._connection is None

    def test_disconnect_when_not_connected(self) -> None:
        cfg = OracleConnectionConfig(host="x", service_name="X")
        scanner = OracleScanner(cfg)
        scanner.disconnect()  # should not raise
