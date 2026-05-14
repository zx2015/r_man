"""
异步任务工具模块

提供 fire_and_forget 辅助函数，用于替代裸 asyncio.create_task。
相比裸调用，额外附加 done_callback 确保任务异常不会静默丢失：
- 任务成功或被 cancel：静默处理
- 任务抛出异常：以 WARNING 级别记录，含任务名称与异常详情
"""
import asyncio
from typing import Coroutine, Any, Optional
from loguru import logger


def fire_and_forget(coro: Coroutine[Any, Any, Any], name: str = "") -> asyncio.Task:
    """
    创建 fire-and-forget 异步任务，附加错误回调以防止异常静默丢失。

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

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            label = f"[{name}] " if name else ""
            logger.warning(f"fire_and_forget task {label}raised an exception: {exc!r}")

    task.add_done_callback(_on_done)
    return task
