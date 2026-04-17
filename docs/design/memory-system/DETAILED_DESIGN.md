# DETAILED_DESIGN: 内存系统存储设计

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-16 | 初始版本，定义 SQLite 向量存储与检索流程 | Gemini CLI |

## 1. 模块职责

内存系统（Memory System）负责将 Agent 的对话片段进行总结、向量化，并提供基于语义相似度的检索能力，实现 Agent 的“长期记忆”。

## 2. 存储选型：SQLite + sqlite-vec

为了保持 r-man 的轻量级与易部署性，采用 SQLite 数据库配合向量搜索插件。

### 2.1 数据库 Schema

```sql
-- 内存条目元数据表
CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,           -- UUID
    tag TEXT,                      -- 标签（如：topic-switch）
    description TEXT,              -- 用户或系统生成的描述
    summary TEXT NOT NULL,         -- 核心内容的总结文本
    full_content TEXT NOT NULL,    -- 完整的对话 JSON 序列
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME            -- 过期时间，默认 7 天
);

-- 向量索引表 (基于 sqlite-vec)
CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[1024]          -- 对应 BGE-M3 的维度
);
```

## 3. 核心流程

### 3.1 内存转储 (memory_dump)

1.  **总结**: 调用 LLM 对当前 Session 的对话内容进行摘要（保留关键决策、命令执行结果、用户偏好）。
2.  **向量化**: 调用 Embedding API（BGE-M3）将摘要文本转为 1024 维向量。
3.  **持久化**:
    - 在 `memory_entries` 插入元数据与总结。
    - 在 `memory_vectors` 插入对应的向量。
4.  **返回**: 返回内存 ID。

### 3.2 内存检索 (memory_get)

1.  **预处理**: 若输入是 `query`，则将其向量化。
2.  **检索**: 
    - 执行向量相似度搜索（Cosine Similarity）。
    - 支持结合 `tag` 进行元数据过滤。
3.  **重排序 (可选)**: 根据 `created_at` 对 Top-K 结果进行微调。
4.  **返回**: 提取 `summary` 和 `full_content` 返回给 Agent。

## 4. Embedding 配置与适配

```yaml
memory:
  embedding:
    base_url: "${EMBEDDING_BASE_URL}"
    api_key: "${EMBEDDING_API_KEY}"
    model: "BAAI/bge-m3"
```

通过 `EmbeddingClient` 类封装对 BGE-M3 的调用，支持异步批量请求以提高效率。

## 5. 维护任务

- **过期清理**: 系统启动时，自动删除 `expires_at < NOW()` 的记录。
- **空间控制**: 超过 100 条记录时，按 LRU（最近最少使用）原则清理。

---
> 下一步：[飞书集成详细设计](../feishu-integration/DETAILED_DESIGN.md)
