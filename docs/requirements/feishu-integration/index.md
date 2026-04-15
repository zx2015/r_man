# docs/requirements/feishu-integration — 索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-15 | 初始版本，创建目录索引 | GitHub Copilot |

## 目录内容

| 文件 | 版本 | 说明 |
| :--- | :--- | :--- |
| [REQ-FEISHU-001.md](REQ-FEISHU-001.md) | v1.1.0 | 飞书通信能力需求文档（基础双向通信：告警推送、指令接收转发、定时报告；已移除人工审批门禁与复杂角色体系） |

## 模块概述

本目录包含 r-man Agent 与飞书（Lark）平台集成的所有需求文档。核心目标：为 r-man 建立双向实时通信通道，涵盖：
- **主动推送**: 告警消息、每日巡检报告
- **指令入口**: 接收飞书自然语言消息，转发至 ReAct Agent 执行，结果回复飞书

实际执行能力依赖核心 Agent 框架：[docs/requirements/core-agent/REQ-CORE-001.md](../core-agent/REQ-CORE-001.md)

**关联设计文档**: [docs/design/feishu-integration/](../../design/feishu-integration/)（待创建）
