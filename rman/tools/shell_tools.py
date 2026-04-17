import asyncio
import os
import subprocess
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool
from rman.common.config import config
from loguru import logger

class ShellCommandParams(BaseModel):
    command: str = Field(..., description="要执行的 Bash 命令")
    description: str = Field(..., description="对本次命令执行意图的简要说明")
    dir_path: str = Field(None, description="命令执行的工作目录（默认为工作目录根路径）")

class ShellCommandTool(BaseTool):
    name = "run_shell_command"
    description = "在服务器上执行 Bash 命令。仅支持非交互式命令。对于耗时较长的任务，请谨慎使用。"
    parameters_schema = ShellCommandParams

    async def execute(self, command: str, description: str, dir_path: str = None) -> str:
        # 1. 确定工作目录
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        exec_dir = os.path.abspath(os.path.join(workspace, dir_path)) if dir_path else workspace

        if not exec_dir.startswith(workspace):
            return f"Error: 权限拒绝。只能在工作目录 {workspace} 内执行命令。"

        logger.info(f"Executing Shell Command: {command} (Intent: {description})")

        try:
            # 2. 异步执行命令
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_dir
            )

            stdout, stderr = await process.communicate()
            exit_code = process.returncode

            # 3. 格式化输出
            result = [f"Command: {command}", f"Exit Code: {exit_code}"]
            if stdout:
                result.append(f"--- Standard Output ---\n{stdout.decode('utf-8', errors='replace')}")
            if stderr:
                result.append(f"--- Standard Error ---\n{stderr.decode('utf-8', errors='replace')}")
            
            return "\n\n".join(result)

        except Exception as e:
            logger.error(f"Failed to execute shell command: {e}")
            return f"Error: 执行失败 - {str(e)}"
