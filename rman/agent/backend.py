from typing import List, Dict, Any, Optional, Tuple
from openai import AsyncOpenAI
from rman.common.config import config
from loguru import logger

class LLMBackend:
    """LLM 后端适配器，统一处理 OpenAI 兼容接口"""
    def __init__(self):
        self.provider = config.llm.provider
        self.api_key = config.llm.api_key
        self.base_url = config.llm.base_url
        self.model = config.llm.model
        self.temperature = config.llm.temperature
        self.max_tokens = config.llm.max_tokens
        self.timeout = config.llm.timeout

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

    async def chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Tuple[Any, Any]:
        """
        执行对话请求，支持原生 Tool Calling
        返回: (message 对象, usage 对象)
        """
        import time
        start_time = time.time()
        try:
            logger.info(f">>> LLM Request [Model: {self.model}] START")
            
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**kwargs)
            
            message = response.choices[0].message
            usage = response.usage
            duration = time.time() - start_time
            
            # 日志增强
            tool_calls_count = len(message.tool_calls) if message.tool_calls else 0
            logger.info(f"<<< LLM Response END [Duration: {duration:.2f}s, ToolCalls: {tool_calls_count}, Tokens: {usage.total_tokens if usage else 'N/A'}]")
            
            return message, usage
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"!!! LLM Request FAILED [Duration: {duration:.2f}s]: {e}")
            raise

# 单例模式
llm_backend = LLMBackend()
