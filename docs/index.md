# r-man 项目文档总索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-15 | 初始版本，建立文档目录骨架 | GitHub Copilot |
| v1.1.0 | 2026-04-15 | 移除 CLI 相关需求，仅保留飞书交互入口；明确飞书配置必须包含 appId 和 appSecret | GitHub Copilot |
| v1.2.0 | 2026-04-15 | 新增安装工具需求，支持自动部署和配置校验；明确飞书应用创建由用户自行解决；首选 WebSocket 模式；添加 systemd 服务配置生成功能 | GitHub Copilot |
| v1.3.0 | 2026-04-15 | 明确与飞书间通信仅使用 WebSocket 模式 | GitHub Copilot |
| v1.4.0 | 2026-04-15 | 移除 BR-001 系统告警实时推送和 BR-003 定时系统巡检报告需求 | GitHub Copilot |
| v1.5.0 | 2026-04-15 | 移除配置文件中的 RMAN.md 和 TOOLS.md 路径配置，改为固定放置在项目根目录 | GitHub Copilot |
| v1.6.0 | 2026-04-15 | 新增内存系统需求文档，添加 memory_dump 和 memory_get 工具 | GitHub Copilot |
| v1.7.0 | 2026-04-15 | 内存系统新增大模型summary和向量化处理功能，支持将对话内容总结后存储到知识库 | GitHub Copilot |
| v1.8.0 | 2026-04-15 | 内存系统新增话题检测与内存管理流程，明确memory_get在用户切换话题时的调用时机和流程 | GitHub Copilot |
| v1.9.0 | 2026-04-16 | memory 需求收敛到独立文档（REQ-CORE-002），并采用第二阶段方案（SQLite + 向量检索 + bge-m3） | GitHub Copilot |

## 项目简介

**r-man** 是一个通用 AI Agent，可以处理多种任务，通过深度融合推理能力与系统工具，完成全自动化的任务执行工作。

## 文档目录

```
docs/
├── index.md                     # 本文件，项目文档总索引
├── requirements/                # 需求文档
│   ├── index.md
│   ├── core-agent/              # 核心 Agent 框架需求
│   │   ├── index.md
│   │   ├── REQ-CORE-001.md      # ReAct 框架 + 内置工具 + 动态 Prompt
│   │   └── REQ-CORE-002.md      # 内存管理独立需求文档（SQLite+向量检索+bge-m3）
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
| 核心 Agent 需求 | [requirements/core-agent/REQ-CORE-001.md](requirements/core-agent/REQ-CORE-001.md) | ReAct 框架、内置工具集、动态 System Prompt、运行配置 |
| Memory 管理需求 | [requirements/core-agent/REQ-CORE-002.md](requirements/core-agent/REQ-CORE-002.md) | memory_dump/memory_get、SQLite+向量检索、bge-m3 配置 |
| 飞书集成需求 | [requirements/feishu-integration/REQ-FEISHU-001.md](requirements/feishu-integration/REQ-FEISHU-001.md) | 飞书双向通信能力（v1.9.0，仅 WebSocket，已移除告警推送/定时报告） |
| 技术架构概览 | docs/design/ARCH_OVERVIEW.md | ⏳ 待创建 |

## 其他资源

- [study/](../study/) — 技术方案预研与对比分析
- [experience/](../experience/) — 工程经验与踩坑记录
- [AGENTS.md](../AGENTS.md) — Agent 工程准则
