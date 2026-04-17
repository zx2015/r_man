# REQ-MESSAGING-001: 飞书消息卡片与交互格式需求

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本，定义交互式卡片结构、Token 消耗统计及 Model 展示 | Gemini CLI |

## 1. 业务目标
为了提升用户反馈的直观性并提供透明的资源消耗监控，R-MAN 必须采用飞书交互式卡片作为标准通讯格式。

## 2. 功能需求

### FR-001: 组件化交互卡片 (Component-based Card)
所有响应必须采用飞书卡片 2.0 规范，优先使用组件而非单一 Markdown 块：
- **Header**: 包含动态图标（🤖/❌）和副标题（显示任务 ID）。
- **Body**: 
    - 关键结果使用 `column_set` 进行分栏展示。
    - 长文本使用支持 Markdown 子集的 `div` 模块。
- **Table Support**: 当需要展示结构化列表（如进程清单、文件属性）时，允许并在 Prompt 中引导模型产出符合卡片 2.0 规范的 `table` 标签结构（包含 `columns` 和 `rows` 数组）。
- **Status Bar**: 使用 `column_set` 实现左右对称布局，左侧显示模型名，右侧显示 Token 消耗。
- **Color Coding**: 
    - 成功: `text_color:green`
    - 消耗: `text_color:grey`
    - 警告/错误: `text_color:red`


### FR-002: Token 消耗统计
系统必须在单个用户消息处理任务完成后，计算并展示该任务产生的总消耗：
- **Input Tokens**: 单个任务中所有 LLM 调用的 prompt 消耗累加。
- **Output Tokens**: 单个任务中所有 LLM 调用的 completion 消耗累加。

### FR-003: 模型信息展示
必须在卡片底部明确标注当前处理任务所使用的具体模型名称（如 `gpt-4o` 或 `MiniMax-M2.7`）。

## 3. 数据契约
```text
注脚格式: ⏱ [HH:mm:ss] | Model: [ModelName] | In: [InCount] | Out: [OutCount]
```

## 4. 验收标准
- **AC-001**: 每次回复必须是一张带有颜色标题栏的卡片。
- **AC-002**: 注脚中显示的 Input/Output Token 总数等于该任务期间所有 ReAct 轮次的消耗之和。
