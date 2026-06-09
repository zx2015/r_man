# DETAILED_DESIGN: 飞书消息卡片与 Token 统计系统

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本，定义卡片发送逻辑与统计累加器 | Gemini CLI |
| v2.0.0 | 2026-06-09 | 同步实际代码：wide_screen_mode、ensure_ascii 修复、18 KB 软限 + 28 KB 硬限双层保护、inferred_template 自动着色、usage 分栏展示 | GitHub Copilot |

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

### 3.1 `_send_card` 完整 Pipeline（v2.0.0）

```
content_md (原始 Markdown)
  │
  ├─ 1. 软限截断 (Soft Limit)
  │      if len(bytes) > 18 KB → 截至 UTF-8 安全边界 + 追加截断提示
  │
  ├─ 2. inferred_template 自动着色
  │      ✅ → green  ❌ → red  ⚠️ → orange  其他 → 入参 template
  │
  ├─ 3. CardFormatter.format_with_components(content_md)
  │      └─ 见 §3.2~§3.3
  │
  ├─ 4. usage 分栏注入（可选）
  │      若传入 usage → 附加 column_set（model / In tokens / Out tokens）
  │
  ├─ 5. wide_screen_mode = True
  │      "config": {"wide_screen_mode": true}
  │
  ├─ 6. ensure_ascii=False 序列化
  │      json.dumps(card_json, ensure_ascii=False)
  │      修复 CJK 字符被转义为 \uXXXX 导致飞书显示异常的问题
  │
  └─ 7. 硬限兜底 (Hard Limit)
         if len(bytes) > 28 KB → 降级为极简纯文本卡片 + ERROR 日志
```

### 3.2 双层大小保护

| 层级 | 阈值 | 对象 | 触发行为 | 日志级别 |
| :--- | :--- | :--- | :--- | :--- |
| 软限 (Soft Limit) | 18 KB | `content_md` 原始 Markdown（字节） | UTF-8 安全截断 + 追加截断说明 | WARNING |
| 硬限 (Hard Limit) | 28 KB | 完整卡片 JSON（序列化后字节） | 降级为纯文本极简卡片（仅保留前 1000 字符） | ERROR |

两层设计的意图：软限在内容层尽早截断，减少格式化开销；硬限在 JSON 层兜底，防止飞书 API 拒绝超大请求。

### 3.3 inferred_template 自动着色规则

`_send_card` 不要求调用方传入 `template`，而是根据 `content_md` 的首字符自动推断：

| content_md 前缀 | inferred_template |
| :--- | :--- |
| `✅` | `green` |
| `❌` | `red` |
| `⚠️` | `orange` |
| 其他 / 未匹配 | 入参 `template`（默认 `"blue"`） |

### 3.4 CardFormatter 处理阶段

1.  **Table Budgeting (预算阶段)**:
    - 统计不在代码块内的 `|---|` 表格。
    - 超过阈值 (`config.feishu.card_table_limit`) 的表格被自动降级为 ` ``` `。
    - 单个表格列数若超过 `config.feishu.card_column_limit`，执行硬截断。
    - `page_size` 默认为 **10**。
2.  **MarkdownOptimizer 正则清洗**:
    - **List Spacer**: `processed = re.sub(r'([^\n])\n([-*] |\d+\. )', r'\1\n\n\2', processed)`。
    - **Bold Tightener**: `processed = re.sub(r'\*\*\s+(.*?)\s+\*\*', r'**\1**', processed)`。
    - **Blockquote Shim**: 将 `> ` 替换为 `▎ `。
3.  **Schema 2.0 Structural Wrap (结构阶段)**:
    - 将处理后的文本嵌入 `lark_md` 或 `markdown` 组件。

### 3.5 样式优化器 (MarkdownOptimizer)
负责正则清洗与语法对齐，包含：
- **List Spacer**: 在列表项前注入空行。
- **Bold Tightener**: 收紧加粗符号内的空格。
- **Blockquote Shim**: 将标准引用转为可视化条。

### 3.6 自动转换器 (Auto-Converters)
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
