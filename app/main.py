from __future__ import annotations

from fastapi import FastAPI

from app.api.milvus_routes import router as milvus_router
from app.dependencies import get_milvus_service

app = FastAPI(title="Milvus Vector Service", version="0.2.0")
app.include_router(milvus_router)


@app.get("/health")
def health() -> dict[str, bool]:
    service = get_milvus_service()
    return {"ok": service.ping()}
