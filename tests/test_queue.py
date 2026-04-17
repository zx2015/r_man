import asyncio
import pytest
from rman.interaction.queue import SerialTaskQueue

@pytest.mark.asyncio
async def test_serial_task_queue_order():
    queue = SerialTaskQueue()
    await queue.start()
    
    execution_order = []
    
    async def task(name, delay):
        await asyncio.sleep(delay)
        execution_order.append(name)
        
    # 添加三个任务，延迟时间递减
    # 如果是并行的，task3 会先完成；如果是串行的，必须是 1->2->3
    await queue.add_task(task("task1", 0.3))
    await queue.add_task(task("task2", 0.2))
    await queue.add_task(task("task3", 0.1))
    
    # 等待足够长的时间让所有任务完成
    await asyncio.sleep(1.0)
    
    assert execution_order == ["task1", "task2", "task3"]
    await queue.stop()

@pytest.mark.asyncio
async def test_serial_task_queue_error_handling():
    queue = SerialTaskQueue()
    await queue.start()
    
    success_flags = []
    
    async def failing_task():
        raise ValueError("Boom")
        
    async def normal_task():
        success_flags.append(True)
        
    await queue.add_task(failing_task())
    await queue.add_task(normal_task())
    
    await asyncio.sleep(0.5)
    
    # 验证第一个任务失败不会阻塞第二个任务的执行
    assert success_flags == [True]
    await queue.stop()
