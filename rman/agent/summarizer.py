import json
from typing import List, Dict
from loguru import logger
from rman.agent.backend import llm_backend
from rman.common.config import config
from openai import AsyncOpenAI

SUMMARIZER_PROMPT = """你是一个记忆构建专家。请将以下对话总结为一段简短的摘要。
规则：
1. 提取任务核心目标、成功执行的命令、以及发现的用户偏好。
2. **隐私清理**: 严禁包含任何 Key、密码、IP 地址或敏感 Token。将它们替换为 [REDACTED]。
3. 只输出摘要文本，不含任何解释。
4. 语言必须与原文保持一致。"""

class MemorySummarizer:
    """负责生成脱敏摘要与向量"""
    def __init__(self):
        # 独立的 Embedding 客户端 (通常使用与 LLM 不同的模型)
        self.emb_client = AsyncOpenAI(
            api_key=config.memory.embedding.api_key,
            base_url=config.memory.embedding.base_url
        )
        self.emb_model = config.memory.embedding.model

    async def summarize(self, messages: List[Dict[str, str]]) -> str:
        """调用 LLM 生成脱敏摘要"""
        # 排除 System Prompt，只总结对话
        chat_content = "\n".join([f"{m['role']}: {m['content']}" for m in messages if m['role'] != 'system'])
        
        prompt = [
            {"role": "system", "content": SUMMARIZER_PROMPT},
            {"role": "user", "content": f"请总结以下对话：\n\n{chat_content}"}
        ]
        
        try:
            # 这里的 usage 我们暂时忽略，因为它是后台任务
            message, _ = await llm_backend.chat(prompt)
            return message.content.strip()
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return ""

    async def embed(self, text: str) -> List[float]:
        """将文本转换为向量"""
        try:
            response = await self.emb_client.embeddings.create(
                input=text,
                model=self.emb_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

# 单例
memory_summarizer = MemorySummarizer()
