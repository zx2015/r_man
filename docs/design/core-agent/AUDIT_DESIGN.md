# DETAILED_DESIGN: 审计日志系统设计

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本，基于 Loguru 处理器实现独立审计链 | Gemini CLI |

## 1. 核心实现方案：双 Logger 架构

系统将利用 `loguru` 的多 Sink 特性。

### 1.1 处理器配置
在 `rman/main.py` 启动时，为审计日志添加一个专门的 `filter`：
```python
logger.add(
    config.agent.audit_log_path,
    rotation=f"{config.agent.audit_log_max_size} MB",
    retention=3,  # 保留 3 份
    filter=lambda record: "audit" in record["extra"],
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | AUDIT | {message}"
)
```

## 2. 审计触发器：`@audit_log` 装饰器

定义一个异步装饰器，用于包裹工具的 `execute` 方法。

### 2.1 记录逻辑
1.  **执行前**: 捕获 `tool_name` 和 `kwargs`。
2.  **执行**: 调用原方法。
3.  **执行后**: 
    - 提取意图参数（`description` 或 `instruction`）。
    - 组合结构化字符串。
    - 调用 `logger.bind(audit=True).info(...)` 触发磁盘写入。

## 3. 配置扩展
在 `AgentConfig` 中增加：
- `audit_log_max_size`: 默认 10 (MB)。
- `audit_log_retention`: 默认 3 (份)。

---
> 关联需求: [REQ-AUDIT-001](../../requirements/core-agent/REQ-AUDIT-001.md)
