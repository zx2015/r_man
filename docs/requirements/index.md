# docs/requirements — 需求文档总索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.2.0 | 2026-04-17 | 模块化重构，增加消息卡片与 Token 统计需求 | Gemini CLI |

## 核心推理系统

| 模块 | 需求文档 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| **Agent 框架** | [core-agent/REQ-CORE-001.md](core-agent/REQ-CORE-001.md) | ✅ 已完成 | ReAct 状态机、内置工具集定义、并发约束 |
| **Prompt 系统** | [core-agent/REQ-CORE-003.md](core-agent/REQ-CORE-003.md) | ✅ 已完成 | 动态章节组装、标签化交互、环境信息注入 |

## 飞书集成系统

| 模块 | 需求文档 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| **通信通道** | [feishu-integration/REQ-FEISHU-001.md](feishu-integration/REQ-FEISHU-001.md) | ✅ 已完成 | WebSocket 链路、消息泵、单用户授权 |
| **消息交互格式** | [feishu-integration/REQ-MESSAGING-001.md](feishu-integration/REQ-MESSAGING-001.md) | ✅ 已完成 | 交互式卡片视觉设计、Token 消耗统计、模型标识 |

---
> 关联设计：[docs/design/index.md](../design/index.md)
