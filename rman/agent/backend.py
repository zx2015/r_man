import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import time
import openai
from openai import AsyncOpenAI
from rman.common.config import config
from loguru import logger

# --- 熔断器参数 ---
_CB_FAILURE_THRESHOLD = 3    # 连续失败 N 次后触发熔断
_CB_RECOVERY_SECONDS  = 60   # 熔断后允许一次探测请求的间隔(秒)

# --- 退避参数 ---
_BACKOFF_BASE = 1.0           # 指数退避基础延迟(秒)
_BACKOFF_MAX  = 30.0          # 最大退避上限(秒)


class _CircuitState(Enum):
    CLOSED    = "closed"      # 正常通行
    OPEN      = "open"        # 熔断，拒绝请求
    HALF_OPEN = "half_open"   # 探测恢复中，放行一次


@dataclass
class _ModelCircuit:
    """单个模型的熔断器状态机"""
    state: _CircuitState = _CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None

    def is_available(self) -> bool:
        """判断模型当前是否可接受请求"""
        if self.state == _CircuitState.CLOSED:
            return True
        if self.state == _CircuitState.OPEN:
            elapsed = (datetime.now() - self.last_failure_time).total_seconds() if self.last_failure_time else 0
            if elapsed > _CB_RECOVERY_SECONDS:
                self.state = _CircuitState.HALF_OPEN
                return True   # 放行一次探测请求
            return False
        return True           # HALF_OPEN：放行探测请求

    def record_success(self, model_name: str):
        """请求成功 → 重置为健康状态"""
        if self.state != _CircuitState.CLOSED:
            logger.success(f"Circuit breaker: [{model_name}] recovered → CLOSED")
        self.state = _CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def record_failure(self, model_name: str):
        """请求失败 → 累积故障，必要时触发熔断"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.state == _CircuitState.HALF_OPEN:
            # 探测失败 → 重新熔断
            self.state = _CircuitState.OPEN
            logger.warning(f"Circuit breaker: [{model_name}] probe failed → back to OPEN")
        elif self.state == _CircuitState.CLOSED and self.failure_count >= _CB_FAILURE_THRESHOLD:
            self.state = _CircuitState.OPEN
            logger.error(f"Circuit breaker: [{model_name}] TRIPPED after {self.failure_count} consecutive failures")


class LLMBackend:
    """LLM 后端适配器，支持多级 Fallback、指数退避 + Jitter 与熔断器"""
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

        # 每个模型独立维护熔断器，挂载在单例上以跨请求持久化
        self._circuits: Dict[str, _ModelCircuit] = {}

    def _get_circuit(self, model_name: str) -> _ModelCircuit:
        if model_name not in self._circuits:
            self._circuits[model_name] = _ModelCircuit()
        return self._circuits[model_name]

    @staticmethod
    def _calc_backoff(attempt: int, retry_after: Optional[float] = None) -> float:
        """计算退避延迟：优先使用 Retry-After 头，否则指数退避 + 均匀抖动"""
        if retry_after is not None:
            return min(retry_after, _BACKOFF_MAX)
        jitter = random.uniform(0.0, _BACKOFF_BASE)
        return min(_BACKOFF_BASE * (2 ** attempt) + jitter, _BACKOFF_MAX)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        model_override: Optional[str] = None,
        max_tokens_override: Optional[int] = None,
    ) -> Tuple[Any, Any]:
        """
        带故障转移的对话请求。
        - model_override: 指定单一模型（跳过 Fallback 链，适用于摘要等后台任务）
        - max_tokens_override: 覆盖全局 max_tokens，用于强制执行 Token 预算
        依次尝试: main_model -> fallback_model[0] -> fallback_model[1] ...
        熔断器: 连续失败 3 次的模型将被屏蔽 60 秒后自动探测恢复
        """
        models_to_try = [model_override] if model_override else [self.main_model] + self.fallback_models
        effective_max_tokens = max_tokens_override if max_tokens_override is not None else self.max_tokens
        last_exception = None

        for idx, model_name in enumerate(models_to_try):
            circuit = self._get_circuit(model_name)

            # 熔断检查：跳过不可用模型，无需等待
            if not circuit.is_available():
                logger.warning(f"Circuit OPEN for [{model_name}], skipping to next fallback.")
                continue

            start_time = time.time()
            is_fallback = idx > 0
            prefix = "[Fallback] " if is_fallback else ""

            try:
                if is_fallback:
                    logger.warning(f"{prefix}Switching to fallback model: {model_name} (Attempt {idx}/{len(models_to_try)-1})")

                logger.info(f">>> LLM Request {prefix}[Model: {model_name}] START")

                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": effective_max_tokens,
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

                circuit.record_success(model_name)
                return message, usage

            except Exception as e:
                duration = time.time() - start_time
                last_exception = e
                is_retryable = False
                retry_after: Optional[float] = None

                # 1. 识别 OpenAI 状态码
                if isinstance(e, openai.APIStatusError):
                    if e.status_code == 429 or e.status_code >= 500:
                        is_retryable = True
                        # 解析 Retry-After 头，让服务端指导退避时间
                        resp = getattr(e, 'response', None)
                        if resp is not None:
                            ra = resp.headers.get('Retry-After') or resp.headers.get('retry-after')
                            if ra:
                                try:
                                    retry_after = float(ra)
                                except ValueError:
                                    pass

                # 2. 识别超时
                elif isinstance(e, openai.APITimeoutError):
                    is_retryable = True

                # 3. 兜底字符串匹配（处理某些非标准 Proxy 返回）
                else:
                    if any(code in str(e) for code in ["429", "529", "500", "502", "503"]):
                        is_retryable = True

                if is_retryable:
                    # 仅可重试错误才累计熔断计数（鉴权失败等非基础设施故障不计入）
                    circuit.record_failure(model_name)

                    if idx < len(models_to_try) - 1:
                        delay = self._calc_backoff(idx, retry_after)
                        logger.error(f"!!! LLM Request FAILED [Model: {model_name}, Duration: {duration:.2f}s]: {e}. Backing off {delay:.1f}s then trying next model...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.critical(f"!!! All models exhausted. Last error: {e}")
                        raise
                else:
                    # 非可重试错误（鉴权失败、参数错误等）立即抛出，不污染熔断计数
                    logger.critical(f"!!! LLM Request FAILED FATALLY [Model: {model_name}]: {e}")
                    raise

        # 所有模型均被熔断跳过
        if last_exception:
            raise last_exception
        raise RuntimeError(f"All models are circuit-broken. Status: {self.get_circuit_status()}")

    def get_circuit_status(self) -> Dict[str, str]:
        """返回所有模型的熔断器状态（用于诊断）"""
        return {
            model: f"{c.state.value} (failures={c.failure_count})"
            for model, c in self._circuits.items()
        }


# 单例模式
llm_backend = LLMBackend()
