from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "milvus-vector-service"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root"
    mysql_database: str = "vector_db"
    mysql_table: str = "vector_data"
    mysql_id_column: str = "id"
    mysql_material_id_column: str = "material_id"
    mysql_tenant_id_column: str = "tenant_id"
    mysql_vector_column: str = "embedding"
    mysql_embedding_model_column: str = "embedding_model"
    mysql_dimension_column: str = "dimension"
    mysql_content_hash_column: str = "content_hash"
    mysql_uid_column: str = "uid"
    mysql_tag_column: str = "tag"
    mysql_create_time_column: str = "create_time"
    mysql_update_time_column: str = "update_time"

    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: str = ""
    milvus_collection_name: str = "ai_material_embedding"
    milvus_vector_dim: int = 2048
    milvus_metric_type: str = "COSINE"
    milvus_index_type: str = "IVF_FLAT"
    milvus_index_nlist: int = 1024
    milvus_search_nprobe: int = 16
    milvus_search_ef: int = 64

    sync_batch_size: int = 1000
    sync_state_file: str = "state/sync_cursor.json"

    embedding_api_url: str = "https://operator.las.cn-beijing.volces.com/api/v1/embeddings/multimodal"
    embedding_api_key: str = ""
    embedding_model: str = "doubao-embedding-vision-250615"
    embedding_dimensions: int = 2048
    embedding_timeout_seconds: int = 60

    @field_validator("embedding_api_key", mode="before")
    @classmethod
    def normalize_embedding_api_key(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    @property
    def sync_state_path(self) -> Path:
        return Path(self.sync_state_file)

    @property
    def mysql_dsn(self) -> str:
        return (
            f"host={self.mysql_host} port={self.mysql_port} user={self.mysql_user} "
            f"database={self.mysql_database}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
