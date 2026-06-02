# Milvus 向量服务 API 接口文档

本文档面向第三方调用方，说明 HTTP 接口的请求参数、返回结构及使用约束。

---

## 1. 基本信息

| 项目 | 说明 |
|------|------|
| 协议 | HTTP/HTTPS |
| 数据格式 | `application/json` |
| 字符编码 | UTF-8 |
| 默认端口 | `8000`（以实际部署为准） |
| Base URL 示例 | `http://{host}:{port}` |
| 接口前缀 | `/milvus` |
| 在线文档 | 服务启动后访问 `{BaseURL}/docs`（Swagger UI） |

### 1.1 健康检查

**GET** `/health`

用于探测服务与 Milvus Collection 是否可用。

**请求参数**：无

**响应示例**：

```json
{
  "ok": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | `true` 表示 Milvus 中目标 Collection 存在且可连接 |

---

## 2. 数据模型（Collection Schema）

当前服务默认操作 Collection：`ai_material_embedding`（由服务端环境变量配置，调用方无需传 collection 名）。

| 字段名 | 类型 | 主键 | 说明 |
|--------|------|------|------|
| primary_key | INT64 | 是 | 主键，与业务侧 MySQL `id` 对应 |
| embedding | FLOAT_VECTOR | - | 向量，维度 **2048** |
| material_id | INT32 | - | 素材 ID |
| tenant_id | INT32 | - | 租户 ID |
| embedding_model | VARCHAR | - | 向量模型名称 |
| content_hash | VARCHAR | - | 内容哈希 |
| uid | INT16 | - | 用户/业务 UID |
| tag | VARCHAR | - | 标签 |
| create_time | INT32 | - | 创建时间（Unix 时间戳，秒） |
| update_time | INT32 | - | 更新时间（Unix 时间戳，秒） |

**重要约束**：

- `embedding` 长度必须为 **2048**，否则写入/检索会失败。
- 向量索引类型为 **IVF_FLAT**，默认度量方式为 **COSINE**（由服务端配置）。

---

## 3. 通用说明

### 3.1 请求头

```http
Content-Type: application/json
```

### 3.2 HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 422 | 请求体校验失败（参数缺失、类型错误等） |
| 500 | 服务端异常（如 Milvus 连接失败、Collection 不存在） |

校验失败时 FastAPI 返回示例：

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "ids"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### 3.3 与 pymilvus SDK 的对应关系

| HTTP 接口 | pymilvus MilvusClient 方法 |
|-----------|---------------------------|
| POST `/milvus/get` | `client.get()` |
| POST `/milvus/insert` | `client.insert()` |
| POST `/milvus/query` | `client.query()` |
| POST `/milvus/search` | `client.search()` |
| POST `/milvus/upsert` | `client.upsert()` |
| POST `/milvus/hybrid-search` | `client.hybrid_search()` |
| POST `/milvus/delete` | `client.delete()` |

### 3.4 标量过滤表达式（filter）

用于 `query`、`search`、`delete` 等接口的 `filter` 字段，语法遵循 Milvus 布尔表达式，例如：

- `tenant_id == 10`
- `material_id in [1, 2, 3]`
- `tenant_id == 10 and tag != ""`

---

## 4. 接口详情

---

### 4.1 按主键获取 — `POST /milvus/get`

封装 `MilvusClient.get()`，根据主键列表批量查询实体。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | int[] | 是 | 主键列表，至少 1 个 |
| output_fields | string[] | 否 | 需要返回的字段名；不传时由 Milvus 返回默认字段集 |

#### 请求示例

```json
{
  "ids": [1001, 1002],
  "output_fields": [
    "primary_key",
    "material_id",
    "tenant_id",
    "embedding_model",
    "content_hash",
    "uid",
    "tag",
    "create_time",
    "update_time"
  ]
}
```

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| data | object[] | 查询到的实体列表 |

#### 响应示例

```json
{
  "data": [
    {
      "primary_key": 1001,
      "material_id": 10,
      "tenant_id": 1,
      "embedding_model": "text-embedding-3-small",
      "content_hash": "abc123",
      "uid": 7,
      "tag": "demo",
      "create_time": 1717000000,
      "update_time": 1717001000
    }
  ]
}
```

**说明**：若需返回向量，请在 `output_fields` 中包含 `embedding`。

---

### 4.2 插入 — `POST /milvus/insert`

封装 `MilvusClient.insert()`。**主键已存在时会失败**（与 upsert 不同）。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| data | object[] | 是 | 待插入实体列表，至少 1 条；每条为字段名到值的映射 |

#### 单条实体推荐字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| primary_key | int | 是 | 主键 |
| embedding | float[] | 是 | 2048 维向量 |
| material_id | int | 否 | 默认由 Milvus/业务处理 |
| tenant_id | int | 否 | 同上 |
| embedding_model | string | 否 | 同上 |
| content_hash | string | 否 | 同上 |
| uid | int | 否 | 同上 |
| tag | string | 否 | 同上 |
| create_time | int | 否 | Unix 秒级时间戳 |
| update_time | int | 否 | Unix 秒级时间戳 |

#### 请求示例

```json
{
  "data": [
    {
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
    }
  ]
}
```

> 示例中 `embedding` 仅展示前 2 维，实际须为 **2048** 维。

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| result | object | pymilvus `insert` 的原始返回（通常含 `insert_count` 等） |

#### 响应示例

```json
{
  "result": {
    "insert_count": 1,
    "ids": [2001]
  }
}
```

---

### 4.3 标量查询 — `POST /milvus/query`

封装 `MilvusClient.query()`，按布尔表达式过滤，**不做向量相似度计算**。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| filter | string | 是 | Milvus 过滤表达式 |
| output_fields | string[] | 否 | 返回字段列表 |
| limit | int | 否 | 最大返回条数，≥1 |

#### 请求示例

```json
{
  "filter": "tenant_id == 1 and material_id == 10",
  "output_fields": ["primary_key", "material_id", "tenant_id", "tag"],
  "limit": 100
}
```

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| data | object[] | 满足条件的实体列表 |

#### 响应示例

```json
{
  "data": [
    {
      "primary_key": 1001,
      "material_id": 10,
      "tenant_id": 1,
      "tag": "demo"
    }
  ]
}
```

---

### 4.4 向量相似检索 — `POST /milvus/search`

封装 `MilvusClient.search()`。**调用方传入原始文本或图片 URL，由本服务调用火山多模态 Embedding API 生成 2048 维向量后再检索。**

> **注意**：本接口**不需要**传入 `data` 向量；`input` 为待检索的原始内容，不是向量。

#### 服务端向量化流程

1. 接收 `input`（文本 / 图片 URL）
2. 调用 `https://operator.las.cn-beijing.volces.com/api/v1/embeddings/multimodal`
3. 得到 2048 维向量后执行 Milvus `search`

需在部署环境配置：`EMBEDDING_API_KEY`、`EMBEDDING_API_URL` 等（见 `.env.example`）。

#### 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| input | object[] | 是 | - | 多模态输入列表，结构同火山 Embedding API（见下表） |
| limit | int | 否 | 10 | TopK，范围 1~1000 |
| filter | string | 否 | `""` | Milvus 标量过滤表达式 |
| output_fields | string[] | 否 | null | 命中结果需返回的标量字段 |
| search_params | object | 否 | null | Milvus 检索参数；不传则用服务端默认（IVF_FLAT + COSINE + nprobe） |
| model | string | 否 | 服务端配置 | Embedding 模型，默认 `doubao-embedding-vision-250615` |
| dimensions | int | 否 | 2048 | 向量维度 |

#### input[] 单条结构（EmbeddingInputItem）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | `text` 或 `image_url` |
| text | string | type=text 时必填 | 检索用文本 |
| image_url | object | type=image_url 时必填 | `{"url": "https://..."}` |

**文本检索示例片段**：

```json
{"type": "text", "text": "球员三步上篮得分"}
```

**图片检索示例片段**：

```json
{"type": "image_url", "image_url": {"url": "https://example.com/test.jpg"}}
```

#### search_params 结构（可选）

```json
{
  "metric_type": "COSINE",
  "params": {
    "nprobe": 16
  }
}
```

| 字段 | 说明 |
|------|------|
| metric_type | 距离度量，需与索引一致，默认 `COSINE` |
| params.nprobe | IVF 检索探测桶数量，越大召回越高、延迟越大 |

#### 请求示例（文本检索）

```json
{
  "input": [
    {"type": "text", "text": "球员三步上篮得分"}
  ],
  "limit": 5,
  "filter": "tenant_id == 1",
  "output_fields": ["material_id", "tenant_id", "tag", "content_hash"],
  "search_params": {
    "metric_type": "COSINE",
    "params": { "nprobe": 16 }
  }
}
```

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| data | array | pymilvus `search` 原始结果 |
| query_vector_count | int | 本次生成的查询向量条数 |

#### 响应示例（单查询向量）

```json
{
  "data": [
    [
      {
        "id": 1001,
        "distance": 0.92,
        "entity": {
          "material_id": 10,
          "tenant_id": 1,
          "tag": "demo",
          "content_hash": "abc123"
        }
      },
      {
        "id": 1002,
        "distance": 0.88,
        "entity": {
          "material_id": 11,
          "tenant_id": 1,
          "tag": "demo2",
          "content_hash": "def456"
        }
      }
    ]
  ],
  "query_vector_count": 1
}
```

| 命中项字段 | 说明 |
|------------|------|
| id | 命中的 `primary_key` |
| distance | 相似度/距离分数（COSINE 下越大通常越相似，以 Milvus 版本行为为准） |
| entity | `output_fields` 指定的标量字段 |

---

### 4.5 插入或更新 — `POST /milvus/upsert`

封装 `MilvusClient.upsert()`。主键存在则更新，不存在则插入。**生产环境推荐使用此接口。**

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| data | object[] | 是 | 实体列表，字段要求同 [4.2 插入](#42-插入--post-milvusinsert) |

#### 请求示例

```json
{
  "data": [
    {
      "primary_key": 1001,
      "embedding": [0.1, 0.2],
      "material_id": 10,
      "tenant_id": 1,
      "embedding_model": "text-embedding-3-small",
      "content_hash": "updated-hash",
      "uid": 2,
      "tag": "tag-updated",
      "create_time": 1717000000,
      "update_time": 1717099999
    }
  ]
}
```

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| result | object | pymilvus `upsert` 原始返回（通常含 `upsert_count` 等） |

#### 响应示例

```json
{
  "result": {
    "upsert_count": 1
  }
}
```

---

### 4.6 混合检索 — `POST /milvus/hybrid-search`

封装 `MilvusClient.hybrid_search()`。每一路检索的 `reqs[].input` 为**原始文本/图片**，由服务端向量化后再做多路融合重排。

> **注意**：`reqs[].input` 不是向量；结构与 [4.4](#44-向量相似检索--post-milvussearch) 的 `input` 相同。

#### 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| reqs | object[] | 是 | - | 多路检索配置，至少 1 条 |
| ranker_type | string | 否 | `weighted` | `weighted` 或 `rrf` |
| ranker_weights | float[] | 条件 | null | `weighted` 时必填，长度 = `reqs` 数量 |
| ranker_k | int | 否 | null | `rrf` 时可选，默认 60 |
| limit | int | 否 | 10 | 最终 TopK |
| output_fields | string[] | 否 | null | 返回标量字段 |

#### reqs[] 单条结构（HybridSearchReqItem）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| input | object[] | 是 | - | 该路检索的原始内容（text / image_url） |
| anns_field | string | 否 | `embedding` | Milvus 向量字段名 |
| param | object | 否 | `{}` | Milvus 检索参数 |
| limit | int | 否 | 10 | 该路 TopK |
| model | string | 否 | 服务端配置 | 覆盖 Embedding 模型 |
| dimensions | int | 否 | 2048 | 覆盖向量维度 |

#### 请求示例（文本单路）

```json
{
  "reqs": [
    {
      "input": [{"type": "text", "text": "球员三步上篮得分"}],
      "anns_field": "embedding",
      "param": {"metric_type": "COSINE", "params": {"nprobe": 16}},
      "limit": 20
    }
  ],
  "ranker_type": "weighted",
  "ranker_weights": [1.0],
  "limit": 10,
  "output_fields": ["material_id", "tenant_id", "tag"]
}
```

#### 请求示例（双路：文本 + 另一段文本）

```json
{
  "reqs": [
    {
      "input": [{"type": "text", "text": "篮球上篮"}],
      "param": {"metric_type": "COSINE", "params": {"nprobe": 16}},
      "limit": 20
    },
    {
      "input": [{"type": "text", "text": "足球射门"}],
      "param": {"metric_type": "COSINE", "params": {"nprobe": 16}},
      "limit": 20
    }
  ],
  "ranker_type": "weighted",
  "ranker_weights": [0.7, 0.3],
  "limit": 10,
  "output_fields": ["material_id", "tenant_id"]
}
```

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| data | array | pymilvus `hybrid_search` 原始结果 |

#### 响应示例

```json
{
  "data": [
    [
      {
        "id": 1001,
        "distance": 0.85,
        "entity": {
          "material_id": 10,
          "tenant_id": 1,
          "tag": "demo"
        }
      }
    ]
  ]
}
```

---

### 4.7 删除 — `POST /milvus/delete`

封装 `MilvusClient.delete()`。`ids` 与 `filter` **至少提供一个**。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | int[] | 条件 | 按主键删除 |
| filter | string | 条件 | 按表达式批量删除，如 `tenant_id == 99` |

#### 请求示例（按主键）

```json
{
  "ids": [1001, 1002]
}
```

#### 请求示例（按条件）

```json
{
  "filter": "tenant_id == 99"
}
```

#### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| result | object | pymilvus `delete` 原始返回 |

#### 响应示例

```json
{
  "result": {
    "delete_count": 2
  }
}
```

---

## 5. 典型调用流程

### 5.1 写入素材向量

```
POST /milvus/upsert  →  写入或更新一条/批量向量数据
POST /milvus/get     →  校验写入结果（可选）
```

### 5.2 相似素材检索

```
POST /milvus/search  →  传入文本/图片 input，服务端向量化后检索 + tenant 过滤 + TopK
```

### 5.3 按业务条件查元数据（不做向量检索）

```
POST /milvus/query   →  filter 指定 tenant_id / material_id 等
```

---

## 6. 错误与排查

| 现象 | 可能原因 | 建议 |
|------|----------|------|
| 连接 Milvus 失败 | URI/Token 配置错误或服务不可达 | 检查部署环境变量 `MILVUS_URI`、`MILVUS_TOKEN` |
| Collection 不存在 | 未在 Milvus 创建 `ai_material_embedding` | 先在 Milvus 侧创建集合并建索引 |
| 向量维度错误 | `embedding` 长度不是 2048 | 确认 embedding 模型输出维度 |
| insert 失败但 upsert 成功 | 主键冲突 | 改用 `upsert` |
| hybrid-search 422 | `weighted` 模式未传 `ranker_weights` 或权重数量与 reqs 不一致 | 检查 ranker 参数 |
| search 结果为空 | filter 过严或集合无数据 | 放宽 filter 或先 query 确认数据量 |
| search/hybrid-search 500 | `EMBEDDING_API_KEY` 未配置或火山 API 失败 | 检查 Embedding 环境变量与网络 |
| 误传 `data` 向量字段 | 旧版接口已废弃 | 改用 `input` 传文本/图片 |

---

## 7. 附录：curl 快速验证

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 按主键查询
curl -X POST "http://127.0.0.1:8000/milvus/get" \
  -H "Content-Type: application/json" \
  -d '{"ids":[1],"output_fields":["primary_key","tenant_id","tag"]}'

# 文本向量检索（服务端自动向量化）
curl -X POST "http://127.0.0.1:8000/milvus/search" \
  -H "Content-Type: application/json" \
  -d '{"input":[{"type":"text","text":"球员三步上篮得分"}],"limit":5,"filter":"tenant_id == 1"}'

# 混合检索
curl -X POST "http://127.0.0.1:8000/milvus/hybrid-search" \
  -H "Content-Type: application/json" \
  -d '{"reqs":[{"input":[{"type":"text","text":"球员三步上篮得分"}],"limit":20}],"ranker_type":"weighted","ranker_weights":[1.0],"limit":10}'
```

---

## 8. 版本信息

| 项目 | 值 |
|------|-----|
| API 版本 | 0.2.0 |
| 默认 Collection | ai_material_embedding |
| 向量维度 | 2048 |
| 索引类型 | IVF_FLAT |
| 度量方式 | COSINE |

文档与代码不一致时，以实际部署的服务行为及 `/docs` 为准。
