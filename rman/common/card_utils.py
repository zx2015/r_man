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
        """识别 Markdown 表格并将其转为飞书原生 table 组件块"""
        elements = []
        table_pattern = r'(\n(?:\|.*\|(?:\n|$)){2,})'
        
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
            
            if part.strip():
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": part.strip()}})
        
        return elements

    @classmethod
    def _parse_markdown_table(cls, md_table: str) -> Optional[dict]:
        """将单个 Markdown 表格文本解析为飞书 JSON 表格"""
        lines = [l.strip() for l in md_table.strip().split("\n") if l.strip()]
        if len(lines) < 3: return None

        # 提取列 (使用常量上限)
        header_cells = [c.strip() for c in lines[0].split("|") if c.strip()][:FEISHU_CARD_COLUMN_LIMIT]
        
        columns = []
        col_names = []
        for i, cell in enumerate(header_cells):
            name = f"col_{i}"
            columns.append({"name": name, "display_name": cell, "data_type": "markdown"})
            col_names.append(name)

        # 提取行
        rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if not cells: continue
            row = {}
            for i, cell in enumerate(cells):
                if i < len(col_names):
                    row[col_names[i]] = cell
            rows.append(row)

        if not rows: return None

        return {
            "tag": "table",
            "page_size": 10,
            "row_height": "low",
            "header_style": {"background_style": "grey", "bold": True},
            "columns": columns,
            "rows": rows
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
