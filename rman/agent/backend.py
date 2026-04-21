import asyncio
from typing import List, Dict, Any, Optional, Tuple
import time
import openai
from openai import AsyncOpenAI
from rman.common.config import config
from loguru import logger

class LLMBackend:
    """LLM 后端适配器，支持多级 Fallback 故障转移"""
    def __init__(self):
        self.provider = config.llm.provider
        self.api_key = config.llm.api_key
        self.base_url = config.llm.base_url
        self.main_model = config.llm.model
        self.fallback_models = config.llm.fallback_models
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
        带故障转移的对话请求。
        依次尝试: main_model -> fallback_model[0] -> fallback_model[1] ...
        """
        # 构建待尝试的模型列表
        models_to_try = [self.main_model] + self.fallback_models
        last_exception = None

        for idx, model_name in enumerate(models_to_try):
            start_time = time.time()
            is_fallback = idx > 0
            prefix = "[Fallback] " if is_fallback else ""
            
            try:
                if is_fallback:
                    logger.warning(f"{prefix}Switching to fallback model: {model_name} (Attempt {idx}/{len(models_to_try)-1})")
                
                logger.info(f">>> LLM Request {prefix}[Model: {model_name}] START")
                
                kwargs = {
                    "model": model_name,
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
                
                tool_calls_count = len(message.tool_calls) if message.tool_calls else 0
                logger.success(f"<<< LLM Response END [Model: {model_name}, Duration: {duration:.2f}s, ToolCalls: {tool_calls_count}, Tokens: {usage.total_tokens if usage else 'N/A'}]")
                
                return message, usage

            except Exception as e:
                duration = time.time() - start_time
                last_exception = e
                
                # 判定是否触发 Fallback
                is_retryable = False
                
                # 1. 识别 OpenAI 状态码
                if isinstance(e, openai.APIStatusError):
                    # 429: 频率限制, 5xx: 服务端错误 (包含 529 拥挤)
                    if e.status_code == 429 or e.status_code >= 500:
                        is_retryable = True
                
                # 2. 识别超时
                elif isinstance(e, openai.APITimeoutError):
                    is_retryable = True
                
                # 3. 兜底字符串匹配 (处理某些非标准 Proxy 返回)
                else:
                    error_str = str(e)
                    if any(code in error_str for code in ["429", "529", "500", "502", "503"]):
                        is_retryable = True
                
                if is_retryable and idx < len(models_to_try) - 1:
                    logger.error(f"!!! LLM Request FAILED [Model: {model_name}, Duration: {duration:.2f}s]: {e}. Triggering fallback...")
                    # 避免紧凑重试，给服务端一点缓冲
                    await asyncio.sleep(1)
                    continue
                else:
                    logger.critical(f"!!! LLM Request FAILED FATALLY [Model: {model_name}]: {e}")
                    raise last_exception

        raise last_exception

# 单例模式
llm_backend = LLMBackend()
