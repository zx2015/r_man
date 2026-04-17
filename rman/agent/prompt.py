import os
import shutil
import time
from datetime import datetime
from rman.common.config import config
from loguru import logger

# --- 核心内容模板定义 ---

IDENTITY_SECTION = """# 角色和身份
你是一个通用 AI Agent，名为 R-MAN, 用于处理用户任务并提供智能助手服务。
你的目标是帮助用户完成多领域任务，并基于上下文选择合适的工具与策略。
在执行任何操作前，先分析任务，再选择合适的工具。
对于危险操作，先说明你的计划，再执行。"""

FORMAT_INSTRUCTION = """# 交互格式规范
1. **强制格式**: 每一条回复必须严格按照以下格式组织，且不能包含标签外的任何文本：
   <think>你的内部思考过程，包括对用户意图的分析、工具选择的考量等</think>
   <final>给用户的最终回复，或者工具执行前的进度说明</final>"""

UI_GUIDELINES_SECTION = """# 飞书呈现美化准则
为了在飞书交互卡片中提供最佳视觉效果，请务必遵循以下格式：
1. **状态标识**: 在 <final> 回复的开头使用 ✅(成功), ❌(失败), ⚠️(警告), ℹ️(提示) 等图标。
2. **标题限制**: 仅允许使用 `#` 和 `##` 标题，禁止使用 `###` 及更小标题。
3. **禁用表格**: 禁止生成 Markdown 表格，请使用嵌套列表或加粗文本进行数据展示。
4. **色彩高亮**: 对关键状态使用飞书专用语法：`[关键词](text_color:颜色)`。
   - 常用颜色: `green` (成功/安全), `red` (错误/危险), `blue` (链接/提示), `grey` (次要信息)。
5. **代码块**: 所有代码或 Shell 输出必须包裹在标准代码块中并注明语言。"""

CONSTRAINTS_SECTION = """# 工具使用约束与风格
1. **行动优先**: 如果用户要求你完成工作，请在同一回合开始执行。
2. **简洁调用**: 直接发起工具调用，禁止在 <final> 中描述“我现在要执行...”。"""

SAFETY_SECTION = """# 安全
1. **目录隔离**: 内部工具 read, write, replace 只能操作工作目录下的文件。
2. **隐私保护**: 严禁透露 API Key、密码等敏感数据。"""

TOOL_STYLE_SECTION = """# 工具调用风格
1. **优先原生调用**: 优先使用 LLM 的 Native Tool Calling。
2. **指令对齐**: 工具名称必须与注册名精确匹配。"""

class PromptBuilder:
    """动态 System Prompt 构建器"""
    def __init__(self):
        self.template_dir = "templates"
        raw_workspace = config.agent.workspace_dir
        self.workspace_dir = raw_workspace.replace("@", "") if raw_workspace.startswith("@") else raw_workspace
        self.abs_workspace = os.path.abspath(self.workspace_dir)
        
        os.makedirs(self.template_dir, exist_ok=True)
        os.makedirs(self.workspace_dir, exist_ok=True)

    def build(self, tool_descriptions: str = "") -> str:
        """组装 System Prompt"""
        self._ensure_files_exist(tool_descriptions)
        
        parts = [
            IDENTITY_SECTION,
            FORMAT_INSTRUCTION,
            UI_GUIDELINES_SECTION, # 新增美化准则
            CONSTRAINTS_SECTION,
            SAFETY_SECTION,
            TOOL_STYLE_SECTION,
            f"# Tools\n{tool_descriptions if tool_descriptions else '目前尚无注册工具。'}",
            f"# 工作目录\n{self.abs_workspace}\n除非另有明确指示，否则视为唯一工作区。",
            f"# 当前日期时间\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Timezone: {time.strftime('%Z')}, {time.strftime('%z')})",
            f"# RMAN.md\n{self._read_file(os.path.join(self.workspace_dir, 'RMAN.md'))}",
            f"# TOOLS.md\n{self._read_file(os.path.join(self.workspace_dir, 'TOOLS.md'))}"
        ]
        
        return "\n\n".join(parts)

    def _ensure_files_exist(self, tool_descriptions: str):
        t_rman = os.path.join(self.template_dir, "RMAN.md")
        t_tool = os.path.join(self.template_dir, "TOOLS.md")
        w_rman = os.path.join(self.workspace_dir, "RMAN.md")
        w_tool = os.path.join(self.workspace_dir, "TOOLS.md")

        if not os.path.exists(w_rman):
            if not os.path.exists(t_rman):
                with open(t_rman, "w", encoding="utf-8") as f: f.write("# RMAN.md")
            shutil.copy(t_rman, w_rman)
        if not os.path.exists(w_tool):
            if not os.path.exists(t_tool):
                with open(t_tool, "w", encoding="utf-8") as f: f.write(tool_descriptions if tool_descriptions else "# TOOLS.md")
            shutil.copy(t_tool, w_tool)

    def _read_file(self, path: str) -> str:
        if not os.path.exists(path): return ""
        try:
            with open(path, "r", encoding="utf-8") as f: return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return ""

prompt_builder = PromptBuilder()
