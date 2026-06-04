from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pymilvus import AnnSearchRequest, MilvusClient, RRFRanker, WeightedRanker

from app.config.settings import Settings


@dataclass
class VectorEntity:
    primary_key: int
    embedding: list[float]
    material_id: int = 0
    tenant_id: int = 0
    embedding_model: str = ""
    content_hash: str = ""
    uid: int = 0
    tag: str = ""
    create_time: int = 0
    update_time: int = 0


class MilvusService:
    """Thin wrapper around pymilvus MilvusClient for vector CRUD and search."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: MilvusClient | None = None
        self._loaded = False

    @property
    def collection_name(self) -> str:
        return self.settings.milvus_collection_name

    def connect(self) -> MilvusClient:
        if self._client is not None:
            return self._client
        self._client = MilvusClient(uri=self.settings.milvus_uri, token=self.settings.milvus_token or "")
        return self._client

    def ensure_collection(self) -> None:
        client = self.connect()
        if not client.has_collection(collection_name=self.collection_name):
            raise ValueError(
                f"Collection `{self.collection_name}` does not exist. Please create it in Milvus first."
            )
        if not self._loaded:
            client.load_collection(collection_name=self.collection_name)
            self._loaded = True

    def _build_search_params(self) -> dict[str, Any]:
        index_type = self.settings.milvus_index_type.upper()
        if index_type == "IVF_FLAT":
            return {
                "metric_type": self.settings.milvus_metric_type,
                "params": {"nprobe": self.settings.milvus_search_nprobe},
            }
        if index_type == "HNSW":
            return {"metric_type": self.settings.milvus_metric_type, "params": {"ef": self.settings.milvus_search_ef}}
        return {"metric_type": self.settings.milvus_metric_type, "params": {}}

    def _build_ranker(self, ranker_type: str, weights: list[float] | None, k: int | None):
        if ranker_type == "rrf":
            return RRFRanker(k=k or 60)
        if not weights:
            raise ValueError("ranker_weights is required when ranker_type is weighted")
        return WeightedRanker(*weights)

    def ping(self) -> bool:
        return self.connect().has_collection(collection_name=self.collection_name)

    @staticmethod
    def _sanitize_mutation_result(result: Any) -> Any:
        """Convert pymilvus protobuf containers into JSON-serializable Python types."""
        if isinstance(result, dict):
            return {key: MilvusService._sanitize_mutation_result(value) for key, value in result.items()}
        if isinstance(result, (str, bytes, int, float, bool)) or result is None:
            return result
        if isinstance(result, list):
            return [MilvusService._sanitize_mutation_result(item) for item in result]
        if isinstance(result, tuple):
            return [MilvusService._sanitize_mutation_result(item) for item in result]
        try:
            iterator = iter(result)
        except TypeError:
            return result
        return [MilvusService._sanitize_mutation_result(item) for item in iterator]

    def get(self, ids: list[int], output_fields: list[str] | None = None) -> list[dict[str, Any]]:
        self.ensure_collection()
        return self.connect().get(
            collection_name=self.collection_name,
            ids=ids,
            output_fields=output_fields,
        )

    def _validate_write_data(self, data: list[dict[str, Any]]) -> None:
        expected_dim = self.settings.milvus_vector_dim
        for index, item in enumerate(data):
            if item.get("primary_key") is None:
                raise ValueError(f"data[{index}]: primary_key is required")
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError(f"data[{index}]: embedding must be a list of floats")
            actual_dim = len(embedding)
            if actual_dim != expected_dim:
                meta_dim = item.get("dimension")
                hint = ""
                if meta_dim is not None and int(meta_dim) != actual_dim:
                    hint = (
                        f"; request field 'dimension'={meta_dim} does not match "
                        f"embedding length ({actual_dim}) — Milvus only uses the embedding array"
                    )
                raise ValueError(
                    f"data[{index}]: embedding length must be {expected_dim}, got {actual_dim}{hint}"
                )

    def insert(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        self.ensure_collection()
        self._validate_write_data(data)
        result = self.connect().insert(collection_name=self.collection_name, data=data)
        return self._sanitize_mutation_result(result)

    def query(
        self,
        filter: str,
        output_fields: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        kwargs: dict[str, Any] = {
            "collection_name": self.collection_name,
            "filter": filter,
            "output_fields": output_fields,
        }
        if limit is not None:
            kwargs["limit"] = limit
        return self.connect().query(**kwargs)

    def search(
        self,
        data: list[list[float]],
        limit: int = 10,
        filter: str = "",
        output_fields: list[str] | None = None,
        search_params: dict[str, Any] | None = None,
    ) -> list[Any]:
        self.ensure_collection()
        return self.connect().search(
            collection_name=self.collection_name,
            data=data,
            limit=limit,
            filter=filter,
            output_fields=output_fields,
            search_params=search_params or self._build_search_params(),
        )

    def upsert(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        self.ensure_collection()
        self._validate_write_data(data)
        result = self.connect().upsert(collection_name=self.collection_name, data=data)
        return self._sanitize_mutation_result(result)

    def hybrid_search(
        self,
        reqs: list[dict[str, Any]],
        ranker_type: Literal["weighted", "rrf"] = "weighted",
        ranker_weights: list[float] | None = None,
        ranker_k: int | None = None,
        limit: int = 10,
        output_fields: list[str] | None = None,
    ) -> list[Any]:
        self.ensure_collection()
        ann_reqs = [AnnSearchRequest(**req) for req in reqs]
        ranker = self._build_ranker(ranker_type, ranker_weights, ranker_k)
        return self.connect().hybrid_search(
            collection_name=self.collection_name,
            reqs=ann_reqs,
            ranker=ranker,
            limit=limit,
            output_fields=output_fields,
        )

    def delete(self, ids: list[int] | None = None, filter: str | None = None) -> dict[str, Any]:
        self.ensure_collection()
        kwargs: dict[str, Any] = {"collection_name": self.collection_name}
        if ids is not None:
            kwargs["ids"] = ids
        if filter is not None:
            kwargs["filter"] = filter
        result = self.connect().delete(**kwargs)
        return self._sanitize_mutation_result(result)

    # ---- helpers used by sync script ----

    def upsert_entities(self, items: list[VectorEntity]) -> int:
        if not items:
            return 0
        payload = [
            {
                "primary_key": item.primary_key,
                "embedding": item.embedding,
                "material_id": item.material_id,
                "tenant_id": item.tenant_id,
                "embedding_model": item.embedding_model,
                "content_hash": item.content_hash,
                "uid": item.uid,
                "tag": item.tag,
                "create_time": item.create_time,
                "update_time": item.update_time,
            }
            for item in items
        ]
        self.upsert(payload)
        return len(items)
