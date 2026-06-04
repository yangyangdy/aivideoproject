from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.services.milvus_service import MilvusService, VectorEntity


class FakeMilvusClient:
    def __init__(self):
        self.collection_exists = True
        self.loaded = False
        self.last_get = None
        self.last_insert = None
        self.last_query = None
        self.last_search = None
        self.last_upsert = None
        self.last_hybrid = None
        self.last_delete = None

    def has_collection(self, collection_name: str):
        return self.collection_exists

    def load_collection(self, collection_name: str):
        self.loaded = True

    def get(self, collection_name: str, ids, output_fields=None):
        self.last_get = {"ids": ids, "output_fields": output_fields}
        return [{"primary_key": ids[0]}] if ids else []

    def insert(self, collection_name: str, data):
        self.last_insert = data
        return {"insert_count": len(data)}

    def query(self, collection_name: str, filter: str, output_fields=None, limit=None):
        self.last_query = {"filter": filter, "limit": limit}
        return [{"primary_key": 1}] if "primary_key in [1]" in filter else []

    def search(self, collection_name: str, data, limit, filter="", output_fields=None, search_params=None):
        self.last_search = {"data": data, "limit": limit, "filter": filter}
        return [[{"id": 1, "distance": 0.9}]]

    def upsert(self, collection_name: str, data):
        self.last_upsert = data
        return {"upsert_count": len(data), "ids": (item["primary_key"] for item in data)}

    def hybrid_search(self, collection_name: str, reqs, ranker, limit=10, output_fields=None):
        self.last_hybrid = {"reqs": reqs, "limit": limit}
        return [[{"id": 1, "distance": 0.8}]]

    def delete(self, collection_name: str, ids=None, filter=None):
        self.last_delete = {"ids": ids, "filter": filter}
        return {"delete_count": len(ids) if ids else 0}


def test_wrapper_get():
    service = MilvusService(Settings())
    fake = FakeMilvusClient()
    service._client = fake  # noqa: SLF001
    service._loaded = True

    rows = service.get(ids=[1], output_fields=["primary_key"])
    assert rows[0]["primary_key"] == 1
    assert fake.last_get["ids"] == [1]


def test_wrapper_upsert_entities():
    service = MilvusService(Settings(milvus_vector_dim=2))
    fake = FakeMilvusClient()
    service._client = fake  # noqa: SLF001
    service._loaded = True

    count = service.upsert_entities(
        [VectorEntity(primary_key=1, embedding=[0.1, 0.2], material_id=11, tenant_id=22)]
    )
    assert count == 1
    assert fake.last_upsert[0]["primary_key"] == 1


def test_wrapper_search():
    service = MilvusService(Settings())
    fake = FakeMilvusClient()
    service._client = fake  # noqa: SLF001
    service._loaded = True

    result = service.search(data=[[0.1, 0.2]], limit=5, filter="tenant_id == 1")
    assert result[0][0]["id"] == 1
    assert fake.last_search["limit"] == 5


def test_upsert_rejects_wrong_embedding_dim():
    service = MilvusService(Settings(milvus_vector_dim=2048))
    fake = FakeMilvusClient()
    service._client = fake  # noqa: SLF001
    service._loaded = True

    with pytest.raises(ValueError, match="embedding length must be 2048, got 1"):
        service.upsert(
            [
                {
                    "primary_key": 35344,
                    "embedding": [-0.016357421875],
                    "dimension": 1024,
                }
            ]
        )
    assert fake.last_upsert is None


def test_sanitize_mutation_result_converts_iterables():
    service = MilvusService(Settings(milvus_vector_dim=2))
    fake = FakeMilvusClient()
    service._client = fake  # noqa: SLF001
    service._loaded = True

    result = service.upsert([{"primary_key": 1, "embedding": [0.1, 0.2]}])
    assert result == {"upsert_count": 1, "ids": [1]}
