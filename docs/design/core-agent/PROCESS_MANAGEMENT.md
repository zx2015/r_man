# DETAILED_DESIGN: 后台进程管理系统

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本，定义进程追踪器与管理逻辑 | Gemini CLI |

## 1. 进程追踪器 (Process Tracker)

由于 Python 的 `asyncio.create_subprocess_shell` 返回的进程对象是非持久的，我们需要一个全局单例来维护其生命周期。

### 1.1 数据模型
```python
class ManagedProcess(BaseModel):
    pid: int
    command: str
    description: str
    start_time: datetime
    process: asyncio.subprocess.Process
    output_buffer: List[str]  # 存储 stdout/stderr 行
```

## 2. 核心逻辑实现

### 2.1 后台启动 (`run_shell_command`)
1.  启动子进程。
2.  创建一个后台协程（Task）持续读取该进程的流，并存入 `output_buffer`。
3.  将 `ManagedProcess` 存入全局字典。
4.  等待 `delay_ms` 后，返回 PID 和当前 Buffer 中的快照。

### 2.2 状态查询 (`process action=status`)
- 检查 `process.returncode`。
- 若为 `None`，返回 `Running`。
- 若不为 `None`，返回 `Exited` 及退出码。

### 2.3 日志读取 (`process action=read`)
- 根据 `offset` 参数，从 `output_buffer` 中提取指定行。
- 单次读取限制 50 行，以保护上下文 Token。

### 2.4 强制终止 (`process action=kill`)
- 调用 `process.terminate()`。
- 等待 2 秒，若未结束则调用 `process.kill()`。

## 3. 资源清理 (TTL Management)
- 系统每隔 10 分钟扫描一次字典。
- 超过 `process_session_max_ttl` (默认 3600s) 的已结束任务将被从字典中移除。

---
> 关联需求: [REQ-CORE-001](../../requirements/core-agent/REQ-CORE-001.md)
