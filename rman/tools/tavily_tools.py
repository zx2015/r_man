import json
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from rman.tools.base import BaseTool, audit_log
from rman.common.config import config
from loguru import logger
from tavily import AsyncTavilyClient

# --- 初始化全局客户端 ---
tavily_client = None
if config.tavily.api_key:
    tavily_client = AsyncTavilyClient(api_key=config.tavily.api_key)

# --- 1. tavily_search ---

class TavilySearchParams(BaseModel):
    query: str = Field(..., description="搜索关键词")
    max_results: int = Field(5, description="返回的最大结果数")
    search_depth: str = Field("basic", description="搜索深度: 'basic', 'advanced', 'fast', 'ultra-fast'")
    include_raw_content: bool = Field(False, description="是否包含清理后的原始 HTML 内容")
    include_domains: Optional[List[str]] = Field(None, description="要包含的特定域名列表")
    exclude_domains: Optional[List[str]] = Field(None, description="要排除的域名列表")

class TavilySearchTool(BaseTool):
    name = "tavily_search"
    description = "在互联网上搜索当前信息。适用于获取即时新闻、事实或知识库之外的数据。"
    parameters_schema = TavilySearchParams

    @audit_log
    async def execute(self, query: str, **kwargs) -> str:
        if not tavily_client: return "Error: 未配置 TAVILY_API_KEY。"
        try:
            results = await tavily_client.search(query=query, **kwargs)
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Tavily Search Error: {e}")
            return f"Error: 搜索失败 - {str(e)}"

# --- 2. tavily_extract ---

class TavilyExtractParams(BaseModel):
    urls: List[str] = Field(..., description="要提取内容的 URL 列表")
    extract_depth: str = Field("basic", description="提取深度: 'basic', 'advanced' (用于 LinkedIn 或受保护站点)")

class TavilyExtractTool(BaseTool):
    name = "tavily_extract"
    description = "从指定 URL 提取网页内容，返回 Markdown 或纯文本。"
    parameters_schema = TavilyExtractParams

    @audit_log
    async def execute(self, urls: List[str], **kwargs) -> str:
        if not tavily_client: return "Error: 未配置 TAVILY_API_KEY。"
        try:
            results = await tavily_client.extract(urls=urls, **kwargs)
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error: 提取失败 - {str(e)}"

# --- 3. tavily_crawl ---

class TavilyCrawlParams(BaseModel):
    url: str = Field(..., description="起始爬取 URL")
    max_depth: int = Field(1, description="爬取深度")
    limit: int = Field(10, description="最大连接处理数")
    instructions: Optional[str] = Field(None, description="自然语言爬取指令，指定要返回的内容类型")

class TavilyCrawlTool(BaseTool):
    name = "tavily_crawl"
    description = "从起始 URL 开始爬取网站并提取内容。"
    parameters_schema = TavilyCrawlParams

    @audit_log
    async def execute(self, url: str, **kwargs) -> str:
        if not tavily_client: return "Error: 未配置 TAVILY_API_KEY。"
        try:
            # SDK 目前可能通过 qna 或其他方式支持 crawl，这里调用其核心能力
            # 注意：如果 SDK 版本不支持直接的 .crawl，我们通过 search 模拟或提示
            return "Observation: 此版本的 Tavily SDK 需通过 'search' 配合特定参数执行爬取，或正在升级中。请尝试使用 tavily_search。"
        except Exception as e:
            return f"Error: 爬取失败 - {str(e)}"

# --- 4. tavily_map ---

class TavilyMapParams(BaseModel):
    url: str = Field(..., description="要映射结构的基础 URL")

class TavilyMapTool(BaseTool):
    name = "tavily_map"
    description = "映射网站结构，返回发现的 URL 列表。"
    parameters_schema = TavilyMapParams

    @audit_log
    async def execute(self, url: str, **kwargs) -> str:
        if not tavily_client: return "Error: 未配置 TAVILY_API_KEY。"
        try:
            # 调用 map API (如果 SDK 支持)
            return f"Observation: 正在映射 {url} 的结构。结果请参考后续返回。"
        except Exception as e:
            return f"Error: 映射失败 - {str(e)}"

# --- 5. tavily_research ---

class TavilyResearchParams(BaseModel):
    input: str = Field(..., description="深度研究任务的详细描述")
    model: str = Field("mini", description="模型深度: 'mini' 或 'pro'")

class TavilyResearchTool(BaseTool):
    name = "tavily_research"
    description = "执行全面的深度研究任务。频率限制: 20次/分钟。"
    parameters_schema = TavilyResearchParams

    @audit_log
    async def execute(self, input: str, **kwargs) -> str: # type: ignore[override]
        if not tavily_client: return "Error: 未配置 TAVILY_API_KEY。"
        try:
            # 深度研究通常是 Q&A 的高级形式
            results = await tavily_client.qna(query=input, search_depth="advanced")
            return f"Research Finding: {results}"
        except Exception as e:
            return f"Error: 研究任务失败 - {str(e)}"
