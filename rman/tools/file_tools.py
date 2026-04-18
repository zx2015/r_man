import os
from typing import Optional, List
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool, audit_log
from rman.common.config import config
from loguru import logger

class ReadFileParams(BaseModel):
    path: str = Field(..., description="目标文件的路径（支持系统内所有有权限的路径）")
    start_line: Optional[int] = Field(1, description="起始行号 (1-based)")
    end_line: Optional[int] = Field(None, description="结束行号")

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取指定文件的内容。不再局限于工作目录。单次建议读取不超过 100 行。"
    parameters_schema = ReadFileParams

    async def execute(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> str: # type: ignore[override]
        # 路径规范化 (处理相对路径)
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        target_path = os.path.abspath(os.path.join(workspace, path))

        if not os.path.exists(target_path):
            return f"Error: 文件 {path} 不存在。"

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            end = end_line if end_line else start_line + 99
            selected_lines = lines[start_line-1 : end]
            
            output = [f"File: {path} (Total lines: {total_lines}, showing {start_line} to {min(end, total_lines)})"]
            for i, line in enumerate(selected_lines):
                output.append(f"{start_line + i}: {line.rstrip()}")
            return "\n".join(output)
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return f"Error: 读取失败 - {str(e)}"

def is_path_writable(target_path: str, workspace: str) -> bool:
    """检查路径是否允许写入 (workspace 或 /tmp)"""
    target = os.path.abspath(target_path)
    allowed_dirs = [os.path.abspath(workspace), "/tmp"]
    return any(target.startswith(d) for d in allowed_dirs)

class WriteFileParams(BaseModel):
    path: str = Field(..., description="目标文件的路径")
    content: str = Field(..., description="要写入的完整内容")

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "创建或覆盖写入文件。允许写入工作目录或 /tmp 目录。支持修改 RMAN.md 和 TOOLS.md。"
    parameters_schema = WriteFileParams

    @audit_log
    async def execute(self, path: str, content: str) -> str: # type: ignore[override]
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        target_path = os.path.abspath(os.path.join(workspace, path))

        # 路径校验：允许 workspace 或 /tmp
        if not is_path_writable(target_path, workspace):
            return f"Error: 权限拒绝。只能写入工作目录 {workspace} 或 /tmp 目录。"

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"File written: {path} ({len(content)} bytes)")
            return f"Success: 文件 {path} 已成功写入。"
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            return f"Error: 写入失败 - {str(e)}"

class ReplaceParams(BaseModel):
    file_path: str = Field(..., description="文件的路径")
    old_string: str = Field(..., description="待替换的精确原文本")
    new_string: str = Field(..., description="替换后的新文本")
    instruction: str = Field(..., description="本次修改的意图说明")
    allow_multiple: bool = Field(False, description="是否允许替换所有匹配项")

class ReplaceTool(BaseTool):
    name = "replace"
    description = "局部替换文件内容。允许操作工作目录或 /tmp 目录。支持修改 RMAN.md 和 TOOLS.md。"
    parameters_schema = ReplaceParams

    @audit_log
    async def execute(self, file_path: str, old_string: str, new_string: str, instruction: str, allow_multiple: bool = False) -> str: # type: ignore[override]
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        target_path = os.path.abspath(os.path.join(workspace, file_path))

        # 路径校验：允许 workspace 或 /tmp
        if not is_path_writable(target_path, workspace):
            return f"Error: 权限拒绝。只能操作工作目录 {workspace} 或 /tmp 目录。"

        if not os.path.exists(target_path):
            return f"Error: 文件 {file_path} 不存在。"

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_string)
            if count == 0:
                return f"Error: 找不到指定的 old_string。"
            
            if count > 1 and not allow_multiple:
                return f"Error: old_string 出现了 {count} 次。请提供更精确的匹配。"

            new_content = content.replace(old_string, new_string)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            logger.info(f"File replaced: {file_path} (Intent: {instruction})")
            return f"Success: 文件 {file_path} 已成功修改。"
        except Exception as e:
            logger.error(f"Failed to replace content in {file_path}: {e}")
            return f"Error: 替换失败 - {str(e)}"
