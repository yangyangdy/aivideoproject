from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymilvus.exceptions import MilvusException

from app.api.milvus_routes import router as milvus_router
from app.dependencies import get_milvus_service

app = FastAPI(title="Milvus Vector Service", version="0.2.0")
app.include_router(milvus_router)


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(MilvusException)
async def milvus_exception_handler(_request: Request, exc: MilvusException) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.get("/health")
def health() -> dict[str, bool]:
    service = get_milvus_service()
    return {"ok": service.ping()}
