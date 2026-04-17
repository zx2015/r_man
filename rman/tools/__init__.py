from rman.tools.registry import tool_registry
from rman.tools.file_tools import ReadFileTool, WriteFileTool, ReplaceTool
from rman.tools.shell_tools import ShellCommandTool
from rman.tools.process_tools import ProcessTool

# 初始化并注册所有内置工具
tool_registry.register(ReadFileTool())
tool_registry.register(WriteFileTool())
tool_registry.register(ReplaceTool())
tool_registry.register(ShellCommandTool())
tool_registry.register(ProcessTool())
