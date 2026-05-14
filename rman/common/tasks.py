"""
异步任务工具模块

提供 fire_and_forget 辅助函数，用于替代裸 asyncio.create_task。
相比裸调用，有两项改进：
1. 维护模块级 _running_tasks set，对运行中任务保持强引用，防止被 GC 提前回收
   （Python 官方文档明确建议此模式：https://docs.python.org/3/library/asyncio-task.html）
2. 附加 done_callback 确保任务异常不会静默丢失：
   - 任务成功或被 cancel：静默处理
   - 任务抛出异常：以 WARNING 级别记录，含任务名称与异常详情
"""
import asyncio
from typing import Coroutine, Any, Set
from loguru import logger

# 持有所有正在运行的 fire-and-forget 任务的强引用，防止 GC 在任务完成前回收。
# 任务完成（成功、失败或取消）后由 done_callback 自动移除。
_running_tasks: Set[asyncio.Task] = set()


def fire_and_forget(coro: Coroutine[Any, Any, Any], name: str = "") -> asyncio.Task:
    """
    创建 fire-and-forget 异步任务，防止 GC 提前回收并捕获异常。

    适用场景：
    - 后台持久化写入（DB、日志）
    - 发送通知消息（飞书卡片等）
    - 事件驱动的非阻塞副作用

    不适用场景：
    - 需要等待结果的操作（请直接 await）
    - 需要协调多个任务的场景（请使用 asyncio.gather 或 TaskGroup）

    Args:
        coro: 要执行的协程对象
        name: 任务名称，用于错误日志定位

    Returns:
        asyncio.Task 对象（调用方可选择保留引用）
    """
    task = asyncio.create_task(coro, name=name or None)
    _running_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _running_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            label = f"[{name}] " if name else ""
            logger.warning(f"fire_and_forget task {label}raised an exception: {exc!r}")

    task.add_done_callback(_on_done)
    return task
