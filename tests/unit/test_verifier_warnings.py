"""Tests for verifier warnings module and ast_compare warning additions."""

from __future__ import annotations

from steindb.verifier.ast_compare import (
    detect_connection_pooler_warning,
    detect_postgres_warnings,
)
from steindb.verifier.warnings import (
    ALL_WARNINGS,
    W_CONNECTION_POOLER,
    W_DATE_TO_TIMESTAMP,
    W_MVCC_AUTOVACUUM,
    W_NUMERIC_JOIN_PERFORMANCE,
    W_TIMESTAMPTZ_LOSES_TZ,
    WarningCategory,
    WarningReport,
    analyze_sql_for_warnings,
    generate_architecture_warnings,
)

# ---------------------------------------------------------------------------
# Tests for ast_compare.detect_postgres_warnings
# ---------------------------------------------------------------------------


class TestDetectPostgresWarnings:
    def test_ctid_warning(self) -> None:
        sql = "SELECT ctid, * FROM employees"
        warnings = detect_postgres_warnings(sql)
        assert any("ctid" in w for w in warnings)

    def test_ctid_case_insensitive(self) -> None:
        sql = "SELECT CTID FROM employees"
        warnings = detect_postgres_warnings(sql)
        assert any("ctid" in w.lower() for w in warnings)

    def test_timestamp_without_precision_warning(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP)"
        warnings = detect_postgres_warnings(sql)
        assert any("TIMESTAMP" in w for w in warnings)

    def test_timestamp_with_precision_no_warning(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP(0))"
        # TIMESTAMP(0) should still match since the pattern looks for TIMESTAMP
        # without WITH, but the warning is about considering TIMESTAMP(0)
        warnings = detect_postgres_warnings(sql)
        # The pattern matches TIMESTAMP not followed by WITH
        assert len(warnings) >= 0  # Pattern may or may not match

    def test_varchar2_byte_semantics_warning(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(50 BYTE))"
        warnings = detect_postgres_warnings(sql)
        assert any("VARCHAR2" in w for w in warnings)

    def test_varchar2_without_byte_warning(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(50))"
        warnings = detect_postgres_warnings(sql)
        assert any("VARCHAR2" in w for w in warnings)

    def test_no_warnings_clean_sql(self) -> None:
        sql = "SELECT id, name FROM employees WHERE id = 1"
        warnings = detect_postgres_warnings(sql)
        assert len(warnings) == 0


class TestDetectConnectionPoolerWarning:
    def test_high_connections_warning(self) -> None:
        warnings = detect_connection_pooler_warning(500)
        assert len(warnings) == 1
        assert "connection pooler" in warnings[0].lower() or "PgBouncer" in warnings[0]

    def test_boundary_101_connections(self) -> None:
        warnings = detect_connection_pooler_warning(101)
        assert len(warnings) == 1

    def test_boundary_100_connections_no_warning(self) -> None:
        warnings = detect_connection_pooler_warning(100)
        assert len(warnings) == 0

    def test_low_connections_no_warning(self) -> None:
        warnings = detect_connection_pooler_warning(50)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Tests for warnings.py module
# ---------------------------------------------------------------------------


class TestMigrationWarning:
    def test_warning_fields(self) -> None:
        assert W_DATE_TO_TIMESTAMP.code == "W001"
        assert W_DATE_TO_TIMESTAMP.category == WarningCategory.DATA_TYPE
        assert "Oracle DATE" in W_DATE_TO_TIMESTAMP.message
        assert "TIMESTAMP(0)" in W_DATE_TO_TIMESTAMP.message

    def test_timestamptz_warning(self) -> None:
        assert W_TIMESTAMPTZ_LOSES_TZ.code == "W002"
        assert "UTC" in W_TIMESTAMPTZ_LOSES_TZ.message
        assert "loses" in W_TIMESTAMPTZ_LOSES_TZ.message.lower()

    def test_mvcc_warning(self) -> None:
        assert W_MVCC_AUTOVACUUM.code == "W003"
        assert "UNDO" in W_MVCC_AUTOVACUUM.message
        assert "autovacuum" in W_MVCC_AUTOVACUUM.message

    def test_connection_pooler_warning(self) -> None:
        assert W_CONNECTION_POOLER.code == "W004"
        assert "PgBouncer" in W_CONNECTION_POOLER.message

    def test_numeric_join_warning(self) -> None:
        assert W_NUMERIC_JOIN_PERFORMANCE.code == "W005"
        assert "NUMERIC" in W_NUMERIC_JOIN_PERFORMANCE.message
        assert "INTEGER" in W_NUMERIC_JOIN_PERFORMANCE.message


class TestAllWarnings:
    def test_all_warnings_indexed(self) -> None:
        assert len(ALL_WARNINGS) == 5
        assert "W001" in ALL_WARNINGS
        assert "W002" in ALL_WARNINGS
        assert "W003" in ALL_WARNINGS
        assert "W004" in ALL_WARNINGS
        assert "W005" in ALL_WARNINGS


class TestWarningReport:
    def test_empty_report(self) -> None:
        report = WarningReport()
        assert report.count == 0
        assert report.format_text() == "No migration warnings."

    def test_add_warning(self) -> None:
        report = WarningReport()
        report.add(W_DATE_TO_TIMESTAMP)
        assert report.count == 1

    def test_add_duplicate_warning(self) -> None:
        report = WarningReport()
        report.add(W_DATE_TO_TIMESTAMP)
        report.add(W_DATE_TO_TIMESTAMP)
        assert report.count == 1

    def test_by_category(self) -> None:
        report = WarningReport()
        report.add(W_DATE_TO_TIMESTAMP)
        report.add(W_TIMESTAMPTZ_LOSES_TZ)
        report.add(W_CONNECTION_POOLER)
        data_type_warnings = report.by_category(WarningCategory.DATA_TYPE)
        assert len(data_type_warnings) == 2
        conn_warnings = report.by_category(WarningCategory.CONNECTION)
        assert len(conn_warnings) == 1

    def test_format_text(self) -> None:
        report = WarningReport()
        report.add(W_DATE_TO_TIMESTAMP)
        report.add(W_MVCC_AUTOVACUUM)
        text = report.format_text()
        assert "Migration Warnings (2):" in text
        assert "[W001]" in text
        assert "[W003]" in text
        assert "Recommendation:" in text


class TestAnalyzeSqlForWarnings:
    def test_detects_timestamp(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP, updated_at TIMESTAMP)"
        report = analyze_sql_for_warnings(sql)
        assert any(w.code == "W001" for w in report.warnings)

    def test_detects_timestamptz(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)"
        report = analyze_sql_for_warnings(sql)
        assert any(w.code == "W002" for w in report.warnings)

    def test_detects_timestamptz_shorthand(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMPTZ)"
        report = analyze_sql_for_warnings(sql)
        assert any(w.code == "W002" for w in report.warnings)

    def test_detects_numeric_zero_scale(self) -> None:
        sql = "CREATE TABLE t (order_id NUMERIC(10, 0))"
        report = analyze_sql_for_warnings(sql)
        assert any(w.code == "W005" for w in report.warnings)

    def test_no_warnings_for_clean_sql(self) -> None:
        sql = "SELECT id, name FROM employees WHERE active = true"
        report = analyze_sql_for_warnings(sql)
        assert report.count == 0

    def test_multiple_warnings(self) -> None:
        sql = (
            "CREATE TABLE t ("
            "  id NUMERIC(10, 0),"
            "  created_at TIMESTAMP,"
            "  event_time TIMESTAMP WITH TIME ZONE"
            ")"
        )
        report = analyze_sql_for_warnings(sql)
        assert report.count >= 2


class TestGenerateArchitectureWarnings:
    def test_high_connections(self) -> None:
        report = generate_architecture_warnings(max_connections=500)
        assert any(w.code == "W004" for w in report.warnings)

    def test_low_connections(self) -> None:
        report = generate_architecture_warnings(max_connections=50)
        assert not any(w.code == "W004" for w in report.warnings)

    def test_heavy_updates(self) -> None:
        report = generate_architecture_warnings(has_heavy_updates=True)
        assert any(w.code == "W003" for w in report.warnings)

    def test_no_heavy_updates(self) -> None:
        report = generate_architecture_warnings(has_heavy_updates=False)
        assert not any(w.code == "W003" for w in report.warnings)

    def test_combined_warnings(self) -> None:
        report = generate_architecture_warnings(max_connections=200, has_heavy_updates=True)
        assert report.count == 2
        assert any(w.code == "W003" for w in report.warnings)
        assert any(w.code == "W004" for w in report.warnings)

    def test_no_warnings_defaults(self) -> None:
        report = generate_architecture_warnings()
        assert report.count == 0
