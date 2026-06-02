from __future__ import annotations

from fastapi.testclient import TestClient

from app.dependencies import get_embedding_service, get_milvus_service
from app.main import app


class FakeEmbeddingService:
    def embed(self, input_items, model=None, dimensions=None):
        return [[0.1, 0.2] for _ in input_items]


class FakeMilvusService:
    def ping(self):
        return True

    def ensure_collection(self):
        return None

    def get(self, ids, output_fields=None):
        return [{"primary_key": ids[0], "tenant_id": 1}]

    def insert(self, data):
        return {"insert_count": len(data)}

    def query(self, filter, output_fields=None, limit=None):
        return [{"primary_key": 1}]

    def search(self, data, limit=10, filter="", output_fields=None, search_params=None):
        assert data == [[0.1, 0.2]]
        return [[{"id": 1, "distance": 0.9, "entity": {"tenant_id": 1}}]]

    def upsert(self, data):
        return {"upsert_count": len(data)}

    def hybrid_search(self, reqs, ranker_type="weighted", ranker_weights=None, ranker_k=None, limit=10, output_fields=None):
        assert reqs[0]["data"] == [[0.1, 0.2]]
        return [[{"id": 1, "distance": 0.8}]]

    def delete(self, ids=None, filter=None):
        return {"delete_count": 1 if ids else 0}


def test_milvus_sdk_routes():
    app.dependency_overrides[get_milvus_service] = lambda: FakeMilvusService()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    assert client.post("/milvus/get", json={"ids": [1]}).status_code == 200
    assert client.post("/milvus/insert", json={"data": [{"primary_key": 1, "embedding": [0.1]}]}).status_code == 200
    assert client.post("/milvus/query", json={"filter": "primary_key > 0", "limit": 10}).status_code == 200

    search_resp = client.post(
        "/milvus/search",
        json={
            "input": [{"type": "text", "text": "球员三步上篮得分"}],
            "limit": 5,
            "filter": "tenant_id == 1",
        },
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["query_vector_count"] == 1

    assert client.post("/milvus/upsert", json={"data": [{"primary_key": 1, "embedding": [0.1]}]}).status_code == 200

    hybrid_resp = client.post(
        "/milvus/hybrid-search",
        json={
            "reqs": [
                {
                    "input": [{"type": "text", "text": "检索文本"}],
                    "anns_field": "embedding",
                    "param": {"metric_type": "COSINE", "params": {"nprobe": 16}},
                    "limit": 5,
                }
            ],
            "ranker_type": "weighted",
            "ranker_weights": [1.0],
            "limit": 5,
        },
    )
    assert hybrid_resp.status_code == 200

    assert client.post("/milvus/delete", json={"ids": [1]}).status_code == 200

    app.dependency_overrides.clear()
