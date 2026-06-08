from functools import lru_cache

from app.dependencies import get_embedding_service, get_milvus_service
from app.material.asr.volcano_asr_service import VolcanoAsrService
from app.material.config import MaterialSettings, get_material_settings
from app.material.matching.embedder_adapter import EmbedderAdapter
from app.material.matching.milvus_searcher_adapter import MilvusSearcherAdapter
from app.material.matching.orchestrator import MatchOrchestrator


@lru_cache(maxsize=1)
def get_volcano_asr_service() -> VolcanoAsrService:
    settings = get_material_settings()
    return VolcanoAsrService(settings)


@lru_cache(maxsize=1)
def get_match_orchestrator() -> MatchOrchestrator:
    settings = get_material_settings()
    embedder = EmbedderAdapter(get_embedding_service())
    searcher = MilvusSearcherAdapter(get_milvus_service(), settings)
    return MatchOrchestrator(
        settings=settings,
        embedder=embedder,
        searcher=searcher,
        asr_client=get_volcano_asr_service(),
    )
