# docs/requirements — 需求文档索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-15 | 初始版本，创建需求目录总索引 | GitHub Copilot |

## 目录结构

```
docs/requirements/
└── feishu-integration/
    ├── index.md                  # 飞书集成模块索引
    └── REQ-FEISHU-001.md         # 飞书通信能力需求文档
```

## 需求模块清单

| 模块 | 目录 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| 核心 Agent 框架 | [core-agent/](core-agent/index.md) | ✅ 已完成 | ReAct Agent 框架、内置工具集（read_file/write_file/exec 等）、动态 System Prompt（RMAN.md + TOOL.md） |
| 飞书通信集成 | [feishu-integration/](feishu-integration/index.md) | ✅ 已完成（v1.1.0） | r-man 与飞书平台双向通信能力，含告警推送、指令接收、定时报告 |

## 关联文档

- [docs/index.md](../index.md) — 项目文档总索引
- [docs/design/](../design/) — 技术设计文档（待创建）
