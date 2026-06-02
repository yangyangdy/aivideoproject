from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_embedding_service, get_milvus_service
from app.schemas.milvus import (
    EmbeddingInputItem,
    MilvusDeleteRequest,
    MilvusGetRequest,
    MilvusHybridSearchRequest,
    MilvusInsertRequest,
    MilvusQueryRequest,
    MilvusSearchRequest,
    MilvusUpsertRequest,
)
from app.services.embedding_service import EmbeddingService
from app.services.milvus_service import MilvusService

router = APIRouter(prefix="/milvus", tags=["milvus"])


def _embed_inputs(
    embedding_service: EmbeddingService,
    items: list[EmbeddingInputItem],
    model: str | None = None,
    dimensions: int | None = None,
) -> list[list[float]]:
    payload = [item.to_api_payload() for item in items]
    return embedding_service.embed(input_items=payload, model=model, dimensions=dimensions)


@router.post("/get")
def milvus_get(
    request: MilvusGetRequest,
    service: MilvusService = Depends(get_milvus_service),
) -> dict[str, Any]:
    data = service.get(ids=request.ids, output_fields=request.output_fields)
    return {"data": data}


@router.post("/insert")
def milvus_insert(
    request: MilvusInsertRequest,
    service: MilvusService = Depends(get_milvus_service),
) -> dict[str, Any]:
    result = service.insert(data=request.data)
    return {"result": result}


@router.post("/query")
def milvus_query(
    request: MilvusQueryRequest,
    service: MilvusService = Depends(get_milvus_service),
) -> dict[str, Any]:
    data = service.query(
        filter=request.filter,
        output_fields=request.output_fields,
        limit=request.limit,
    )
    return {"data": data}


@router.post("/search")
def milvus_search(
    request: MilvusSearchRequest,
    milvus_service: MilvusService = Depends(get_milvus_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> dict[str, Any]:
    vectors = _embed_inputs(
        embedding_service,
        request.input,
        model=request.model,
        dimensions=request.dimensions,
    )
    data = milvus_service.search(
        data=vectors,
        limit=request.limit,
        filter=request.filter,
        output_fields=request.output_fields,
        search_params=request.search_params,
    )
    return {"data": data, "query_vector_count": len(vectors)}


@router.post("/upsert")
def milvus_upsert(
    request: MilvusUpsertRequest,
    service: MilvusService = Depends(get_milvus_service),
) -> dict[str, Any]:
    result = service.upsert(data=request.data)
    return {"result": result}


@router.post("/hybrid-search")
def milvus_hybrid_search(
    request: MilvusHybridSearchRequest,
    milvus_service: MilvusService = Depends(get_milvus_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> dict[str, Any]:
    ann_reqs: list[dict[str, Any]] = []
    for item in request.reqs:
        vectors = _embed_inputs(
            embedding_service,
            item.input,
            model=item.model,
            dimensions=item.dimensions,
        )
        ann_reqs.append(
            {
                "data": vectors,
                "anns_field": item.anns_field,
                "param": item.param,
                "limit": item.limit,
            }
        )
    data = milvus_service.hybrid_search(
        reqs=ann_reqs,
        ranker_type=request.ranker_type,
        ranker_weights=request.ranker_weights,
        ranker_k=request.ranker_k,
        limit=request.limit,
        output_fields=request.output_fields,
    )
    return {"data": data}


@router.post("/delete")
def milvus_delete(
    request: MilvusDeleteRequest,
    service: MilvusService = Depends(get_milvus_service),
) -> dict[str, Any]:
    result = service.delete(ids=request.ids, filter=request.filter)
    return {"result": result}
