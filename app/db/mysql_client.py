import json
import re
from datetime import datetime
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from app.config.settings import Settings

VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MySQLClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._validate_identifiers()

    def _column_mappings(self) -> list[tuple[str, str]]:
        s = self.settings
        return [
            (s.mysql_id_column, "id"),
            (s.mysql_material_id_column, "material_id"),
            (s.mysql_tenant_id_column, "tenant_id"),
            (s.mysql_vector_column, "vector"),
            (s.mysql_embedding_model_column, "embedding_model"),
            (s.mysql_dimension_column, "dimension"),
            (s.mysql_content_hash_column, "content_hash"),
            (s.mysql_uid_column, "uid"),
            (s.mysql_tag_column, "tag"),
            (s.mysql_create_time_column, "create_time"),
            (s.mysql_update_time_column, "update_time"),
        ]

    def _validate_identifiers(self) -> None:
        for column, _alias in self._column_mappings():
            if not VALID_IDENTIFIER.match(column):
                raise ValueError(f"Invalid SQL identifier: {column}")

    def _select_clause(self) -> str:
        parts = [f"`{col}` AS `{alias}`" for col, alias in self._column_mappings()]
        return ", ".join(parts)

    def _connect(self):
        return pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            database=self.settings.mysql_database,
            charset="utf8mb4",
            cursorclass=DictCursor,
        )

    def fetch_full_batch(self, offset: int, limit: int) -> list[dict[str, Any]]:
        query = (
            f"SELECT {self._select_clause()} "
            f"FROM `{self.settings.mysql_table}` "
            f"ORDER BY `{self.settings.mysql_id_column}` ASC LIMIT %s OFFSET %s"
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (limit, offset))
                rows = cursor.fetchall()
        return [self._normalize_row(row) for row in rows]

    def fetch_incremental_batch(self, last_id: int | None, limit: int) -> list[dict[str, Any]]:
        base = f"SELECT {self._select_clause()} FROM `{self.settings.mysql_table}` "
        if last_id is None:
            query = base + f"ORDER BY `{self.settings.mysql_id_column}` ASC LIMIT %s"
            args: tuple[Any, ...] = (limit,)
        else:
            query = (
                base
                + f"WHERE `{self.settings.mysql_id_column}` > %s "
                + f"ORDER BY `{self.settings.mysql_id_column}` ASC LIMIT %s"
            )
            args = (last_id, limit)

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, args)
                rows = cursor.fetchall()
        return [self._normalize_row(row) for row in rows]

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        vector = row.get("vector")
        if isinstance(vector, str):
            vector = json.loads(vector)
        row["vector"] = vector
        row["create_time"] = MySQLClient._to_epoch(row.get("create_time"))
        row["update_time"] = MySQLClient._to_epoch(row.get("update_time"))
        if row.get("uid") is not None:
            row["uid"] = int(row["uid"])
        if row.get("content_hash") is None:
            row["content_hash"] = ""
        else:
            row["content_hash"] = str(row["content_hash"])
        if row.get("tag") is None:
            row["tag"] = ""
        else:
            row["tag"] = str(row["tag"])
        return row

    @staticmethod
    def _to_epoch(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return int(value.timestamp())
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None
