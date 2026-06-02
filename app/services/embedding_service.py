from __future__ import annotations

import re
from typing import Any

import httpx

from app.config.settings import Settings

# 方舟真实 Key 为 sk- 后接较长随机串；sk-UUID 多为误用业务 ID 或错误拼接
_SK_UUID_PATTERN = re.compile(
    r"^sk-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class EmbeddingService:
    """Call Volces multimodal embedding API to convert text/image into vectors."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def embed(
        self,
        input_items: list[dict[str, Any]],
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        if not input_items:
            raise ValueError("input_items must not be empty")
        api_key = self.settings.embedding_api_key
        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is not configured")
        if api_key.startswith("your_") or api_key == "your_api_key_here":
            raise ValueError("EMBEDDING_API_KEY is still placeholder, please set a real API key in .env")
        if _SK_UUID_PATTERN.match(api_key):
            raise ValueError(
                "EMBEDDING_API_KEY 形如 sk-xxxxxxxx-xxxx-....（UUID），不是火山方舟有效 Key。"
                "请到 https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey 创建 API Key，"
                "复制完整 sk- 开头字符串写入 .env 后重启服务。"
            )

        payload = {
            "model": model or self.settings.embedding_model,
            "dimensions": dimensions or self.settings.embedding_dimensions,
            "encoding_format": "float",
            "input": input_items,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        with httpx.Client(timeout=self.settings.embedding_timeout_seconds) as client:
            response = client.post(self.settings.embedding_api_url, headers=headers, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:800]
                hint = (
                    "请确认：1) EMBEDDING_API_KEY 来自火山方舟/LAS「API Key 管理」（通常为 sk- 开头）；"
                    "2) 已在控制台开通 doubao-embedding-vision 模型；"
                    "3) 修改 .env 后需重启 uvicorn（配置有缓存）。"
                )
                if exc.response.status_code == 401:
                    hint += " 401 多为 Key 无效、过期或类型不对（不要用 Milvus Token 代替）。"
                raise ValueError(
                    f"Embedding API HTTP {exc.response.status_code}: {body}. {hint}"
                ) from exc
            return self._parse_embeddings(response.json())

    @staticmethod
    def _parse_embeddings(body: dict[str, Any]) -> list[list[float]]:
        data = body.get("data")
        if isinstance(data, dict) and "embedding" in data:
            return [[float(v) for v in data["embedding"]]]
        if isinstance(data, list):
            vectors: list[list[float]] = []
            for item in data:
                if isinstance(item, dict) and "embedding" in item:
                    vectors.append([float(v) for v in item["embedding"]])
            if vectors:
                return vectors
        raise ValueError(f"unexpected embedding API response: {body}")
