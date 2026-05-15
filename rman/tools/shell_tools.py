import asyncio
import os
import shlex
from typing import Callable, List, Optional
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool, audit_log
from rman.common.config import config
from loguru import logger

# 前台命令进度心跳间隔（秒）
_HEARTBEAT_INTERVAL = 60

# 高危二进制黑名单：这些命令一旦带绝对路径参数，极易造成系统级破坏
# 使用 shlex 解析后检查第一个 token，防止空格/转义绕过（如 rm\ -rf, "rm" -rf）
_DANGEROUS_BINARIES = frozenset({
    "rm", "shred", "unlink", "wipe",           # 文件删除
    "dd",                                        # 磁盘裸写
    "mkfs", "fdisk", "parted", "mkswap",        # 磁盘格式化
    "truncate",                                  # 文件截断
})


def _extract_absolute_paths(tokens: list) -> list:
    """从 token 列表中提取所有绝对路径，支持直接路径和 key=value 格式（如 dd 的 of=/dev/sda）"""
    paths = []
    for token in tokens:
        if token.startswith('/'):
            paths.append(token)
        elif '=' in token:
            value = token.partition('=')[2]
            if value.startswith('/'):
                paths.append(value)
    return paths


def _extract_write_paths(binary: str, tokens: list) -> list:
    """提取命令中实际的写目标路径。
    dd 仅检查 of= 参数（if= 是读取源，允许引用任意路径），其余黑名单命令检查所有绝对路径。
    """
    if binary == "dd":
        return [
            token.partition('=')[2]
            for token in tokens
            if token.startswith('of=') and token.partition('=')[2].startswith('/')
        ]
    return _extract_absolute_paths(tokens)


def _check_command_safety(command: str, workspace: str) -> Optional[str]:
    """
    命令安全检查。返回错误消息字符串表示拦截，返回 None 表示放行。
    采用双层检测：
      1. shlex 解析 → 提取二进制名称 → 对比黑名单（防绕过）
      2. 原始字符串匹配 → 拦截重定向到根路径（shlex 无法感知 shell 操作符）
    """
    # Layer 1：解析 token，提取实际执行的二进制名称
    try:
        tokens = shlex.split(command)
    except ValueError:
        # shlex 解析失败（如未闭合引号）说明命令本身有问题
        tokens = command.split()

    if tokens:
        binary = os.path.basename(tokens[0])
        if binary in _DANGEROUS_BINARIES:
            # 提取写目标路径（dd 仅看 of=，其余看所有绝对路径参数）
            for abs_path in _extract_write_paths(binary, tokens[1:]):
                if not abs_path.startswith(workspace) and not abs_path.startswith('/tmp'):
                    logger.warning(f"Dangerous command with external path blocked: {command}")
                    return f"Error: 权限拒绝。命令 '{binary}' 包含工作目录外的绝对路径参数：{abs_path}"

    # Layer 2：检测重定向到工作目录外的绝对路径（shlex 无法感知 shell 操作符）
    # 提取 > 或 >> 后的目标路径，放行 workspace 和 /tmp，拦截其他绝对路径
    if '>' in command:
        import re
        for redir_target in re.findall(r'>{1,2}\s*(/[^\s;|&]*)', command):
            if not redir_target.startswith('/tmp') and not redir_target.startswith(workspace):
                logger.warning(f"Redirect to external absolute path blocked: {command}")
                return f"Error: 权限拒绝。检测到重定向到工作目录外的绝对路径：{redir_target}"

    return None  # 通过检查


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
    async def execute(self, command: str, description: str, dir_path: Optional[str] = None, is_background: bool = False, delay_ms: int = 0, **kwargs) -> str: # type: ignore[override]
        from rman.tools.process_manager import ManagedProcess, process_manager

        # 1. 确定工作目录（使用 realpath 解析软链，防止软链目录绕过）
        workspace = os.path.realpath(config.agent.workspace_dir.replace("@", ""))
        exec_dir = os.path.realpath(os.path.join(workspace, dir_path)) if dir_path else workspace

        if not exec_dir.startswith(workspace):
            return f"Error: 权限拒绝。只能在工作目录 {workspace} 内执行命令。"

        # 2. 命令安全检查
        safety_err = _check_command_safety(command, workspace)
        if safety_err:
            return safety_err

        logger.info(f"Executing Shell Command (Background={is_background}): {command}")

        try:
            # 3. 启动子进程
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_dir
            )

            pid = process.pid

            if is_background:
                # 4. 后台模式：交给管理器并等待快照
                m_proc = ManagedProcess(pid, command, description, process)
                process_manager.add_process(m_proc)
                
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
                
                initial_output = "\n".join(m_proc.output_buffer)
                return f"Success: 任务已在后台启动。PID: {pid}\n初始输出快照:\n{initial_output if initial_output else '[无即时输出]'}"
            
            else:
                # 5. 前台模式：死等结束
                stdout, stderr = await process.communicate()
                exit_code = process.returncode
                result = [f"Command: {command}", f"Exit Code: {exit_code}"]
                if stdout: result.append(f"--- Standard Output ---\n{stdout.decode('utf-8', errors='replace')}")
                if stderr: result.append(f"--- Standard Error ---\n{stderr.decode('utf-8', errors='replace')}")
                return "\n\n".join(result)

        except Exception as e:
            logger.error(f"Failed to execute shell command: {e}")
            return f"Error: 执行失败 - {str(e)}"

    async def execute_with_progress(
        self,
        progress_callback: Optional[Callable] = None,
        command: str = "",
        description: str = "",
        dir_path: Optional[str] = None,
        is_background: bool = False,
        delay_ms: int = 0,
        **kwargs,
    ) -> str:
        """带进度心跳的命令执行入口。前台模式每 60 秒调用一次 progress_callback；
        后台模式和安全检查逻辑与 execute() 完全一致。"""
        from rman.tools.process_manager import ManagedProcess, process_manager

        workspace = os.path.realpath(config.agent.workspace_dir.replace("@", ""))
        exec_dir = os.path.realpath(os.path.join(workspace, dir_path)) if dir_path else workspace

        if not exec_dir.startswith(workspace):
            return f"Error: 权限拒绝。只能在工作目录 {workspace} 内执行命令。"

        safety_err = _check_command_safety(command, workspace)
        if safety_err:
            return safety_err

        logger.info(f"Executing Shell Command (Background={is_background}, Progress=True): {command}")

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_dir,
            )
            pid = process.pid

            if is_background:
                m_proc = ManagedProcess(pid, command, description, process)
                process_manager.add_process(m_proc)
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
                initial_output = "\n".join(m_proc.output_buffer)
                return (
                    f"Success: 任务已在后台启动。PID: {pid}\n"
                    f"初始输出快照:\n{initial_output if initial_output else '[无即时输出]'}"
                )
            else:
                return await self._run_foreground_with_heartbeat(process, command, progress_callback)

        except Exception as e:
            logger.error(f"Failed to execute shell command (with_progress): {e}")
            return f"Error: 执行失败 - {str(e)}"

    async def _run_foreground_with_heartbeat(
        self,
        process: asyncio.subprocess.Process,
        command: str,
        progress_callback: Optional[Callable],
    ) -> str:
        """流式读取 stdout/stderr，每 _HEARTBEAT_INTERVAL 秒触发一次进度回调。"""
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        async def _drain(stream: asyncio.StreamReader, buf: List[str]) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                buf.append(line.decode("utf-8", errors="replace").rstrip())

        # 后台并发读取两个流，避免管道缓冲区满导致进程阻塞
        async def _read_all() -> None:
            await asyncio.gather(
                _drain(process.stdout, stdout_lines),
                _drain(process.stderr, stderr_lines),
            )

        reader = asyncio.create_task(_read_all())

        start = asyncio.get_event_loop().time()
        last_heartbeat = start

        # 1 秒轮询，直到进程退出
        while process.returncode is None:
            await asyncio.sleep(1)
            now = asyncio.get_event_loop().time()
            if progress_callback and (now - last_heartbeat) >= _HEARTBEAT_INTERVAL:
                elapsed_min = int((now - start) / 60)
                recent = (stdout_lines + stderr_lines)[-10:]
                try:
                    await progress_callback(
                        {
                            "command": command,
                            "elapsed_minutes": elapsed_min,
                            "recent_output": recent,
                        }
                    )
                except Exception as cb_exc:
                    logger.warning(f"Progress callback error: {cb_exc}")
                last_heartbeat = now

        await reader  # 等待剩余输出全部刷入缓冲区

        exit_code = process.returncode
        result = [f"Command: {command}", f"Exit Code: {exit_code}"]
        if stdout_lines:
            result.append(f"--- Standard Output ---\n" + "\n".join(stdout_lines))
        if stderr_lines:
            result.append(f"--- Standard Error ---\n" + "\n".join(stderr_lines))
        return "\n\n".join(result)
