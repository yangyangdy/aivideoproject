from __future__ import annotations

from datetime import datetime

from app.config.settings import Settings
from app.db.mysql_client import MySQLClient


def test_normalize_row_maps_extended_fields():
    settings = Settings()
    row = {
        "id": 1,
        "vector": "[0.1,0.2]",
        "material_id": 1,
        "tenant_id": 2,
        "embedding_model": "model-a",
        "dimension": 2,
        "content_hash": "abc123",
        "uid": 7,
        "tag": "demo-tag",
        "create_time": datetime(2026, 1, 1, 0, 0, 0),
        "update_time": 1717000000,
    }
    normalized = MySQLClient(settings)._normalize_row(row)
    assert normalized["content_hash"] == "abc123"
    assert normalized["uid"] == 7
    assert normalized["tag"] == "demo-tag"
    assert isinstance(normalized["create_time"], int)
    assert normalized["update_time"] == 1717000000
