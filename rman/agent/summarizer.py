import json
import re
from typing import List, Dict, Optional
from loguru import logger
from rman.agent.backend import llm_backend
from rman.common.config import config
from openai import AsyncOpenAI

# --- 确定性正则脱敏规则（LLM 处理前的第一道防线）---
_REDACT_RULES = [
    (re.compile(r'sk-[A-Za-z0-9\-_]{20,}'), '[REDACTED_KEY]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*'), 'Bearer [REDACTED_TOKEN]'),
    (re.compile(r'(?i)(?:api[_\-]?key|secret|password|token)\s*[:=]\s*\S+'), '[REDACTED_CREDENTIAL]'),
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[REDACTED_IP]'),
]

SUMMARIZER_PROMPT = """你是一个记忆构建专家。请将以下对话总结为一段简短的摘要。
规则：
1. 提取任务核心目标、成功执行的命令、以及发现的用户偏好。
2. **隐私清理**: 严禁包含任何 Key、密码、IP 地址或敏感 Token。将它们替换为 [REDACTED]。
3. 只输出摘要文本，不含任何解释。
4. 语言必须与原文保持一致。"""


def _redact(text: str) -> str:
    """正则预脱敏：在 LLM 处理前清除可检测的敏感信息"""
    for pattern, replacement in _REDACT_RULES:
        text = pattern.sub(replacement, text)
    return text


def _preprocess_trace(trace_json: str) -> str:
    """将原始 JSON 消息列表转换为可读的执行轨迹文本，降低 LLM 解析负担"""
    try:
        msgs = json.loads(trace_json)
    except Exception:
        return trace_json[:4000]

    lines = []
    for m in msgs:
        role = m.get('role', 'unknown')
        content = (m.get('content') or '').strip()
        tool_calls = m.get('tool_calls')

        if role == 'system':
            continue
        elif role == 'assistant':
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get('function', {})
                    args_preview = (fn.get('arguments') or '')[:200]
                    lines.append(f"[Action] {fn.get('name', 'unknown')}({args_preview})")
            if content:
                # 优先提取 <final> 标签降噪，过滤 <think> 推理过程
                final_match = re.search(r'<final>(.*?)</final>', content, re.DOTALL | re.IGNORECASE)
                snippet = final_match.group(1).strip() if final_match else content
                if not tool_calls:
                    lines.append(f"[Result] {snippet[:300]}")
        elif role == 'tool':
            name = m.get('name', 'tool')
            lines.append(f"[Obs/{name}] {content[:400]}")
        elif role == 'user':
            lines.append(f"[User] {content[:200]}")

    return '\n'.join(lines) if lines else trace_json[:2000]


class MemorySummarizer:
    """负责生成脱敏摘要与向量"""
    def __init__(self):
        self.emb_client = AsyncOpenAI(
            api_key=config.memory.embedding.api_key,
            base_url=config.memory.embedding.base_url
        )
        self.emb_model = config.memory.embedding.model

    def _get_summarizer_model(self) -> Optional[str]:
        """获取摘要专用模型；若未配置则返回 None，由 backend 沿用主模型"""
        m = config.llm.summarizer_model
        return m.strip() if m and m.strip() else None

    async def summarize(self, messages: List[Dict[str, str]]) -> str:
        """调用 LLM 生成脱敏摘要"""
        lines = []
        for m in messages:
            if m.get('role') == 'system':
                continue
            content = (m.get('content') or '').strip()  # 修复: tool_calls 消息 content 可能为 None
            if content:
                lines.append(f"{m['role']}: {content}")

        chat_content = _redact('\n'.join(lines))

        prompt = [
            {"role": "system", "content": SUMMARIZER_PROMPT},
            {"role": "user", "content": f"请总结以下对话：\n\n{chat_content}"}
        ]

        try:
            message, _ = await llm_backend.chat(prompt, model_override=self._get_summarizer_model())
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

    async def summarize_observation(self, tool_name: str, raw_output: str) -> str:
        """对巨大的工具输出执行智能预蒸馏"""
        sample = _redact(raw_output[:5000] + "\n...[Content Omitted]...\n" + raw_output[-5000:])
        prompt = [
            {"role": "system", "content": "你是一个系统数据分析专家。以下是一个工具执行产生的海量原始输出采样。请总结其中包含的关键信息、规律或错误模式。字数控制在 300 字以内。"},
            {"role": "user", "content": f"工具: {tool_name}\n原始输出采样: \n{sample}"}
        ]
        try:
            msg, _ = await llm_backend.chat(prompt, model_override=self._get_summarizer_model())
            return msg.content.strip()
        except Exception as e:
            logger.error(f"Observation distillation failed: {e}")
            return "[Error during distillation]"

    async def summarize_react_trace(
        self,
        trace_content: str,
        existing_summary: str = "",
        max_tokens: int = 200
    ) -> str:
        """将 ReAct 执行轨迹增量压缩为持久化技术纪要

        Args:
            trace_content: 待压缩的消息 JSON 字符串
            existing_summary: 已有的滚动摘要（差量更新用，为空则做全量摘要）
            max_tokens: 输出 Token 预算上限（强制传递给 LLM API）
        """
        # 1. 预处理：JSON → 可读文本，降低 LLM 解析噪声
        readable_trace = _preprocess_trace(trace_content)

        # 2. 正则脱敏（确定性防线，先于 LLM）
        readable_trace = _redact(readable_trace)

        # 3. Token → 字数换算（中文 1字 ≈ 1.5 tokens）
        char_limit = max(50, int(max_tokens / 1.5))

        # 4. 差量 vs 全量 Prompt
        if existing_summary:
            system_content = (
                f"你是一个资深审计专家。请将【现有摘要】与【新增执行轨迹】合并，生成一份更新的统一技术纪要。"
                f"重点保留: 任务目标、执行的工具及关键参数、遇到的错误及解决方法、最终状态。"
                f"严禁泄露 Key 或密码，用 [REDACTED] 替代。只输出摘要内容，字数控制在 {char_limit} 字以内。"
            )
            user_content = (
                f"【现有摘要】\n{existing_summary}\n\n"
                f"【新增执行轨迹】\n{readable_trace}"
            )
        else:
            system_content = (
                f"你是一个资深审计专家。请将以下 ReAct 执行轨迹压缩为技术纪要。"
                f"重点保留: 任务目标、执行的工具及关键参数、遇到的错误及解决方法、最终状态。"
                f"严禁泄露 Key 或密码，用 [REDACTED] 替代。只输出摘要内容，字数控制在 {char_limit} 字以内。"
            )
            user_content = f"【执行轨迹】\n{readable_trace}"

        prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

        try:
            msg, _ = await llm_backend.chat(
                prompt,
                model_override=self._get_summarizer_model(),
                max_tokens_override=max_tokens  # 强制执行 Token 预算
            )
            return msg.content.strip()
        except Exception as e:
            logger.error(f"Trace distillation failed: {e}")
            return self._deterministic_fallback(trace_content, existing_summary)

    def _deterministic_fallback(self, trace_content: str, existing_summary: str = "") -> str:
        """LLM 失败时的确定性规则摘要，保证压缩后不完全失忆"""
        parts = []
        if existing_summary:
            parts.append(f"[已有摘要] {existing_summary[:300]}")

        try:
            msgs = json.loads(trace_content)

            user_msgs = [m for m in msgs if m.get('role') == 'user' and m.get('content')]
            if user_msgs:
                parts.append(f"[用户请求] {(user_msgs[0].get('content') or '')[:150]}")

            tool_names = list({
                tc.get('function', {}).get('name', '')
                for m in msgs if m.get('tool_calls')
                for tc in (m.get('tool_calls') or [])
            })
            tool_call_count = sum(1 for m in msgs if m.get('tool_calls'))
            if tool_call_count:
                parts.append(f"[执行] 共调用工具 {tool_call_count} 次，使用: {', '.join(filter(None, tool_names))}")

            asst_msgs = [m for m in msgs if m.get('role') == 'assistant' and m.get('content')]
            if asst_msgs:
                last_content = asst_msgs[-1].get('content') or ''
                final_match = re.search(r'<final>(.*?)</final>', last_content, re.DOTALL | re.IGNORECASE)
                snippet = (final_match.group(1).strip() if final_match else last_content)[:200]
                parts.append(f"[最终状态] {snippet}")

        except Exception:
            parts.append("[注意] 执行了若干步骤（摘要结构解析失败）")

        return '\n'.join(parts) if parts else "执行了多个步骤（摘要生成失败）。"


# 单例
memory_summarizer = MemorySummarizer()
