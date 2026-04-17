import asyncio
from typing import Coroutine, Any, Optional
from loguru import logger

class SerialTaskQueue:
    """串行任务队列，确保同一时间只有一个任务在执行"""
    def __init__(self):
        self._queue: Optional[asyncio.Queue] = None
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """在主事件循环中初始化队列和 Worker"""
        if self._queue is None:
            self._queue = asyncio.Queue()
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Serial task queue worker started.")

    async def stop(self):
        """停止队列 Worker"""
        if self._worker_task:
            logger.info("Stopping Serial task queue worker...")
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            self._queue = None

    async def add_task(self, coro: Coroutine[Any, Any, Any]):
        """向队列添加异步任务（线程安全封装见交互层调用）"""
        if self._queue is not None:
            await self._queue.put(coro)
            logger.debug("New task added to queue.")
        else:
            logger.error("Queue not initialized! Call start() first.")

    async def _worker(self):
        """持续从队列中取出并执行任务"""
        while True:
            coro = None
            try:
                coro = await self._queue.get()
                logger.info("Worker: Starting execution of a new task.")
                await coro
                logger.info("Worker: Task completed successfully.")
            except asyncio.CancelledError:
                logger.debug("Worker: Worker task cancelled.")
                break
            except Exception as e:
                logger.exception(f"Worker: Error during task execution: {e}")
            finally:
                if coro is not None:
                    self._queue.task_done()
                    logger.debug("Worker: Task marked as done.")

# 单例
task_queue = SerialTaskQueue()
