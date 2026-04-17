# REQ-TOOLS-TAVILY: Tavily 联网搜索与研究工具需求

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本，定义 5 个 Tavily 核心联网工具 | Gemini CLI |

## 1. 业务目标
赋予 R-MAN 实时联网能力，使其能够获取即时新闻、提取网页数据并进行深度的互联网主题研究。

## 2. 工具列表定义

### FR-001: tavily_search
- **描述**: 在互联网上搜索任何话题的当前信息。
- **核心参数**: `query` (必填), `max_results`, `search_depth` ('basic'|'advanced'), `include_raw_content`。
- **返回**: 网页摘要快照及原始 URL 列表。

### FR-002: tavily_extract
- **描述**: 从指定的 URL 列表中提取内容。
- **核心参数**: `urls` (必填), `extract_depth` ('basic'|'advanced')。
- **返回**: 网页的 Markdown 或纯文本内容。

### FR-003: tavily_crawl
- **描述**: 从起始 URL 开始爬取网站，支持深度和广度配置。
- **核心参数**: `url` (必填), `max_depth`, `limit`, `instructions` (自然语言爬取指令)。

### FR-004: tavily_map
- **描述**: 映射网站结构，返回从基础 URL 开始发现的 URL 列表。
- **核心参数**: `url` (必填), `max_depth`。

### FR-005: tavily_research
- **描述**: 执行全面的深度研究任务。
- **核心参数**: `input` (必填), `model` ('mini'|'pro')。
- **频率限制**: 每分钟 20 次请求。

## 3. 安全要求
- 所有通过 Tavily 提取的内容在注入上下文前，必须经过 Agent 的隐私自检（遵循 REQ-CORE-003）。
