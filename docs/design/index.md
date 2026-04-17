# docs/design — 技术设计文档总索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.1.0 | 2026-04-17 | 模块化重构，增加消息卡片与 Token 统计设计 | Gemini CLI |

## 整体架构

- [ARCH_OVERVIEW.md](ARCH_OVERVIEW.md) — 逻辑分层、数据流转、物理目录结构。

## 模块详细设计

| 模块 | 设计文档 | 核心内容 |
| :--- | :--- | :--- |
| **核心推理 (ReAct)** | [core-agent/DETAILED_DESIGN.md](core-agent/DETAILED_DESIGN.md) | 状态机实现、LLM 后端适配、原生 Tool Calling 支持 |
| **Prompt 系统** | [core-agent/PROMPT_DESIGN.md](core-agent/PROMPT_DESIGN.md) | 标签约束 (<think>/<final>)、环境注入、热加载机制 |
| **飞书接入 (Channel)** | [feishu-integration/DETAILED_DESIGN.md](feishu-integration/DETAILED_DESIGN.md) | WebSocket 状态机、串行 FIFO 队列、优雅停机设计 |
| **消息交互 (Messaging)** | [feishu-integration/MESSAGING_DESIGN.md](feishu-integration/MESSAGING_DESIGN.md) | 卡片 JSON 模板、Token 统计累加器实现 |

---
> 关联需求：[docs/requirements/index.md](../requirements/index.md)
