import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

class ManagedProcess:
    """受控后台进程的数据模型"""
    def __init__(self, pid: int, command: str, description: str, process: asyncio.subprocess.Process):
        self.pid = pid
        self.command = command
        self.description = description
        self.process = process
        self.start_time = datetime.now()
        self.output_buffer: List[str] = []
        self._reader_task: Optional[asyncio.Task] = None

    def start_reading(self):
        """启动后台流读取"""
        self._reader_task = asyncio.create_task(self._read_streams())

    async def _read_streams(self):
        """同时读取 stdout 和 stderr"""
        async def stream_to_buffer(stream):
            while True:
                line = await stream.readline()
                if not line:
                    break
                # 解码并存入 buffer，限制 buffer 大小防止内存溢出 (最多存 2000 行)
                self.output_buffer.append(line.decode('utf-8', errors='replace').rstrip())
                if len(self.output_buffer) > 2000:
                    self.output_buffer.pop(0)

        # 运行并发读取
        tasks = []
        if self.process.stdout:
            tasks.append(stream_to_buffer(self.process.stdout))
        if self.process.stderr:
            tasks.append(stream_to_buffer(self.process.stderr))
        
        if tasks:
            await asyncio.gather(*tasks)

    def get_status(self) -> str:
        ret = self.process.returncode
        if ret is None:
            return "Running"
        return f"Exited (Code: {ret})"

    def read_logs(self, offset: int = 0, limit: int = 50) -> List[str]:
        return self.output_buffer[offset : offset + limit]

class ProcessManager:
    """全局后台进程管理器单例"""
    def __init__(self):
        self._processes: Dict[int, ManagedProcess] = {}

    def add_process(self, m_proc: ManagedProcess):
        self._processes[m_proc.pid] = m_proc
        m_proc.start_reading()
        logger.info(f"Process {m_proc.pid} added to manager: {m_proc.command}")

    def get_process(self, pid: int) -> Optional[ManagedProcess]:
        return self._processes.get(pid)

    def remove_process(self, pid: int):
        if pid in self._processes:
            del self._processes[pid]
            logger.info(f"Process {pid} removed from manager.")

# 单例
process_manager = ProcessManager()
