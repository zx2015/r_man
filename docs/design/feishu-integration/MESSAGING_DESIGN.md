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

## 3. 实现考量
- **异步安全性**: 使用 `run_in_executor` 调用 `im.message.create` 以防止阻塞 IO。
- **错误处理**: 若 `usage` 字段缺失（某些 Provider 不返回），注脚将显示 `N/A`，不应导致程序崩溃。

---
> 关联需求: [REQ-MESSAGING-001](../../requirements/feishu-integration/REQ-MESSAGING-001.md)
