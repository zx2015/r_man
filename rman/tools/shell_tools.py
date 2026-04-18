import asyncio
import os
import subprocess
from typing import Optional
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool, audit_log
from rman.common.config import config
from loguru import logger

class ShellCommandParams(BaseModel):
    command: str = Field(..., description="要执行的 Bash 命令")
    description: str = Field(..., description="对本次命令执行意图的简要说明")
    dir_path: str = Field(None, description="命令执行的工作目录（相对于工作目录根路径）")
    is_background: bool = Field(False, description="是否后台执行")
    delay_ms: int = Field(0, description="后台执行时等待获取初始输出的毫秒数")

class ShellCommandTool(BaseTool):
    name = "run_shell_command"
    description = "在服务器上执行 Bash 命令。支持前台阻塞与后台异步两种模式。"
    parameters_schema = ShellCommandParams

    @audit_log
    async def execute(self, command: str, description: str, dir_path: Optional[str] = None, is_background: bool = False, delay_ms: int = 0) -> str: # type: ignore[override]
        from rman.tools.process_manager import ManagedProcess, process_manager

        # 1. 确定工作目录
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        exec_dir = os.path.abspath(os.path.join(workspace, dir_path)) if dir_path else workspace

        if not exec_dir.startswith(workspace):
            return f"Error: 权限拒绝。只能在工作目录 {workspace} 内执行命令。"

        logger.info(f"Executing Shell Command (Background={is_background}): {command}")

        # --- 新增：基础高危命令检查 ---
        forbidden_patterns = ["rm ", "truncate ", "> /", "mv "]
        if any(p in command for p in forbidden_patterns):
            # 如果包含高危词，检查是否有路径穿越
            if ".." in command or ("/" in command and not command.startswith("./") and not command.startswith(workspace)):
                 # 这是一个简单的启发式检查，未来可以引入更严谨的解析
                 logger.warning(f"Potentially dangerous shell command blocked: {command}")
                 return f"Error: 权限拒绝。检测到潜在的破坏性操作或路径穿越：{command}"
        # ---------------------------

        try:
            # 2. 启动子进程
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_dir
            )

            pid = process.pid

            if is_background:
                # 3. 后台模式：交给管理器并等待快照
                m_proc = ManagedProcess(pid, command, description, process)
                process_manager.add_process(m_proc)
                
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
                
                initial_output = "\n".join(m_proc.output_buffer)
                return f"Success: 任务已在后台启动。PID: {pid}\n初始输出快照:\n{initial_output if initial_output else '[无即时输出]'}"
            
            else:
                # 4. 前台模式：死等结束
                stdout, stderr = await process.communicate()
                exit_code = process.returncode
                result = [f"Command: {command}", f"Exit Code: {exit_code}"]
                if stdout: result.append(f"--- Standard Output ---\n{stdout.decode('utf-8', errors='replace')}")
                if stderr: result.append(f"--- Standard Error ---\n{stderr.decode('utf-8', errors='replace')}")
                return "\n\n".join(result)

        except Exception as e:
            logger.error(f"Failed to execute shell command: {e}")
            return f"Error: 执行失败 - {str(e)}"
