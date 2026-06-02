from functools import lru_cache

from app.config.settings import get_settings
from app.db.mysql_client import MySQLClient
from app.services.embedding_service import EmbeddingService
from app.services.milvus_service import MilvusService
from app.services.sync_service import SyncService


@lru_cache(maxsize=1)
def get_milvus_service() -> MilvusService:
    settings = get_settings()
    return MilvusService(settings)


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(settings)


@lru_cache(maxsize=1)
def get_sync_service() -> SyncService:
    settings = get_settings()
    mysql_client = MySQLClient(settings)
    milvus_service = MilvusService(settings)
    return SyncService(settings=settings, mysql_client=mysql_client, milvus_service=milvus_service)
