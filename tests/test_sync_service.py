from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.services.sync_service import SyncService


class FakeMySQLClient:
    def __init__(self):
        self.full_called = False
        self.incremental_called = False
        self.full_limit = None
        self.incremental_limit = None

    def fetch_full_batch(self, offset: int, limit: int):
        self.full_called = True
        self.full_limit = limit
        if offset > 0:
            return []
        return [
            {
                "id": 1,
                "vector": [0.1, 0.2],
                "dimension": 2,
                "material_id": 10,
                "tenant_id": 20,
                "embedding_model": "m1",
                "content_hash": "hash-1",
                "uid": 3,
                "tag": "tag-1",
                "create_time": 100,
                "update_time": 200,
            }
        ]

    def fetch_incremental_batch(self, last_id, limit: int):
        self.incremental_called = True
        self.incremental_limit = limit
        if last_id is not None:
            return []
        return [
            {
                "id": 2,
                "vector": [0.3, 0.4],
                "metadata": {"source": "b"},
                "dimension": 2,
            }
        ]


class FakeMilvusService:
    def __init__(self):
        self.items = []

    def ensure_collection(self):
        return None

    def upsert_entities(self, entities):
        self.items.extend(entities)
        return len(entities)


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        milvus_vector_dim=2,
        sync_state_file=str(tmp_path / "state" / "sync_cursor.json"),
    )


def test_full_sync_writes_records(tmp_path: Path):
    settings = build_settings(tmp_path)
    mysql_client = FakeMySQLClient()
    milvus_service = FakeMilvusService()
    service = SyncService(settings=settings, mysql_client=mysql_client, milvus_service=milvus_service)

    stats = service.run_full_sync(batch_size=100)

    assert mysql_client.full_called is True
    assert stats.total == 1
    assert stats.success == 1
    assert stats.failed == 0
    assert len(milvus_service.items) == 1
    entity = milvus_service.items[0]
    assert entity.content_hash == "hash-1"
    assert entity.uid == 3
    assert entity.tag == "tag-1"
    assert entity.create_time == 100
    assert entity.update_time == 200


def test_incremental_sync_persists_cursor(tmp_path: Path):
    settings = build_settings(tmp_path)
    mysql_client = FakeMySQLClient()
    milvus_service = FakeMilvusService()
    service = SyncService(settings=settings, mysql_client=mysql_client, milvus_service=milvus_service)

    stats = service.run_incremental_sync(batch_size=100)

    assert mysql_client.incremental_called is True
    assert stats.total == 1
    assert stats.success == 1
    assert service.load_cursor() == 2


def test_full_sync_respects_max_records(tmp_path: Path):
    settings = build_settings(tmp_path)
    mysql_client = FakeMySQLClient()
    milvus_service = FakeMilvusService()
    service = SyncService(settings=settings, mysql_client=mysql_client, milvus_service=milvus_service)

    stats = service.run_full_sync(batch_size=100, max_records=1)

    assert stats.total == 1
    assert stats.success == 1
    assert mysql_client.full_limit == 1


def test_incremental_sync_respects_max_records(tmp_path: Path):
    settings = build_settings(tmp_path)
    mysql_client = FakeMySQLClient()
    milvus_service = FakeMilvusService()
    service = SyncService(settings=settings, mysql_client=mysql_client, milvus_service=milvus_service)

    stats = service.run_incremental_sync(batch_size=100, max_records=1)

    assert stats.total == 1
    assert stats.success == 1
    assert mysql_client.incremental_limit == 1
