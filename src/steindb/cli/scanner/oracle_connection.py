"""Live Oracle database connection for schema scanning.

Requires: pip install steindb[oracle]  (oracledb package)
Uses thin mode -- no Oracle Client installation needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OracleConnectionConfig:
    """Configuration for connecting to an Oracle database."""

    host: str = "localhost"
    port: int = 1521
    service_name: str | None = None
    sid: str | None = None
    user: str = ""
    password: str = ""

    @property
    def dsn(self) -> str:
        if self.service_name:
            return f"{self.host}:{self.port}/{self.service_name}"
        elif self.sid:
            return (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
                f"(HOST={self.host})(PORT={self.port}))"
                f"(CONNECT_DATA=(SID={self.sid})))"
            )
        raise ValueError("Either service_name or sid must be provided")


class OracleScanner:
    """Scan a live Oracle database for schema objects.

    Uses python-oracledb in thin mode (no Oracle Client needed).
    """

    SCANNABLE_TYPES = (
        "TABLE",
        "VIEW",
        "INDEX",
        "SEQUENCE",
        "TRIGGER",
        "PROCEDURE",
        "FUNCTION",
        "PACKAGE",
        "PACKAGE BODY",
        "SYNONYM",
        "MATERIALIZED VIEW",
        "TYPE",
    )

    def __init__(self, config: OracleConnectionConfig) -> None:
        self.config = config
        self._connection: Any = None

    def connect(self) -> None:
        try:
            import oracledb
        except ImportError as err:
            raise ImportError(
                "python-oracledb required for live Oracle connections. "
                "Install with: pip install steindb[oracle]"
            ) from err
        self._connection = oracledb.connect(
            user=self.config.user,
            password=self.config.password,
            dsn=self.config.dsn,
        )

    def disconnect(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None

    def get_schemas(self) -> list[str]:
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT DISTINCT owner FROM all_objects "
            "WHERE owner NOT IN ('SYS','SYSTEM','DBSNMP','OUTLN') "
            "ORDER BY owner"
        )
        return [row[0] for row in cursor]

    def get_objects(self, schema: str) -> list[dict[str, Any]]:
        cursor = self._connection.cursor()
        type_list = ",".join(f"'{t}'" for t in self.SCANNABLE_TYPES)
        cursor.execute(
            f"SELECT object_name, object_type FROM all_objects "
            f"WHERE owner = :schema AND object_type IN ({type_list}) "
            f"ORDER BY object_type, object_name",
            schema=schema.upper(),
        )
        objects: list[dict[str, Any]] = []
        for name, obj_type in cursor:
            ddl = self._get_ddl(schema, name, obj_type)
            objects.append(
                {
                    "name": name,
                    "schema": schema,
                    "object_type": obj_type,
                    "source_sql": ddl,
                }
            )
        return objects

    def _get_ddl(self, schema: str, name: str, obj_type: str) -> str:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "SELECT DBMS_METADATA.GET_DDL(:t, :n, :s) FROM DUAL",
                t=obj_type,
                n=name,
                s=schema.upper(),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else ""
        except Exception:
            if obj_type in ("PROCEDURE", "FUNCTION", "PACKAGE", "PACKAGE BODY", "TRIGGER", "TYPE"):
                return self._get_source(schema, name, obj_type)
            return f"-- DDL extraction failed for {schema}.{name} ({obj_type})"

    def _get_source(self, schema: str, name: str, obj_type: str) -> str:
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT text FROM all_source "
            "WHERE owner = :s AND name = :n AND type = :t ORDER BY line",
            s=schema.upper(),
            n=name.upper(),
            t=obj_type.upper(),
        )
        return "".join(row[0] for row in cursor)
