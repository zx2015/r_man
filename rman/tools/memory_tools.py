from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool
from rman.storage.memory import memory_store
from rman.agent.summarizer import memory_summarizer
from loguru import logger

class MemorySearchParams(BaseModel):
    query: str = Field(..., description="搜索关键词或描述，用于语义匹配历史记忆")
    limit: int = Field(3, description="返回的相关记录数量上限")

class MemorySearchTool(BaseTool):
    name = "memory_search"
    description = "搜索长期记忆，寻找与当前任务相关的历史背景、执行结果或用户偏好。"
    parameters_schema = MemorySearchParams

    async def execute(self, query: str, limit: int = 3, **kwargs) -> str: # type: ignore[override]
        # 1. 对查询内容进行向量化
        vec = await memory_summarizer.embed(query)
        if not vec:
            return "Error: 向量化查询失败，无法搜索。请检查 Embedding API 配置。"
            
        # 2. 执行搜索
        results = await memory_store.search(vec, limit=limit)
        
        if not results:
            return "Observation: 未找到相关的历史记忆。"
            
        # 3. 格式化结果
        output = ["Observation: 找到以下相关历史记录："]
        for i, res in enumerate(results):
            output.append(f"--- 记录 {i+1} [{res['time']}] ---")
            output.append(f"摘要: {res['summary']}")
            output.append(f"相似度分: {res['score']:.4f}")
            
        return "\n".join(output)

class MemoryDumpParams(BaseModel):
    summary: str = Field(..., description="要存入记忆的脱敏内容摘要")
    tag: str = Field("general", description="可选标签")
    ttl_days: int = Field(90, description="有效期天数，默认 90 天。过期后将被自动清理。")

class MemoryDumpTool(BaseTool):
    name = "memory_dump"
    description = "将当前学到的重要知识、用户偏好或任务总结存入长期记忆。"
    parameters_schema = MemoryDumpParams

    async def execute(self, summary: str, tag: str = "general", ttl_days: int = 90, **kwargs) -> str: # type: ignore[override]
        # 1. 对摘要进行向量化
        vec = await memory_summarizer.embed(summary)
        if not vec:
            return "Error: 向量化失败。"
            
        # 2. 持久化存储
        try:
            await memory_store.save(summary, vec, tag=tag, ttl_days=ttl_days)
            return f"Success: 已存入长期记忆，有效期 {ttl_days} 天。"
        except Exception as e:
            return f"Error: 存入失败 - {str(e)}"
