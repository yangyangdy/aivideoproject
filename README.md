# ai_material_project

基于 `Python + FastAPI + pymilvus` 的向量服务，包含：

- MySQL 向量数据离线同步到 Milvus（全量 / 增量）
- 对外提供 Milvus 向量数据增删改查与相似检索 API

当前实现已对齐的 Milvus Collection（你已创建）核心约束：

- Collection: `ai_material_embedding`
- 主键字段: `primary_key`（INT64）
- 向量字段: `embedding`（FLOAT_VECTOR, dim=2048）
- 索引类型: `IVF_FLAT`
- 度量方式: `COSINE`

## 项目结构

```text
.
├── app
│   ├── api
│   │   └── milvus_routes.py        # Milvus SDK 封装接口
│   ├── config
│   │   └── settings.py             # 配置管理
│   ├── db
│   │   └── mysql_client.py         # MySQL 数据读取
│   ├── schemas
│   │   └── milvus.py               # 请求/响应模型
│   ├── services
│   │   ├── embedding_service.py    # 火山多模态向量化
│   │   ├── milvus_service.py       # pymilvus MilvusClient 封装
│   │   └── sync_service.py         # 离线同步逻辑
│   └── main.py                     # FastAPI 入口
├── scripts
│   └── sync_mysql_to_milvus.py     # 离线同步脚本
├── tests                           # 测试用例
├── .env.example                    # 环境变量示例
└── doc
    ├── api_reference.md            # 第三方 API 文档
    └── operation_and_test_guide.md # 操作与测试指南
```

## 快速开始

### 1) 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2) 配置环境变量

复制并编辑配置：

```bash
cp .env.example .env
```

重点检查以下项：

- `MILVUS_URI`、`MILVUS_TOKEN`（若开启鉴权）
- `MILVUS_COLLECTION_NAME=ai_material_embedding`
- `MILVUS_VECTOR_DIM=2048`、`MILVUS_INDEX_TYPE=IVF_FLAT`
- `EMBEDDING_API_KEY`、`EMBEDDING_API_URL`（`/milvus/search` 与 `/milvus/hybrid-search` 必填）
- `MYSQL_*` 连接信息与表字段映射

### 3) 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## API 概览

对外接口封装 `pymilvus.MilvusClient`，Base Path: `/milvus`

| HTTP | 路径 | 对应 SDK |
|------|------|----------|
| POST | `/milvus/get` | `client.get()` |
| POST | `/milvus/insert` | `client.insert()` |
| POST | `/milvus/query` | `client.query()` |
| POST | `/milvus/search` | `client.search()` |
| POST | `/milvus/upsert` | `client.upsert()` |
| POST | `/milvus/hybrid-search` | `client.hybrid_search()` |
| POST | `/milvus/delete` | `client.delete()` |

示例（按主键查询）：

```bash
curl -X POST "http://127.0.0.1:8000/milvus/get" \
  -H "Content-Type: application/json" \
  -d '{"ids": [1001], "output_fields": ["primary_key", "material_id", "tenant_id"]}'
```

示例（文本检索，服务端自动调用火山 Embedding 再查 Milvus）：

```bash
curl -X POST "http://127.0.0.1:8000/milvus/search" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"type": "text", "text": "球员三步上篮得分"}],
    "limit": 5,
    "filter": "tenant_id == 10",
    "output_fields": ["material_id", "tenant_id", "tag"]
  }'
```

需在 `.env` 中配置 `EMBEDDING_API_KEY` 等，见 `.env.example`。

示例（混合检索）：

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
    "limit": 10
  }'
```

说明：`/milvus/search` 与 `/milvus/hybrid-search` 传**文本/图片**，无需传向量；`insert`/`upsert` 写入时 `embedding` 须为 **2048** 维。

## 离线同步脚本

全量同步：

```bash
python scripts/sync_mysql_to_milvus.py --mode full
```

增量同步（按 `id > last_id`）：

```bash
python scripts/sync_mysql_to_milvus.py --mode incremental
```

脚本输出为 JSON，包含 `total/success/failed/elapsed_seconds` 统计。

## 测试

```bash
pytest -q
```

- 操作与测试：`doc/operation_and_test_guide.md`
- **第三方 API 接口文档**：`doc/api_reference.md`
