# docs/design — 技术设计文档总索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.1.0 | 2026-04-17 | 模块化重构，增加消息卡片与 Token 统计设计 | Gemini CLI |
| v1.2.0 | 2026-06-09 | 更新子文档版本引用；新增 memory-system 入口 | GitHub Copilot |

## 整体架构

- [ARCH_OVERVIEW.md](ARCH_OVERVIEW.md) — 逻辑分层、数据流转、物理目录结构。

## 模块详细设计

| 模块 | 设计文档 | 版本 | 核心内容 |
| :--- | :--- | :--- | :--- |
| **核心推理 (ReAct)** | [core-agent/DETAILED_DESIGN.md](core-agent/DETAILED_DESIGN.md) | v2.2.0 | 状态机实现、LLM 后端适配、80/60 上下文压缩算法、N+1 收尾轮 |
| **Prompt 系统** | [core-agent/PROMPT_DESIGN.md](core-agent/PROMPT_DESIGN.md) | — | 标签约束 (<think>/<final>)、环境注入、热加载机制 |
| **飞书接入 (Channel)** | [feishu-integration/DETAILED_DESIGN.md](feishu-integration/DETAILED_DESIGN.md) | v2.1.0 | WebSocket 状态机、串行 FIFO 队列、进度心跳、优雅停机设计 |
| **消息交互 (Messaging)** | [feishu-integration/MESSAGING_DESIGN.md](feishu-integration/MESSAGING_DESIGN.md) | v2.0.0 | 卡片 Pipeline、双层大小保护、inferred_template、Token 统计累加器 |
| **审计日志** | [core-agent/AUDIT_DESIGN.md](core-agent/AUDIT_DESIGN.md) | — | 装饰器模式实现、独立日志 Sink 配置 |
| **长期记忆** | [memory-system/DETAILED_DESIGN.md](memory-system/DETAILED_DESIGN.md) | v2.2.0 | 向量存储、TTL 配置化、session history FTS5 |


---
> 关联需求：[docs/requirements/index.md](../requirements/index.md)
