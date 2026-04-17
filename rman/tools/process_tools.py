from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool
from rman.tools.process_manager import process_manager
from loguru import logger

class ProcessAction(str, Enum):
    STATUS = "status"
    READ = "read"
    KILL = "kill"

class ProcessParams(BaseModel):
    action: ProcessAction = Field(..., description="操作类型: status (查询状态), read (读取输出), kill (终止进程)")
    pid: int = Field(..., description="目标后台进程的 PID")
    offset: int = Field(0, description="仅 action=read 时有效。读取日志的起始偏移行号")
    limit: int = Field(50, description="仅 action=read 时有效。单次读取的最大行数")

class ProcessTool(BaseTool):
    name = "process"
    description = "管理由 run_shell_command(is_background=True) 启动的后台进程。"
    parameters_schema = ProcessParams

    async def execute(self, action: ProcessAction, pid: int, offset: int = 0, limit: int = 50) -> str:
        m_proc = process_manager.get_process(pid)
        
        if not m_proc:
            return f"Error: 找不到 PID 为 {pid} 的后台任务。它可能已超时清理或从未启动。"

        if action == ProcessAction.STATUS:
            status = m_proc.get_status()
            return f"Process {pid} Status: {status}\nCommand: {m_proc.command}\nStart Time: {m_proc.start_time}"

        elif action == ProcessAction.READ:
            logs = m_proc.read_logs(offset, limit)
            total = len(m_proc.output_buffer)
            if not logs:
                return f"Process {pid} Logs: [当前偏移量无新输出] (Total buffered lines: {total})"
            
            output = [f"Process {pid} Logs (Lines {offset} to {offset + len(logs)}, Total {total}):"]
            output.extend([f"[{i+offset}] {line}" for i, line in enumerate(logs)])
            return "\n".join(output)

        elif action == ProcessAction.KILL:
            logger.warning(f"Killing process {pid} by user request.")
            try:
                m_proc.process.terminate()
                return f"Success: 已向进程 {pid} 发送终止信号 (SIGTERM)。"
            except Exception as e:
                return f"Error: 终止失败 - {str(e)}"
        
        return "Error: 未知操作类型。"
