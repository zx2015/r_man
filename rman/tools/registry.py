from typing import Dict, Optional
from rman.tools.base import BaseTool
from loguru import logger

class ToolRegistry:
    """工具注册表，管理所有可用的内置和插件工具"""
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """注册一个新工具"""
        if not tool.name:
            logger.error(f"Tool {tool.__class__.__name__} has no name defined.")
            return
        self._tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """获取所有工具"""
        return self._tools

    def get_openai_tools(self) -> list:
        """获取符合 OpenAI 规范的工具定义列表"""
        tools = []
        for name, tool in self._tools.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.get_schema()
                }
            })
        return tools

    def generate_tools_description(self) -> str:
        """生成用于 System Prompt 的工具文本说明文档"""
        if not self._tools:
            return "目前尚无可用工具。"
        
        lines = []
        for name, tool in self._tools.items():
            lines.append(f"### {name}")
            lines.append(f"{tool.description}")
            if tool.parameters_schema:
                lines.append("**参数说明**:")
                schema = tool.get_schema()
                for param, info in schema.get("properties", {}).items():
                    req = " (必填)" if param in schema.get("required", []) else " (可选)"
                    lines.append(f"- `{param}` ({info.get('type')}){req}: {info.get('description', '')}")
            lines.append("\n---\n")
        
        return "\n".join(lines)

# 全局单例
tool_registry = ToolRegistry()
