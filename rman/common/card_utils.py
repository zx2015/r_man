from typing import Optional, Any
import re
import json
from loguru import logger

class CardFormatter:
    """飞书卡片格式化流水线：预算预处理 -> 样式优化 -> 结构转换"""

    @classmethod
    def format(cls, text: str) -> str:
        """主入口：执行完整的清洗流水线"""
        if not text:
            return ""
        
        # 1. 表格预算处理
        processed = cls._sanitize_table_budget(text)
        
        # 2. 样式优化
        processed = cls._optimize_markdown_style(processed)
        
        return processed

    @classmethod
    def _sanitize_table_budget(cls, text: str, threshold: int = 3) -> str:
        """
        表格预算管理：防止卡片因表格组件过多报错 (11310)。
        前 N 个表格保留原样（供后续可能的组件化），超出的降级为代码块。
        """
        # 识别 Markdown 表格的简单正则 (至少两行，包含 | 和 -)
        table_pattern = r'((?:\|.*\|(?:\n|$)){2,})'
        
        tables = re.findall(table_pattern, text)
        if len(tables) <= threshold:
            return text

        logger.warning(f"Table budget exceeded ({len(tables)} > {threshold}). Downgrading extra tables.")
        
        parts = re.split(table_pattern, text)
        result = []
        table_count = 0
        
        for part in parts:
            if re.match(table_pattern, part):
                table_count += 1
                if table_count > threshold:
                    # 降级为代码块
                    result.append(f"```text\n{part.strip()}\n```")
                else:
                    result.append(part)
            else:
                result.append(part)
        
        return "".join(result)

    @classmethod
    def format_with_components(cls, text: str) -> list:
        """
        核心渲染方法：执行 Pipeline 并产出组件列表。
        不再返回纯字符串，而是返回飞书 elements 列表。
        """
        if not text:
            return []

        # 1. 执行文本级优化
        processed = cls._optimize_markdown_style(text)
        
        # 2. 识别并转换表格
        elements = cls._convert_tables_to_components(processed)
        
        return elements

    @classmethod
    def _convert_tables_to_components(cls, text: str) -> list:
        """识别 Markdown 表格并将其转为飞书原生 table 组件块"""
        elements = []
        # 匹配标准 Markdown 表格
        table_pattern = r'(\n(?:\|.*\|(?:\n|$)){2,})'
        
        parts = re.split(table_pattern, text)
        table_count = 0

        for part in parts:
            if re.match(table_pattern, part) and table_count < 3:
                table_count += 1
                try:
                    table_comp = cls._parse_markdown_table(part)
                    if table_comp:
                        elements.append(table_comp)
                        continue
                except:
                    pass
            
            # 如果不是表格或解析失败，作为普通 Markdown 文本
            if part.strip():
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": part.strip()}})
        
        return elements

    @classmethod
    def _parse_markdown_table(cls, md_table: str) -> Optional[dict]:
        """将单个 Markdown 表格文本解析为飞书 JSON 表格"""
        lines = [l.strip() for l in md_table.strip().split("\n") if l.strip()]
        if len(lines) < 3: return None # 至少要有表头、分割线、数据行

        # 提取列
        header_cells = [c.strip() for c in lines[0].split("|") if c.strip()]
        columns = []
        col_names = []
        for i, cell in enumerate(header_cells):
            name = f"col_{i}"
            columns.append({"name": name, "display_name": cell, "data_type": "markdown"})
            col_names.append(name)

        # 提取行
        rows = []
        for line in lines[2:]: # 跳过分割线
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
        
        # 1. 列表间距修复：在列表项前强制注入双换行，确保缩进渲染
        # 匹配：非换行符 + 换行 + (列表符号)
        processed = re.sub(r'([^\n])\n([-*•] |\d+\. )', r'\1\n\n\2', processed)
        
        # 2. 加粗语法收紧：移除 ** 内部的空格，防止飞书渲染失效
        processed = re.sub(r'\*\*\s+(.*?)\s+\*\*', r'**\1**', processed)
        
        # 3. 符号标准化：将 __text__ 统一为 **text**
        processed = re.sub(r'__(.*?)__', r'**\1**', processed)
        
        # 4. 引用块美化：将 > 转换为飞书支持更好的 ▎符号（模拟引用感）
        processed = re.sub(r'^>\s*(.*)', r'▎ \1', processed, flags=re.MULTILINE)
        
        # 5. Mention 转换 (预留): 如果有特殊标记 [Name](id)，可转为 <at id=...></at>
        # TODO: 根据需要实现具体的 Mention 识别
        
        return processed
