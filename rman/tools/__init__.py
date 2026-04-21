from rman.tools.registry import tool_registry
from rman.tools.file_tools import ReadFileTool, WriteFileTool, ReplaceTool
from rman.tools.shell_tools import ShellCommandTool
from rman.tools.process_tools import ProcessTool
from rman.tools.memory_tools import MemorySearchTool, MemoryDumpTool
from rman.tools.session_search import SessionSearchTool
from rman.tools.tavily_tools import (
    TavilySearchTool, TavilyExtractTool, TavilyCrawlTool, 
    TavilyMapTool, TavilyResearchTool
)

# 初始化并注册所有内置工具
tool_registry.register(ReadFileTool())
tool_registry.register(WriteFileTool())
tool_registry.register(ReplaceTool())
tool_registry.register(ShellCommandTool())
tool_registry.register(ProcessTool())
tool_registry.register(MemorySearchTool())
tool_registry.register(MemoryDumpTool())
tool_registry.register(SessionSearchTool())
tool_registry.register(TavilySearchTool())
tool_registry.register(TavilyExtractTool())
tool_registry.register(TavilyCrawlTool())
tool_registry.register(TavilyMapTool())
tool_registry.register(TavilyResearchTool())
