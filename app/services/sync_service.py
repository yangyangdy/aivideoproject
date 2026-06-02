from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.settings import Settings
from app.db.mysql_client import MySQLClient
from app.services.milvus_service import MilvusService, VectorEntity


@dataclass
class SyncStats:
    total: int = 0
    success: int = 0
    failed: int = 0


class SyncService:
    def __init__(self, settings: Settings, mysql_client: MySQLClient, milvus_service: MilvusService):
        self.settings = settings
        self.mysql_client = mysql_client
        self.milvus_service = milvus_service

    def run_full_sync(self, batch_size: int | None = None, max_records: int | None = None) -> SyncStats:
        size = batch_size or self.settings.sync_batch_size
        stats = SyncStats()
        self.milvus_service.ensure_collection()

        offset = 0
        while True:
            if max_records is not None and stats.total >= max_records:
                break
            current_limit = size
            if max_records is not None:
                current_limit = min(size, max_records - stats.total)
                if current_limit <= 0:
                    break
            rows = self.mysql_client.fetch_full_batch(offset=offset, limit=current_limit)
            if not rows:
                break
            entities, failed = self._prepare_entities(rows)
            written = self.milvus_service.upsert_entities(entities)
            stats.total += len(rows)
            stats.success += written
            stats.failed += failed
            offset += len(rows)
        return stats

    def run_incremental_sync(self, batch_size: int | None = None, max_records: int | None = None) -> SyncStats:
        size = batch_size or self.settings.sync_batch_size
        stats = SyncStats()
        self.milvus_service.ensure_collection()
        last_id = self.load_cursor()
        max_seen_id = last_id
        while True:
            if max_records is not None and stats.total >= max_records:
                break
            current_limit = size
            if max_records is not None:
                current_limit = min(size, max_records - stats.total)
                if current_limit <= 0:
                    break
            rows = self.mysql_client.fetch_incremental_batch(last_id=last_id, limit=current_limit)
            if not rows:
                break
            entities, failed = self._prepare_entities(rows)
            written = self.milvus_service.upsert_entities(entities)
            stats.total += len(rows)
            stats.success += written
            stats.failed += failed
            if rows:
                max_seen_id = max(int(row["id"]) for row in rows)
                last_id = max_seen_id

        if max_seen_id is not None:
            self.save_cursor(max_seen_id)
        return stats

    def load_cursor(self) -> int | None:
        path = self.settings.sync_state_path
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        last_id = payload.get("last_id")
        return int(last_id) if last_id is not None else None

    def save_cursor(self, cursor: int) -> None:
        path = self.settings.sync_state_path
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"last_id": cursor}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _prepare_entities(self, rows: list[dict[str, Any]]) -> tuple[list[VectorEntity], int]:
        entities: list[VectorEntity] = []
        failed = 0
        for row in rows:
            try:
                entities.append(self._to_entity(row))
            except (TypeError, ValueError):
                failed += 1
        return entities, failed

    def _to_entity(self, row: dict[str, Any]) -> VectorEntity:
        item_id = int(row["id"])
        vector = row["vector"]
        if not isinstance(vector, list):
            raise TypeError("vector must be list")
        source_dimension = row.get("dimension")
        if source_dimension is not None and int(source_dimension) != len(vector):
            raise ValueError(
                f"source dimension mismatch for id={item_id}, source={source_dimension}, actual={len(vector)}"
            )
        if len(vector) != self.settings.milvus_vector_dim:
            raise ValueError(
                f"vector dim mismatch for id={item_id}, expected {self.settings.milvus_vector_dim}, got {len(vector)}"
            )
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        create_time = row.get("create_time")
        update_time = row.get("update_time")
        return VectorEntity(
            primary_key=item_id,
            embedding=[float(v) for v in vector],
            material_id=int(row.get("material_id") or 0),
            tenant_id=int(row.get("tenant_id") or 0),
            embedding_model=str(row.get("embedding_model") or ""),
            content_hash=str(row.get("content_hash") or ""),
            uid=int(row.get("uid") or 0),
            tag=str(row.get("tag") or ""),
            create_time=int(create_time if create_time is not None else now_epoch),
            update_time=int(update_time if update_time is not None else now_epoch),
        )
