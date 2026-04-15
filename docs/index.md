# r-man 项目文档总索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-15 | 初始版本，建立文档目录骨架 | GitHub Copilot |

## 项目简介

**r-man** 是一个用来维护 Linux 系统的 AI Agent，通过深度融合推理能力与系统工具，完成全自动化的 Linux 系统维护工作。

## 文档目录

```
docs/
├── index.md                     # 本文件，项目文档总索引
├── requirements/                # 需求文档
│   ├── index.md
│   ├── core-agent/              # 核心 Agent 框架需求
│   │   ├── index.md
│   │   └── REQ-CORE-001.md      # ReAct 框架 + 内置工具 + 动态 Prompt
│   └── feishu-integration/      # 飞书通信集成需求
│       ├── index.md
│       └── REQ-FEISHU-001.md    # 飞书双向通信能力（v1.1.0）
└── design/                      # 技术设计文档（待创建）
    ├── ARCH_OVERVIEW.md         # 整体架构概览（待创建）
    ├── core-agent/              # 核心 Agent 详细设计（待创建）
    └── feishu-integration/      # 飞书集成详细设计（待创建）
```

## 快速导航

| 文档类型 | 路径 | 说明 |
| :--- | :--- | :--- |
| 需求文档总览 | [requirements/index.md](requirements/index.md) | 所有功能模块的需求清单 |
| 核心 Agent 需求 | [requirements/core-agent/REQ-CORE-001.md](requirements/core-agent/REQ-CORE-001.md) | ReAct 框架、内置工具集、动态 System Prompt |
| 飞书集成需求 | [requirements/feishu-integration/REQ-FEISHU-001.md](requirements/feishu-integration/REQ-FEISHU-001.md) | 飞书双向通信能力（v1.1.0） |
| 技术架构概览 | docs/design/ARCH_OVERVIEW.md | ⏳ 待创建 |

## 其他资源

- [study/](../study/) — 技术方案预研与对比分析
- [experience/](../experience/) — 工程经验与踩坑记录
- [AGENTS.md](../AGENTS.md) — Agent 工程准则
