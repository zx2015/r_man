# docs/design/feishu-integration — 飞书集成设计

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-16 | 初始版本 | Gemini CLI |

## 文档列表

- [DETAILED_DESIGN.md](DETAILED_DESIGN.md) — WebSocket 消息泵与队列调度设计

## 模块概述

该模块负责系统的外部通信，通过 WebSocket 接收用户指令并维持任务串行化。
