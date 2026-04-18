# DETAILED_DESIGN: 飞书消息卡片与 Token 统计系统

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本，定义卡片发送逻辑与统计累加器 | Gemini CLI |

## 1. 统计累加逻辑

### 1.1 数据结构
在 `AgentRunner.run` 方法中初始化 `total_usage` 字典：
```python
total_usage = {
    "model": config.llm.model,
    "input": 0,
    "output": 0
}
```

### 1.2 累加时机
每一轮 LLM 响应返回后：
1.  从 `OpenAI.usage` 提取 `prompt_tokens` 和 `completion_tokens`。
2.  分别累加至 `total_usage["input"]` 和 `total_usage["output"]`。
3.  即便发生 `Action` 迭代，统计也会一直累积，直到任务终点。

## 2. 卡片 UI 组件化设计

### 2.1 增强型结果卡片结构
```json
{
  "header": { "template": "green", "title": { "tag": "plain_text", "content": "🤖 R-MAN 执行报告" } },
  "elements": [
    {
      "tag": "div",
      "text": { "tag": "lark_md", "content": "{final_answer}" }
    },
    { "tag": "hr" },
    {
      "tag": "column_set",
      "flex_mode": "stretch",
      "columns": [
        {
          "tag": "column", "width": "weighted", "weight": 1,
          "elements": [ { "tag": "div", "text": { "tag": "lark_md", "content": "🏷 **Model**: {model}" } } ]
        },
        {
          "tag": "column", "width": "weighted", "weight": 1,
          "elements": [ { "tag": "div", "text": { "tag": "lark_md", "content": "📊 **Usage**: In {input} / Out {output}" } } ]
        }
      ]
    },
    {
      "tag": "note",
      "elements": [ { "tag": "plain_text", "content": "⏱ {time}" } ]
    }
  ]
}
```

## 3. 卡片格式化流水线 (Formatting Pipeline)

为了保证发送成功率及视觉一致性，所有 Markdown 内容在发送前必须经过 `CardFormatter`。

### 3.1 处理阶段
1.  **Table Budgeting (预算阶段)**:
    - 统计不在代码块内的 `|---|` 表格。
    - 超过阈值 (`config.feishu.card_table_limit`) 的表格被自动降级为 ` ``` `。
    - 单个表格列数若超过 `config.feishu.card_column_limit`，执行硬截断。
    - `page_size` 默认为 **10**。
    - **List Spacer**: `processed = re.sub(r'([^\n])\n([-*] |\d+\. )', r'\1\n\n\2', processed)`。
    - **Bold Tightener**: `processed = re.sub(r'\*\*\s+(.*?)\s+\*\*', r'**\1**', processed)`。
    - **Blockquote Shim**: 将 `> ` 替换为 `▎ `。
3.  **Schema 2.0 Structural Wrap (结构阶段)**:
    - 将处理后的文本嵌入 `lark_md` 或 `markdown` 组件。

### 3.2 样式优化器 (MarkdownOptimizer)
负责正则清洗与语法对齐，包含：
- **List Spacer**: 在列表项前注入空行。
- **Bold Tightener**: 收紧加粗符号内的空格。
- **Blockquote Shim**: 将标准引用转为可视化条。

### 3.3 自动转换器 (Auto-Converters)
1.  **Markdown Table to Native**:
    - **Step 1**: 使用正则 `\|(.+)\|\n\|[:\-\s|]+\|\n((?:\|.*\|\n?)*)` 捕捉表格块。
    - **Step 2**: 提取第一行为 `columns`。
    - **Step 3**: 循环解析后续行为 `rows` 字典。
    - **Step 4**: 返回飞书卡片 2.0 兼容的 `table` 元素。
2.  **Header Mood Inference**:
    - 检查文本前 5 个字符。
    - 映射：`{"✅": "green", "❌": "red", "⚠️": "orange", "ℹ️": "blue"}`。

## 4. 日志管理与轮转方案 (Logging Strategy)

系统弃用原始的 systemd 文件重定向，改由 Loguru 全面接管日志生命周期：

### 4.1 日志分类
| 文件 | 级别 | 轮转策略 | 保留策略 |
| :--- | :--- | :--- | :--- |
| `logs/rman.log` | DEBUG | 10 MB | 3 份 |
| `logs/audit.log` | INFO | 10 MB | 3 份 |

### 4.2 导出逻辑
- 所有日志同时输出到 `sys.stderr`，由 `journald` 捕获以支持 `journalctl` 查询。
- 使用 `enqueue=True` 确保在大并发或网络阻塞时的线程安全性。

---
> 关联需求: [REQ-MESSAGING-001](../../requirements/feishu-integration/REQ-MESSAGING-001.md)
