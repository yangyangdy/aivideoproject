from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymilvus.exceptions import MilvusException

from app.api.milvus_routes import router as milvus_router
from app.dependencies import get_milvus_service
from app.logging_config import setup_logging
from app.material.api.routes import router as material_router
from app.material.api.version import MATCH_API_VERSION, MATCH_SEGMENT_FIELDS
from app.middleware.request_logging import RequestLoggingMiddleware

http_logger = logging.getLogger("app.http")

setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.config.settings import get_settings
    from app.logging_config import _running_under_pytest

    startup_logger = logging.getLogger("app.startup")
    if not _running_under_pytest():
        log_path = setup_logging()
        settings = get_settings()
        startup_logger.info(
            "service ready api_version=%s segment_fields=%s host=%s port=%s log_file=%s endpoint=POST /material/match-segments GET /material/info",
            MATCH_API_VERSION,
            ",".join(MATCH_SEGMENT_FIELDS),
            settings.app_host,
            settings.app_port,
            log_path,
        )
    yield


app = FastAPI(title="Milvus Vector Service", version="0.2.0", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(milvus_router)
app.include_router(material_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    http_logger.warning(
        "request validation failed path=%s errors=%s",
        request.url.path,
        exc.errors(),
    )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    http_logger.warning("request rejected path=%s detail=%s", request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(MilvusException)
async def milvus_exception_handler(_request: Request, exc: MilvusException) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.get("/health")
def health() -> dict[str, bool]:
    service = get_milvus_service()
    return {"ok": service.ping()}
