# r-man 项目文档总索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v2.0.0 | 2026-04-17 | 全量同步 Phase 1-5 成果，建立完整的模块化导航 | Gemini CLI |

## 项目简介
**r-man** 是一个工业级的通用 AI Agent，通过 ReAct 推理循环深度粘合系统工具（Shell、文件、进程管理）与飞书交互能力，具备 200K 超长上下文管理及基于 SQLite+vec 的长期记忆系统。

## 文档目录结构
```text
docs/
├── requirements/           # 业务与功能需求 (What & Why)
│   ├── core-agent/         # 推理引擎、Prompt、审计与联网工具
│   ├── feishu-integration/ # 通信通道与消息卡片格式
│   └── memory-system/      # 长期记忆与向量化存储
└── design/                 # 技术架构与详细设计 (How)
    ├── ARCH_OVERVIEW.md    # 整体分层架构与数据流转
    ├── core-agent/         # 状态机、解析器与工具调度
    ├── feishu-integration/ # WebSocket 状态机与任务队列
    └── memory-system/      # SQLite 向量 Schema 与定时维护
```

## 快速导航

| 文档类型 | 入口路径 | 核心内容 |
| :--- | :--- | :--- |
| **整体架构** | [design/ARCH_OVERVIEW.md](design/ARCH_OVERVIEW.md) | **必读**。定义了 Interaction, Reasoning, Capability, Storage 四层架构。 |
| **需求清单** | [requirements/index.md](requirements/index.md) | 汇总了从 Agent 框架到 Tavily 联网的所有功能点。 |
| **设计总览** | [design/index.md](design/index.md) | 汇总了各模块的类图、时序图及核心逻辑实现。 |
| **用户手册** | [../USER_GUIDE.md](../USER_GUIDE.md) | 安装、配置、运行及安全操作指南。 |

---
## 辅助资源
- [AGENTS.md](../AGENTS.md) — 资深工程师角色的工程准则。
- [GEMINI.md](../GEMINI.md) — 项目指令集与三位一体同步规范。
- [.learnings/](../.learnings/index.md) — 持续进化的最佳实践与教训库。
