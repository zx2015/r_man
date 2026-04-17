import os
from typing import Optional
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool
from rman.common.config import config
from loguru import logger

class ReadFileParams(BaseModel):
    path: str = Field(..., description="目标文件的相对路径（相对于工作目录）")
    start_line: Optional[int] = Field(1, description="起始行号 (1-based)")
    end_line: Optional[int] = Field(None, description="结束行号")

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取指定文件的内容。出于性能考虑，单次建议读取不超过 100 行。"
    parameters_schema = ReadFileParams

    async def execute(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
        # ... (保持原有代码逻辑)
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        target_path = os.path.abspath(os.path.join(workspace, path))

        if not target_path.startswith(workspace):
            return f"Error: 权限拒绝。只能读取工作目录 {workspace} 内的文件。"

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

class WriteFileParams(BaseModel):
    path: str = Field(..., description="目标文件的相对路径")
    content: str = Field(..., description="要写入的完整内容")

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "创建或覆盖写入文件。使用前请确认不需要保留原内容。"
    parameters_schema = WriteFileParams

    async def execute(self, path: str, content: str) -> str:
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        target_path = os.path.abspath(os.path.join(workspace, path))

        if not target_path.startswith(workspace):
            return f"Error: 权限拒绝。只能写入工作目录 {workspace} 内的文件。"

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"File written: {path} ({len(content)} bytes)")
            return f"Success: 文件 {path} 已写入 ({len(content)} 字节)。"
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            return f"Error: 写入失败 - {str(e)}"

class ReplaceParams(BaseModel):
    file_path: str = Field(..., description="文件的相对路径")
    old_string: str = Field(..., description="待替换的精确原文本")
    new_string: str = Field(..., description="替换后的新文本")
    instruction: str = Field(..., description="本次修改的意图说明（用于审计）")
    allow_multiple: bool = Field(False, description="是否允许替换所有匹配项")

class ReplaceTool(BaseTool):
    name = "replace"
    description = "对文件进行局部替换。old_string 必须精确匹配。推荐优先使用此工具修改现有文件。"
    parameters_schema = ReplaceParams

    async def execute(self, file_path: str, old_string: str, new_string: str, instruction: str, allow_multiple: bool = False) -> str:
        workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
        target_path = os.path.abspath(os.path.join(workspace, file_path))

        if not target_path.startswith(workspace):
            return f"Error: 权限拒绝。只能操作工作目录 {workspace} 内的文件。"

        if not os.path.exists(target_path):
            return f"Error: 文件 {file_path} 不存在。"

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_string)
            if count == 0:
                return f"Error: 在文件 {file_path} 中找不到指定的 old_string。请确保空格和换行完全匹配。"
            
            if count > 1 and not allow_multiple:
                return f"Error: old_string 在文件中出现了 {count} 次。为避免误伤，请提供更精确的匹配或设置 allow_multiple=True。"

            new_content = content.replace(old_string, new_string)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            logger.info(f"File replaced: {file_path} (Intent: {instruction})")
            return f"Success: 文件 {file_path} 已成功修改。意图: {instruction}"
        except Exception as e:
            logger.error(f"Failed to replace content in {file_path}: {e}")
            return f"Error: 替换失败 - {str(e)}"
