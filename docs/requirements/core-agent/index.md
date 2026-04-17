# docs/requirements/core-agent — 索引

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-15 | 初始版本，创建目录索引 | GitHub Copilot |
| v1.1.0 | 2026-04-16 | 同步 REQ 版本信息，统一“通用 AI Agent”表述 | GitHub Copilot |
| v1.2.0 | 2026-04-16 | 同步 memory 独立文档与第二阶段方案（SQLite + bge-m3）版本信息 | GitHub Copilot |

## 目录内容

| 文件 | 版本 | 说明 |
| :--- | :--- | :--- |
| [REQ-CORE-001.md](REQ-CORE-001.md) | v1.13.0 | r-man 核心 Agent 框架完整需求文档（ReAct 框架、内置工具集、动态 System Prompt 机制、LLM 后端适配、memory 配置入口） |
| [REQ-CORE-002.md](REQ-CORE-002.md) | v1.4.0 | r-man 内存系统独立需求文档（memory_dump/memory_get、话题管理、SQLite+向量检索、bge-m3 配置） |

## 模块概述

本目录包含 r-man 核心 Agent 引擎的所有需求文档，涵盖四大核心能力：

1. **ReAct Agent 执行框架**: Think → Act → Observe 多轮迭代，支持最大迭代次数与超时控制。
2. **内置工具集**: `read_file`、`write_file`、`replace`、`run_shell_command`、`process`、`memory_dump`、`memory_get`，统一注册机制，支持插件扩展。
3. **动态 System Prompt**: 从用户可编辑的 `RMAN.md`（角色与行为约束）和 `TOOLS.md`（工具使用说明）运行时动态组装 Prompt，无需修改代码即可定制 Agent 行为。
4. **内存系统**: 支持对话内存的保存、检索与恢复，实现话题切换时的上下文保持。

r-man 是一个通用 AI Agent，可以处理多种任务，通过深度融合推理能力与系统工具，完成全自动化的任务执行工作。

**关联文档**:
- 飞书通信集成需求: [docs/requirements/feishu-integration/REQ-FEISHU-001.md](../feishu-integration/REQ-FEISHU-001.md)
- 核心 Agent 详细设计: [docs/design/core-agent/](../../design/core-agent/)（待创建）
