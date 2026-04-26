import re
import json
from typing import Optional, List, Dict
from loguru import logger

# --- 飞书卡片物理规格常量 ---
FEISHU_CARD_TABLE_LIMIT = 5
FEISHU_CARD_COLUMN_LIMIT = 50

class CardFormatter:
    """飞书卡片格式化流水线：预算预处理 -> 样式优化 -> 结构转换"""

    @classmethod
    def format_with_components(cls, text: str) -> list:
        """
        核心渲染方法：执行 Pipeline 并产出组件列表。
        """
        if not text:
            return []

        # 1. 执行文本级优化
        processed = cls._optimize_markdown_style(text)
        
        # 2. 识别并转换表格 (使用常量上限)
        elements = cls._convert_tables_to_components(processed)
        
        return elements

    @classmethod
    def _convert_tables_to_components(cls, text: str) -> list:
        """识别 Markdown 表格及标题，并将其转为飞书原生组件"""
        elements = []
        # 1. 识别标题行并赋予 heading 样式
        # 匹配以 # 开头的行，支持 1-6 级
        header_pattern = r'(^#{1,6}\s+.*)'
        
        # 2. 识别表格
        table_pattern = r'(\n(?:\|.*\|(?:\n|$)){2,})'
        
        # 混合解析：先处理表格，再在剩余文本中处理标题
        parts = re.split(table_pattern, text)
        table_count = 0

        for part in parts:
            if re.match(table_pattern, part) and table_count < FEISHU_CARD_TABLE_LIMIT:
                table_count += 1
                try:
                    table_comp = cls._parse_markdown_table(part)
                    if table_comp:
                        elements.append(table_comp)
                        continue
                except Exception as e:
                    logger.error(f"Failed to convert table: {e}")
            
            if not part.strip(): continue

            # 处理段落中的标题
            sub_parts = re.split(header_pattern, part, flags=re.MULTILINE)
            for sub_part in sub_parts:
                if not sub_part.strip(): continue
                
                header_match = re.match(r'^(#{1,6})\s+(.*)', sub_part)
                if header_match:
                    level = len(header_match.group(1))
                    title_text = header_match.group(2).strip()
                    # 映射规则微调：实现 16px, 15px(近似), 14px 视觉效果
                    # 1-2级 -> heading-4 (16px)
                    # 3级   -> heading (16px)
                    # 4-6级 -> normal (14px)
                    size_map = {
                        1: "heading-4", 2: "heading-4", # 16px
                        3: "heading",                  # 16px (飞书最接近 15px 的档位)
                        4: "normal", 5: "normal", 6: "normal" # 14px
                    }
                    elements.append({
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{title_text}**",
                            "text_size": size_map.get(level, "heading")
                        }
                    })
                else:
                    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": sub_part.strip()}})
        
        return elements

    @classmethod
    def _parse_markdown_table(cls, md_table: str) -> Optional[dict]:
        """将单个 Markdown 表格文本解析为飞书 JSON 表格 (带智能权重计算)"""
        lines = [l.strip() for l in md_table.strip().split("\n") if l.strip()]
        if len(lines) < 3: return None

        # 1. 提取原始数据
        header_cells = [c.strip() for c in lines[0].split("|") if c.strip()][:FEISHU_CARD_COLUMN_LIMIT]
        rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells: rows.append(cells)
        
        if not rows: return None

        # 2. 计算每列的最大字符长度（用于权重分配）
        col_count = len(header_cells)
        max_lengths = [len(h) for h in header_cells]
        for row in rows:
            for i in range(min(len(row), col_count)):
                max_lengths[i] = max(max_lengths[i], len(row[i]))
        
        total_len = sum(max_lengths) or 1
        
        # 3. 构造列描述，分配权重
        columns = []
        col_names = []
        for i, cell in enumerate(header_cells):
            name = f"col_{i}"
            # 计算权重比例：最小 5%，防止过窄
            weight = max(5, int((max_lengths[i] / total_len) * 100))
            columns.append({
                "name": name, 
                "display_name": cell, 
                "data_type": "markdown",
                "width": f"{weight}%" # 使用百分比权重
            })
            col_names.append(name)

        # 4. 组装行数据
        formatted_rows = []
        for row in rows:
            record = {}
            for i, cell in enumerate(row):
                if i < len(col_names):
                    record[col_names[i]] = cell
            formatted_rows.append(record)

        return {
            "tag": "table",
            "page_size": 10,
            "row_height": "auto",      # 自适应内容高度
            "row_max_height": "120px", # 限制单行最大高度，防止布局异常，同时配合 auto 模式
            "header_style": {"background_style": "grey", "bold": True},
            "columns": columns,
            "rows": formatted_rows
        }

    @classmethod
    def _optimize_markdown_style(cls, text: str) -> str:
        """飞书 lark_md 语法补丁"""
        processed = text
        processed = re.sub(r'([^\n])\n([-*•] |\d+\. )', r'\1\n\n\2', processed)
        processed = re.sub(r'\*\*\s+(.*?)\s+\*\*', r'**\1**', processed)
        processed = re.sub(r'__(.*?)__', r'**\1**', processed)
        processed = re.sub(r'^>\s*(.*)', r'▎ \1', processed, flags=re.MULTILINE)
        return processed

    @classmethod
    def format(cls, text: str) -> str:
        """[降级接口] 仅执行文本预算处理。"""
        if not text: return ""
        processed = cls._sanitize_table_budget(text)
        processed = cls._optimize_markdown_style(processed)
        return processed

    @classmethod
    def _sanitize_table_budget(cls, text: str) -> str:
        """表格数量预检查及强制降级逻辑"""
        table_pattern = r'((?:\|.*\|(?:\n|$)){2,})'
        tables = re.findall(table_pattern, text)
        
        if len(tables) <= FEISHU_CARD_TABLE_LIMIT:
            return text

        logger.warning(f"Table budget exceeded ({len(tables)} > {FEISHU_CARD_TABLE_LIMIT}).")
        parts = re.split(table_pattern, text)
        result = []
        table_count = 0
        for part in parts:
            if re.match(table_pattern, part):
                table_count += 1
                if table_count > FEISHU_CARD_TABLE_LIMIT:
                    result.append(f"```text\n{part.strip()}\n```")
                else:
                    result.append(part)
            else:
                result.append(part)
        return "".join(result)
