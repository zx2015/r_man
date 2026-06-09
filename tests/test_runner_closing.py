"""
单元测试：AgentRunner N+1 收尾轮机制

覆盖场景：
1. _run_closing_summary - max_iterations 原因：正常 LLM 返回
2. _run_closing_summary - deadlock 原因：prompt 不同、正常返回
3. _run_closing_summary - token 累加到 total_usage
4. _run_closing_summary - self.messages 不被污染
5. _run_closing_summary - LLM 失败降级到 _build_progress_summary
6. _run_closing_summary - LLM 和降级都失败，返回兜底文字
7. run() - 死锁路径（consecutive_empty >= 3）→ _run_closing_summary("deadlock")
8. run() - 超限路径（耗尽 max_iterations）→ _run_closing_summary("max_iterations")
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from rman.agent.runner import AgentRunner


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def make_runner(session_id: str = "test-session") -> AgentRunner:
    """创建不依赖真实配置的 AgentRunner 实例"""
    with patch("rman.agent.runner.config") as mock_cfg:
        mock_cfg.llm.model = "test-model"
        mock_cfg.agent.max_iterations = 3
        mock_cfg.llm.context_window = 128_000
        runner = AgentRunner.__new__(AgentRunner)
        runner.session_id = session_id
        runner.chat_id = ""
        runner.max_iterations = 3
        runner.messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "帮我检查一下日志"},
            {"role": "assistant", "content": "好的，我来查看日志。"},
            {"role": "tool", "content": "日志内容：一切正常", "name": "run_shell_command"},
        ]
        runner._rolling_summary = ""
    return runner


def make_llm_response(content: str, input_tokens: int = 100, output_tokens: int = 50):
    """构造 llm_backend.chat 的返回值 (message, usage)"""
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    usage = MagicMock()
    usage.prompt_tokens = input_tokens
    usage.completion_tokens = output_tokens
    return message, usage


# ---------------------------------------------------------------------------
# 1. _run_closing_summary — max_iterations 正常返回
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closing_summary_max_iterations_success():
    runner = make_runner()
    total_usage = {"input": 500, "output": 200, "model": "test-model"}

    llm_reply = "## 当前进展\n已完成步骤 1。\n\n## 下一步建议\n请执行步骤 2。"
    mock_msg, mock_usage = make_llm_response(llm_reply, input_tokens=300, output_tokens=80)

    with patch("rman.agent.runner.llm_backend") as mock_backend:
        mock_backend.chat = AsyncMock(return_value=(mock_msg, mock_usage))
        result = await runner._run_closing_summary("max_iterations", 3, total_usage)

    # 输出包含 LLM 回复内容
    assert llm_reply in result
    # 前缀说明超限原因
    assert "最大步数" in result


# ---------------------------------------------------------------------------
# 2. _run_closing_summary — deadlock 原因，使用不同 prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closing_summary_deadlock_uses_different_prompt():
    runner = make_runner()
    total_usage = {"input": 0, "output": 0, "model": "test-model"}

    captured_messages = []

    async def capture_chat(messages, tools=None):
        captured_messages.extend(messages)
        msg, usage = make_llm_response("总结内容")
        return msg, usage

    with patch("rman.agent.runner.llm_backend") as mock_backend:
        mock_backend.chat = capture_chat
        result = await runner._run_closing_summary("deadlock", 2, total_usage)

    # 最后一条注入的 prompt 应该是 deadlock 版本
    injected_prompt = captured_messages[-1]["content"]
    assert "未能产生有效输出" in injected_prompt
    # max_iterations 版本不应出现
    assert "最大步数限制" not in injected_prompt
    # 前缀说明死锁原因
    assert "提前终止" in result


# ---------------------------------------------------------------------------
# 3. _run_closing_summary — token 累加到 total_usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closing_summary_accumulates_tokens():
    runner = make_runner()
    total_usage = {"input": 1000, "output": 400, "model": "test-model"}

    mock_msg, mock_usage = make_llm_response("总结", input_tokens=200, output_tokens=60)

    with patch("rman.agent.runner.llm_backend") as mock_backend:
        mock_backend.chat = AsyncMock(return_value=(mock_msg, mock_usage))
        await runner._run_closing_summary("max_iterations", 3, total_usage)

    assert total_usage["input"] == 1200   # 1000 + 200
    assert total_usage["output"] == 460   # 400 + 60


# ---------------------------------------------------------------------------
# 4. _run_closing_summary — self.messages 不被修改
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closing_summary_does_not_mutate_messages():
    runner = make_runner()
    original_len = len(runner.messages)
    original_last = runner.messages[-1].copy()
    total_usage = {"input": 0, "output": 0, "model": "test-model"}

    mock_msg, mock_usage = make_llm_response("总结内容")

    with patch("rman.agent.runner.llm_backend") as mock_backend:
        mock_backend.chat = AsyncMock(return_value=(mock_msg, mock_usage))
        await runner._run_closing_summary("max_iterations", 3, total_usage)

    # messages 长度不变
    assert len(runner.messages) == original_len
    # 最后一条消息内容不变
    assert runner.messages[-1] == original_last


# ---------------------------------------------------------------------------
# 5. _run_closing_summary — LLM 失败，降级到 _build_progress_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closing_summary_fallback_on_llm_failure():
    runner = make_runner()
    total_usage = {"input": 0, "output": 0, "model": "test-model"}

    with patch("rman.agent.runner.llm_backend") as mock_backend, \
         patch.object(runner, "_build_progress_summary", new_callable=AsyncMock) as mock_fallback:
        mock_backend.chat = AsyncMock(side_effect=RuntimeError("API timeout"))
        mock_fallback.return_value = "自动摘要内容"

        result = await runner._run_closing_summary("max_iterations", 3, total_usage)

    mock_fallback.assert_called_once()
    assert "自动摘要内容" in result
    assert "自动摘要" in result  # 包含降级说明


# ---------------------------------------------------------------------------
# 6. _run_closing_summary — LLM 和降级都失败，返回兜底文字
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closing_summary_double_failure_returns_fallback_text():
    runner = make_runner()
    total_usage = {"input": 0, "output": 0, "model": "test-model"}

    with patch("rman.agent.runner.llm_backend") as mock_backend, \
         patch.object(runner, "_build_progress_summary", new_callable=AsyncMock) as mock_fallback:
        mock_backend.chat = AsyncMock(side_effect=RuntimeError("API down"))
        mock_fallback.side_effect = RuntimeError("DB unavailable")

        result = await runner._run_closing_summary("deadlock", 2, total_usage)

    # 应返回兜底文字，不抛异常
    assert "deadlock" in result or "退出" in result
    assert "日志" in result or "2" in result  # 包含 iteration_count 或日志提示


# ---------------------------------------------------------------------------
# 7. run() — 死锁路径调用 _run_closing_summary("deadlock", ...)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_deadlock_path_calls_closing_summary():
    """连续 3 轮空输出 → break → _run_closing_summary("deadlock", ...)"""

    def _make_empty_llm_response():
        msg = MagicMock()
        msg.content = ""       # 空输出，无 think/final/action
        msg.tool_calls = None
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        return msg, usage

    with patch("rman.agent.runner.config") as mock_cfg, \
         patch("rman.agent.runner.llm_backend") as mock_backend, \
         patch("rman.agent.runner.prompt_builder") as mock_prompt, \
         patch("rman.agent.runner.tool_registry") as mock_registry, \
         patch("rman.agent.runner.session_store") as mock_store:

        mock_cfg.llm.model = "test-model"
        mock_cfg.agent.max_iterations = 10  # 设大，让死锁先触发
        mock_cfg.llm.context_window = 128_000
        mock_prompt.build.return_value = "system prompt"
        mock_registry.generate_tools_description.return_value = ""
        mock_registry.get_openai_tools.return_value = []
        mock_store.load_history.return_value = []
        mock_backend.chat = AsyncMock(side_effect=lambda *a, **kw: _make_empty_llm_response())

        runner = AgentRunner("sess-deadlock")

        # mock _run_closing_summary 以捕获调用参数，同时避免真实 LLM 调用
        with patch.object(runner, "_run_closing_summary", new_callable=AsyncMock) as mock_closing:
            mock_closing.return_value = "收尾总结"
            result_text, result_usage = await runner.run("测试任务")

    # 验证以 deadlock 原因调用
    mock_closing.assert_called_once()
    call_args = mock_closing.call_args
    assert call_args[0][0] == "deadlock"
    # 已执行轮次应该是触发死锁时的迭代号（不超过 max_iterations）
    assert call_args[0][1] <= 10
    assert result_text == "收尾总结"


# ---------------------------------------------------------------------------
# 8. run() — 超限路径调用 _run_closing_summary("max_iterations", ...)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_max_iterations_path_calls_closing_summary():
    """每轮都调用工具但不给 final → 耗尽 max_iterations → _run_closing_summary("max_iterations", ...)"""

    call_count = 0

    def _make_tool_call_response():
        """每轮返回一个工具调用，不给 final"""
        msg = MagicMock()
        msg.content = ""
        tc = MagicMock()
        tc.id = f"call_{call_count}"
        tc.type = "function"
        tc.function.name = "run_shell_command"
        tc.function.arguments = '{"command": "echo hello"}'
        msg.tool_calls = [tc]
        usage = MagicMock()
        usage.prompt_tokens = 50
        usage.completion_tokens = 20
        return msg, usage

    async def fake_chat(messages, tools=None):
        nonlocal call_count
        call_count += 1
        return _make_tool_call_response()

    async def fake_tool_execute(**kwargs):
        return "tool output"

    with patch("rman.agent.runner.config") as mock_cfg, \
         patch("rman.agent.runner.llm_backend") as mock_backend, \
         patch("rman.agent.runner.prompt_builder") as mock_prompt, \
         patch("rman.agent.runner.tool_registry") as mock_registry, \
         patch("rman.agent.runner.session_store") as mock_store:

        mock_cfg.llm.model = "test-model"
        mock_cfg.agent.max_iterations = 3
        mock_cfg.llm.context_window = 128_000
        mock_prompt.build.return_value = "system prompt"
        mock_registry.generate_tools_description.return_value = ""
        mock_registry.get_openai_tools.return_value = []
        mock_store.load_history.return_value = []
        mock_backend.chat = fake_chat

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="tool output")
        mock_registry.get_tool.return_value = mock_tool

        runner = AgentRunner("sess-maxiter")

        with patch.object(runner, "_run_closing_summary", new_callable=AsyncMock) as mock_closing, \
             patch.object(runner, "_check_and_compress_context", new_callable=AsyncMock):
            mock_closing.return_value = "超限收尾"
            result_text, result_usage = await runner.run("测试任务")

    mock_closing.assert_called_once()
    call_args = mock_closing.call_args
    assert call_args[0][0] == "max_iterations"
    assert call_args[0][1] == 3   # exit_iteration == max_iterations
    assert result_text == "超限收尾"
    # token 应被累加（3 轮 × 50 input + 20 output）
    assert result_usage["input"] >= 150
    assert result_usage["output"] >= 60
