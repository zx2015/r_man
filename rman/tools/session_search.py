from pydantic import BaseModel, Field
from typing import Optional, List
from rman.tools.base import BaseTool
from rman.storage.session import session_store
from loguru import logger

class SessionSearchInput(BaseModel):
    query: str = Field(..., description="要搜索的关键词或 FTS5 查询语句")
    limit: int = Field(5, description="返回结果的最大数量")

class SessionSearchTool(BaseTool):
    name: str = "session_search"
    description: str = "在历史对话中搜索关键词。它会自动排除当前会话内容，仅回溯久远的历史背景。"
    parameters_schema: type[BaseModel] = SessionSearchInput

    async def execute(self, query: str, limit: int = 5, **kwargs) -> str:
        """执行全局全文搜索"""
        try:
            results = session_store.search_sessions(
                query=query, 
                limit=limit
            )
            
            if not results:
                return f"未在历史会话中找到与 '{query}' 相关的记录。"

            formatted_results = ["### 历史会话全局搜索结果"]
            for r in results:
                line = f"- [{r['timestamp']}] Session: {r['chat_id']} | Role: {r['role']}\n  Content: {r['content'][:300]}..."
                formatted_results.append(line)
            
            return "\n\n".join(formatted_results)
            
        except Exception as e:
            logger.error(f"Session search failed: {e}")
            return f"搜索失败: {e}"
