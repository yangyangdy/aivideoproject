from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EmbeddingInputItem(BaseModel):
    """Multimodal input item, same structure as Volces embedding API."""

    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_content(self) -> EmbeddingInputItem:
        if self.type == "text" and not self.text:
            raise ValueError("text is required when type is text")
        if self.type == "image_url" and not self.image_url:
            raise ValueError("image_url is required when type is image_url")
        return self

    def to_api_payload(self) -> dict[str, Any]:
        if self.type == "text":
            return {"type": "text", "text": self.text}
        return {"type": "image_url", "image_url": self.image_url}


class MilvusGetRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    output_fields: list[str] | None = None


class MilvusInsertRequest(BaseModel):
    data: list[dict[str, Any]] = Field(min_length=1)


class MilvusQueryRequest(BaseModel):
    filter: str
    output_fields: list[str] | None = None
    limit: int | None = Field(default=None, ge=1)


class MilvusSearchRequest(BaseModel):
    """Pass raw text/image; server embeds then searches Milvus."""

    input: list[EmbeddingInputItem] = Field(min_length=1, description="Multimodal content to embed")
    limit: int = Field(default=10, ge=1, le=1000)
    filter: str = ""
    output_fields: list[str] | None = None
    search_params: dict[str, Any] | None = None
    model: str | None = None
    dimensions: int | None = Field(default=None, ge=1)


class MilvusUpsertRequest(BaseModel):
    data: list[dict[str, Any]] = Field(min_length=1)


class HybridSearchReqItem(BaseModel):
    """One ANN search branch: embed input on server, then search."""

    input: list[EmbeddingInputItem] = Field(min_length=1)
    anns_field: str = "embedding"
    param: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=1000)
    model: str | None = None
    dimensions: int | None = Field(default=None, ge=1)


class MilvusHybridSearchRequest(BaseModel):
    reqs: list[HybridSearchReqItem] = Field(min_length=1)
    ranker_type: Literal["weighted", "rrf"] = "weighted"
    ranker_weights: list[float] | None = None
    ranker_k: int | None = Field(default=None, ge=1)
    limit: int = Field(default=10, ge=1, le=1000)
    output_fields: list[str] | None = None


class MilvusDeleteRequest(BaseModel):
    ids: list[int] | None = None
    filter: str | None = None

    @model_validator(mode="after")
    def require_ids_or_filter(self) -> MilvusDeleteRequest:
        if not self.ids and not self.filter:
            raise ValueError("either ids or filter must be provided")
        return self
