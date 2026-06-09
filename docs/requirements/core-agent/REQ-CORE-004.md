# REQ-CORE-004: AgentRunner 优雅超限退出与主动收尾总结

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-06-09 | 初始版本，定义 N+1 轮收尾总结需求 | GitHub Copilot |

---

## 1. 背景与问题

### 1.1 当前行为

`AgentRunner` 的 ReAct 循环受 `config.agent.max_iterations`（默认 20）控制。当触发以下两种退出条件时，系统直接调用 `_build_progress_summary()` 生成摘要并返回：

| 退出条件 | 触发位置 | 当前输出 |
| :--- | :--- | :--- |
| 耗尽最大迭代次数 | 循环结束后 | `⚠️ 任务已达最大执行步数…` + summarizer 摘要 |
| 逻辑死锁（连续 3 轮无输出） | 循环内部 | `⚠️ 任务执行遇到障碍…` + summarizer 摘要 |

### 1.2 问题

1. **被动归纳**：`_build_progress_summary()` 使用 summarizer 模型，只能被动提取已有信息，无法主动分析任务状态或给出后续行动建议。
2. **信息价值低**：用户得到的是一段摘要文字，不包含"下一步应该怎么做"的指导。
3. **两条路径不一致**：死锁路径和超限路径各自独立 `return`，行为不统一。

### 1.3 目标

在正常 ReAct 循环（N 轮）结束后，额外进行 **1 轮收尾对话**（第 N+1 轮），由**主模型**以完整上下文为依据，主动生成：

- 当前任务的进展总结（已完成什么、还差什么）
- 具体的下一步行动建议（自然语言描述）

---

## 2. 功能需求

### FR-001: N+1 轮收尾机制

- **触发条件**：以下任意一种情况发生时，均进入第 N+1 轮收尾阶段：
  1. ReAct 循环耗尽 `max_iterations` 轮次（正常超限）
  2. 连续 `consecutive_empty >= 3` 轮无有效输出（逻辑死锁）
- **执行内容**：向主模型发起一次独立的 LLM 调用，prompt 包含：
  - 任务终止原因说明（超限 或 死锁）
  - 已执行的轮次数量
  - 要求：以自然语言总结当前进展，并给出下一步建议
- **输出格式**：自然语言 Markdown，包含两个部分：
  1. **当前进展**：已完成了什么，还差什么
  2. **下一步建议**：用户如果想继续，具体应该做什么

### FR-002: 收尾轮与正常循环解耦

- 收尾轮**不属于** ReAct 循环，不计入 `max_iterations`
- 收尾轮的 prompt **不写入** `self.messages`（不污染 ReAct 轨迹，不持久化）
- 收尾轮传入 `tools=None`，禁止模型在此轮调用工具
- 若模型意外返回 tool_call，忽略之，只取 `.content`

### FR-003: Token 用量追踪

- 收尾轮消耗的 token（input + output）必须累加至 `total_usage`，与正常轮次一致

### FR-004: 降级处理

- 收尾轮 LLM 调用失败时（如 context 超限、网络超时等），必须降级到现有的 `_build_progress_summary()` 方法，保证系统始终有输出
- 降级后的输出前缀应注明"（收尾总结生成失败，以下为自动摘要）"

### FR-005: 动态跟随配置

- N+1 中的 N 等于 `config.agent.max_iterations`，不硬编码
- 若配置改为 30，则系统运行 30+1 轮；改为 10，则运行 10+1 轮

---

## 3. 非功能需求

### NFR-001: 收尾轮超时

- 收尾轮应遵循与正常轮次相同的 LLM 超时配置，不单独设置超时

### NFR-002: 日志

- 收尾轮开始前记录 `INFO` 日志，说明触发原因和当前迭代数
- 降级时记录 `WARNING` 日志

---

## 4. 退出路径统一设计

```
正常超限路径:
  for i in range(max_iterations): ... → 循环自然结束
  exit_reason = "max_iterations"
  → _run_closing_summary(exit_reason, total_usage)

逻辑死锁路径:
  for i in range(max_iterations):
      if consecutive_empty >= 3:
          exit_reason = "deadlock"
          break   ← 不再 return，统一跳出循环
  → _run_closing_summary(exit_reason, total_usage)
```

两条路径收敛到同一个 `_run_closing_summary()` 方法，消除代码重复。

---

## 5. Closing Prompt 示例

### 超限触发时

```
你已执行了 {n} 轮推理步骤（系统最大步数限制），任务尚未完全完成。

请根据以上完整的对话记录，用自然语言完成以下两件事：

1. **当前进展总结**：到目前为止，你已经完成了什么？任务还差哪些步骤没有完成？
2. **下一步建议**：如果用户希望继续这个任务，他/她应该做什么？请给出具体、可操作的建议。

请用清晰的 Markdown 格式回复，不要调用任何工具。
```

### 死锁触发时

```
你在最近连续 {n} 轮推理中未能产生有效输出（既没有调用工具，也没有给出结论），系统已提前终止任务。

请根据以上完整的对话记录，用自然语言完成以下两件事：

1. **当前进展总结**：到目前为止，你已经完成了什么？任务还差哪些步骤没有完成？
2. **下一步建议**：如果用户希望继续这个任务，他/她应该做什么？请给出具体、可操作的建议。

请用清晰的 Markdown 格式回复，不要调用任何工具。
```

---

## 6. 验收标准

| 编号 | 验收条件 |
| :--- | :--- |
| AC-001 | 超限退出时，用户收到包含"当前进展"和"下一步建议"两部分内容的自然语言回复 |
| AC-002 | 逻辑死锁退出时，用户同样收到相同格式的收尾回复 |
| AC-003 | 收尾轮 token 正确计入 `total_usage`（验证：对比收尾前后的 input/output 数字） |
| AC-004 | 收尾轮 LLM 失败时，自动降级到 `_build_progress_summary` 且有 WARNING 日志 |
| AC-005 | 修改 `config.agent.max_iterations = 5`，系统运行 5+1 轮后退出（验证：日志显示 iteration 6 为收尾轮） |
| AC-006 | 收尾轮 prompt 不出现在 session history 中（验证：`session_search` 工具搜索不到收尾 prompt 原文） |

---

## 7. 关联文档

- 核心 Agent 需求: [REQ-CORE-001.md](REQ-CORE-001.md)
- 核心 Agent 详细设计: [../../design/core-agent/DETAILED_DESIGN.md](../../design/core-agent/DETAILED_DESIGN.md)
