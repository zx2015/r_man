# docs/design/core-agent — 核心推理模块设计

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-16 | 初始版本 | Gemini CLI |

## 文档列表

- [DETAILED_DESIGN.md](DETAILED_DESIGN.md) — ReAct 引擎、Prompt 组装、工具注册详细设计

## 模块概述

该模块是 r-man 的“大脑”，负责：
1. 实现 ReAct 循环。
2. 动态读取并组装 System Prompt。
3. 管理上下文 Token 压力。
