import json
import re
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Callable, Coroutine
from loguru import logger

from rman.common.config import config
from rman.agent.backend import llm_backend
from rman.agent.prompt import prompt_builder
from rman.tools.registry import tool_registry
from rman.storage.session import session_store

class AgentRunner:
    """ReAct Agent 执行引擎，支持 5 层 Context 结构、80/60 压缩与实时持久化"""
    def __init__(self, session_id: str, chat_id: str = ""):
        self.session_id = session_id
        self.chat_id = chat_id
        self.max_iterations = config.agent.max_iterations
        self.messages: List[Dict[str, Any]] = []

    async def run(self, user_input: str, on_intermediate_status: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None) -> Tuple[str, Dict[str, Any]]:
        """运行 ReAct 循环"""
        # 1. 系统层 (System Layer)
        tool_descriptions = tool_registry.generate_tools_description()
        openai_tools = tool_registry.get_openai_tools()
        system_prompt = prompt_builder.build(tool_descriptions=tool_descriptions)
        
        # 2. 加载历史 (包含 Summary 层和近期消息层)
        history = []
        if self.chat_id:
            history = session_store.load_history(self.chat_id)
        
        self.messages = [{"role": "system", "content": system_prompt}]
        self.messages.extend(history)
        
        # 注入当前 User 输入并持久化
        self.messages.append({"role": "user", "content": user_input})
        self._persist_message("user", user_input)
        
        logger.info(f"Session {self.session_id} started. History: {len(history)} messages.")

        final_response = ""
        total_usage = {"input": 0, "output": 0, "model": config.llm.model}

        for i in range(self.max_iterations):
            # --- 自动窗口压缩 (80/60 准则) ---
            await self._check_and_compress_context()
            
            # 调用 LLM
            llm_message, usage = await llm_backend.chat(self.messages, tools=openai_tools if openai_tools else None)
            if usage:
                total_usage["input"] += usage.prompt_tokens
                total_usage["output"] += usage.completion_tokens
            
            # 记录 Assistant 回复并持久化
            assistant_content = llm_message.content or ""
            msg_to_add: Dict[str, Any] = {"role": "assistant", "content": assistant_content}
            if llm_message.tool_calls:
                msg_to_add["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    } for tc in llm_message.tool_calls
                ]
            
            self.messages.append(msg_to_add)
            # 对 Assistant 消息进行持久化 (包括 tool_calls 内容)
            self._persist_message("assistant", assistant_content, tool_calls=msg_to_add.get("tool_calls"))

            # 解析
            think, final, text_actions = self._parse_output(assistant_content)
            if think: logger.debug(f"Thought: {think}")

            # 汇总 Action
            actions_to_run = []
            if llm_message.tool_calls:
                for tc in llm_message.tool_calls:
                    try:
                        actions_to_run.append({"tool": tc.function.name, "parameters": json.loads(tc.function.arguments), "call_id": tc.id})
                    except: pass
            elif text_actions:
                actions_to_run = text_actions

            # 中间预告
            if actions_to_run and on_intermediate_status:
                for action in actions_to_run:
                    tool_name = action.get("tool")
                    params = action.get("parameters", {})
                    intent = params.get("description") or params.get("instruction")
                    desc = final if final else (f"✅ 准备执行 `{tool_name}`：{intent}" if intent else f"⚙️ 正在调用工具 `{tool_name}`...")
                    await on_intermediate_status(desc)
                    break

            # 执行工具 (Observation Layer)
            if actions_to_run:
                for action in actions_to_run:
                    tool_name = str(action.get("tool"))
                    params = action.get("parameters", {})
                    call_id = action.get("call_id")
                    
                    tool = tool_registry.get_tool(tool_name)
                    obs = await tool.execute(**params) if tool else f"Error: 找不到工具 {tool_name}。"
                    
                    # 仅保留硬熔断（100,000 字符），防止单次请求超过 LLM API 物理极限
                    # 不再进行 AI 摘要，确保原始数据的纯净性
                    if len(obs) > 100000:
                        logger.warning(f"Observation exceeds 100k chars. Applying hard truncation.")
                        obs = obs[:100000] + "\n\n[Warning: Output exceeds 100k chars and was hard-truncated for system stability.]"

                    # 记录 Observation 层并持久化
                    if call_id:
                        obs_msg = {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": obs}
                    else:
                        obs_msg = {"role": "user", "content": f"Observation for {tool_name}: {obs}"}
                    
                    self.messages.append(obs_msg)
                    self._persist_message(obs_msg["role"], obs_msg["content"], name=obs_msg.get("name"), tool_call_id=obs_msg.get("tool_call_id"))

                # 执行完工具后，必须进入下一轮 LLM 循环以分析结果
                continue
            
            elif final:
                return final, total_usage
            
            else:
                prompt = "系统提示：请继续。如果任务已完成，请回复 <final>；如果需要工具，请调用。"
                self.messages.append({"role": "user", "content": prompt})
                # 此类引导消息不强制持久化，以免污染历史

        return final_response or "已达到最大迭代次数。", total_usage

    def _persist_message(self, role: str, content: str, name: str = None, tool_call_id: str = None, tool_calls: Any = None):
        """内部持久化逻辑，支持结构化 tool_calls"""
        if not self.chat_id: return
        
        asyncio.create_task(asyncio.to_thread(
            session_store.save_message, 
            self.chat_id, role, content, name, tool_call_id, tool_calls
        ))

    async def _check_and_compress_context(self):
        """80/60 自动窗口压缩"""
        total_chars = sum(len(str(m.get("content", ""))) for m in self.messages)
        estimated_tokens = total_chars // 2 
        if estimated_tokens < config.llm.context_window * 0.8: return

        logger.warning(f"Context pressure ({estimated_tokens} tokens). Starting 80/60 compression...")
        if len(self.messages) <= 10: return

        system_msg = self.messages[0]
        preserved_msgs = self.messages[-5:] # 保留最近 5 条
        compressible_msgs = self.messages[1:-5]
        
        try:
            from rman.agent.summarizer import memory_summarizer
            summary_text = await memory_summarizer.summarize_react_trace(json.dumps(compressible_msgs, ensure_ascii=False))
            # 使用 assistant 角色记录技术摘要，并加上系统备注前缀，符合语义
            summary_msg = {"role": "assistant", "content": f"[System Note: Context Summary]\n{summary_text}\n---"}
            
            # 重组
            self.messages = [system_msg, summary_msg] + preserved_msgs
            
            # 持久化压缩摘要
            self._persist_message(summary_msg["role"], summary_msg["content"])
            logger.info("Context compression completed.")
        except Exception as e:
            logger.error(f"Compression failed: {e}")

    def _parse_output(self, text: str) -> Tuple[Optional[str], Optional[str], List[Dict]]:
        think = None
        final = None
        actions = []
        think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
        if think_match: think = think_match.group(1).strip()
        final_match = re.search(r"<final>(.*?)</final>", text, re.DOTALL)
        if final_match: final = final_match.group(1).strip()
        action_matches = re.finditer(r"Action:\s*(\{.*?\})", text, re.DOTALL)
        for match in action_matches:
            try:
                actions.append(json.loads(match.group(1).strip()))
            except: pass
        return think, final, actions
