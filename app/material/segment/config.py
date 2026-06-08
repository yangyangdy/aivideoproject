from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MaterialSettings(BaseSettings):
    """Settings for material module (ASR, segmentation, matching)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Volcano Engine ASR v3 bigmodel（见 asr-integration-example.md）
    asr_app_id: str = ""
    asr_access_token: str = ""
    asr_api_key: str = ""
    asr_resource_id: str = "volc.bigasr.auc"
    asr_submit_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
    asr_query_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
    asr_model_name: str = "bigmodel"
    asr_audio_format: str = "mp3"
    asr_enable_itn: bool = True
    asr_enable_punc: bool = True
    asr_show_utterances: bool = True
    asr_timeout_seconds: int = 60
    asr_poll_interval_seconds: float = 1.0
    asr_poll_max_attempts: int = 120

    # 3-second segmentation
    segment_duration_ms: int = 3000
    segment_min_chars: int = 6
    segment_max_borrow_words: int = 8
    segment_max_chars: int = 80
    segment_sentence_endings: str = "。！？；.!?;"

    # Material matching
    match_fallback_material_id: int = 0
    milvus_search_batch_size: int = 10


@lru_cache(maxsize=1)
def get_material_settings() -> MaterialSettings:
    return MaterialSettings()
