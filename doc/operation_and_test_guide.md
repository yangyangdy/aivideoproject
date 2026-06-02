# 操作与测试指南

本文档用于本项目日常开发、联调、离线同步和测试验收。

## 1. 前置条件

- Python 3.10+
- 可用的 MySQL 实例（包含向量源表）
- 可用的 Milvus 实例（已创建 collection：`ai_material_embedding`）

推荐先确认 Milvus collection 关键字段：

- `primary_key` (INT64, primary)
- `embedding` (FLOAT_VECTOR, dim=2048)
- `material_id` (INT32)
- `tenant_id` (INT32)
- `embedding_model` (VARCHAR)
- `content_hash` (VARCHAR)
- `uid` (INT16)
- `tag` (VARCHAR)
- `create_time` (INT32)
- `update_time` (INT32)

## 2. 环境配置

### 2.1 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2.2 初始化配置

```bash
cp .env.example .env
```

建议重点检查 `.env`：

- `MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE`
- `MYSQL_TABLE` 与字段映射（含 `content_hash/uid/tag/create_time/update_time` 等，见 `.env.example`）
- `MILVUS_URI`、`MILVUS_TOKEN`
- `MILVUS_COLLECTION_NAME=ai_material_embedding`
- `MILVUS_VECTOR_DIM=2048`、`MILVUS_INDEX_TYPE=IVF_FLAT`
- `MILVUS_INDEX_NLIST`、`MILVUS_SEARCH_NPROBE`
- `EMBEDDING_API_KEY`、`EMBEDDING_API_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`

## 3. 服务启动与接口操作

第三方集成请参阅完整接口说明：[api_reference.md](./api_reference.md)（含各接口请求参数、返回字段与示例）。

### 3.1 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.2 健康检查

```bash
curl http://127.0.0.1:8000/health
```

期望返回：

```json
{"ok": true}
```

### 3.3 API 调用示例

以下示例均使用当前 `/milvus/*` 接口（详见 [api_reference.md](./api_reference.md)）。

#### 3.3.1 Upsert（写入/更新，需传 2048 维 embedding）

```bash
curl -X POST "http://127.0.0.1:8000/milvus/upsert" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "primary_key": 2001,
      "embedding": [0.01, 0.02],
      "material_id": 10,
      "tenant_id": 1,
      "embedding_model": "text-embedding-3-small",
      "content_hash": "hash-demo",
      "uid": 1,
      "tag": "tag-a",
      "create_time": 1717000000,
      "update_time": 1717000000
    }]
  }'
```

> 示例中 `embedding` 仅展示前 2 维，实际须 **2048** 维。

#### 3.3.2 按主键查询

```bash
curl -X POST "http://127.0.0.1:8000/milvus/get" \
  -H "Content-Type: application/json" \
  -d '{"ids": [2001], "output_fields": ["primary_key", "material_id", "tenant_id", "tag"]}'
```

#### 3.3.3 标量条件查询（非向量检索）

```bash
curl -X POST "http://127.0.0.1:8000/milvus/query" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": "tenant_id == 1",
    "output_fields": ["primary_key", "material_id", "tag"],
    "limit": 10
  }'
```

#### 3.3.4 文本相似检索（服务端自动向量化）

```bash
curl -X POST "http://127.0.0.1:8000/milvus/search" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"type": "text", "text": "球员三步上篮得分"}],
    "limit": 5,
    "filter": "tenant_id == 1",
    "output_fields": ["material_id", "tenant_id", "tag"]
  }'
```

需配置 `EMBEDDING_API_KEY`。图片检索将 `input` 改为：

```json
{"type": "image_url", "image_url": {"url": "https://example.com/test.jpg"}}
```

#### 3.3.5 混合检索

```bash
curl -X POST "http://127.0.0.1:8000/milvus/hybrid-search" \
  -H "Content-Type: application/json" \
  -d '{
    "reqs": [{
      "input": [{"type": "text", "text": "球员三步上篮得分"}],
      "param": {"metric_type": "COSINE", "params": {"nprobe": 16}},
      "limit": 20
    }],
    "ranker_type": "weighted",
    "ranker_weights": [1.0],
    "limit": 10,
    "output_fields": ["material_id", "tenant_id", "tag"]
  }'
```

#### 3.3.6 删除

```bash
curl -X POST "http://127.0.0.1:8000/milvus/delete" \
  -H "Content-Type: application/json" \
  -d '{"ids": [2001]}'
```

## 4. 离线同步操作

脚本：`scripts/sync_mysql_to_milvus.py`

脚本支持参数：

- `--mode`：`full` / `incremental`（必填）
- `--batch-size`：单批读取与写入条数（可选）
- `--max-records`：本次最多同步条数（可选，适合联调与抽样验证）

### 4.1 全量同步

```bash
python scripts/sync_mysql_to_milvus.py --mode full --batch-size 1000
```

### 4.2 增量同步

当前实现增量游标为 `last_id`（状态文件：`state/sync_cursor.json`）：

```bash
python scripts/sync_mysql_to_milvus.py --mode incremental --batch-size 1000
```

### 4.3 指定数量同步（联调推荐）

只同步指定条数，便于快速检查：

```bash
python scripts/sync_mysql_to_milvus.py --mode full --max-records 100
```

增量模式同理：

```bash
python scripts/sync_mysql_to_milvus.py --mode incremental --max-records 50
```

可与批次组合使用（例如每批 20，最多 100）：

```bash
python scripts/sync_mysql_to_milvus.py --mode full --batch-size 20 --max-records 100
```

说明：

- 当达到 `max-records` 后脚本会立即停止本轮同步
- 不会影响后续再次执行（增量游标仍按本次成功处理的最大 `id` 更新）

### 4.4 同步结果校验

脚本会输出 JSON，例如：

```json
{
  "mode": "incremental",
  "total": 1000,
  "success": 995,
  "failed": 5,
  "elapsed_seconds": 12.34
}
```

建议检查：

- `failed` 是否为 0 或可解释
- 失败是否由向量维度不一致导致（`dimension` 或 `MILVUS_VECTOR_DIM` 配置问题）

## 5. 测试指南

### 5.1 执行自动化测试

```bash
pytest -q
```

当前测试覆盖：

- `tests/test_milvus_service.py`：Milvus 封装层
- `tests/test_embedding_service.py`：向量化响应解析
- `tests/test_milvus_api.py`：HTTP 接口
- `tests/test_sync_service.py`：全量/增量同步、游标、`max-records` 限流
- `tests/test_mysql_client.py`：MySQL 字段映射

### 5.2 回归检查清单

每次修改后建议至少验证：

1. `pytest -q` 全通过
2. `/health` 返回 `ok=true`
3. `POST /milvus/upsert` + `POST /milvus/get` 正常
4. `POST /milvus/search`（文本 `input`）正常返回
5. 同步脚本在目标环境可执行并返回统计结果

## 6. 常见问题排查

### 6.1 维度不匹配

现象：同步失败或写入失败。  
排查：

- 确认 MySQL `dimension` 与 `embedding` 实际长度一致
- 确认 `.env` 中 `MILVUS_VECTOR_DIM=2048`
- 确认 Milvus collection 向量字段维度是 2048

### 6.2 检索效果不稳定

`IVF_FLAT` 下建议调优：

- 增大 `MILVUS_INDEX_NLIST`（更细分桶）
- 增大 `MILVUS_SEARCH_NPROBE`（更高召回，牺牲延迟）

### 6.4 文本检索失败（Embedding API）

现象：`POST /milvus/search` 返回 500 或校验错误。  
排查：

- 确认 `.env` 中 `EMBEDDING_API_KEY` 已配置且有效
- 确认 `EMBEDDING_API_URL` 可访问
- 确认 `input` 格式正确（`type=text` 时必须有 `text` 字段）

### 6.3 增量未覆盖“更新旧记录”

当前增量条件是 `id > last_id`，适用于“新增”场景。  
若需要覆盖“旧 id 被更新”场景，建议引入 `updated_at` 作为增量游标并改造同步查询条件。
