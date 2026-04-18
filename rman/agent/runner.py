import re
import json
from typing import List, Dict, Any, Tuple, Optional, Callable, Coroutine
from loguru import logger
from rman.common.config import config
from rman.agent.backend import llm_backend
from rman.agent.prompt import prompt_builder
from rman.tools.registry import tool_registry

class AgentRunner:
    """ReAct Agent 执行引擎，支持标签化解析与原生工具调用预留"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.max_iterations = config.agent.max_iterations
        self.messages: List[Dict[str, str]] = []

    async def run(self, user_input: str, on_intermediate_status: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None) -> Tuple[str, Dict[str, Any]]:
        """运行 ReAct 循环直到产生最终结果。返回 (答案, 元数据)"""
        # 1. 组装 System Prompt (不再自动注入历史背景)
        tool_descriptions = tool_registry.generate_tools_description()
        openai_tools = tool_registry.get_openai_tools()
        system_prompt = prompt_builder.build(tool_descriptions=tool_descriptions)
        
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        logger.info(f"Starting ReAct loop for session {self.session_id}")

        final_response = ""
        total_usage = {"input": 0, "output": 0, "model": config.llm.model}

        for i in range(self.max_iterations):
            logger.debug(f"Iteration {i+1}/{self.max_iterations}")
            
            # --- 新增：上下文压缩检测 (80/60 准则) ---
            await self._check_and_compress_context()
            
            # 1. 调用 LLM
            llm_message, usage = await llm_backend.chat(self.messages, tools=openai_tools if openai_tools else None)
            
            # 累加 token
            if usage:
                total_usage["input"] += usage.prompt_tokens
                total_usage["output"] += usage.completion_tokens
            
            # ... (保持原有的助理消息添加逻辑)
            msg_to_add = {"role": "assistant", "content": llm_message.content or ""}
            if llm_message.tool_calls:
                # 转换 ToolCalls 对象为可序列化的列表
                msg_to_add["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in llm_message.tool_calls
                ]
            self.messages.append(msg_to_add)

            # 2. 解析逻辑
            response_text = llm_message.content or ""
            think, final, text_actions = self._parse_output(response_text)
            
            if think:
                logger.info(f"Agent Thinking: {think}")

            # 3. 汇总待执行工具 (原生优先)
            actions_to_run = []
            if llm_message.tool_calls:
                for tc in llm_message.tool_calls:
                    try:
                        actions_to_run.append({
                            "tool": tc.function.name,
                            "parameters": json.loads(tc.function.arguments),
                            "call_id": tc.id # 标记为原生调用
                        })
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse native tool arguments: {tc.function.arguments}")
            elif text_actions:
                actions_to_run = text_actions

            # --- 新增：触发中间状态回调 (方案 A: 自动生成) ---
            if actions_to_run and on_intermediate_status:
                for action in actions_to_run:
                    tool_name = action.get("tool")
                    params = action.get("parameters", {})
                    # 优先从参数中提取人类可读的意图
                    intent = params.get("description") or params.get("instruction")
                    
                    if final:
                        desc = final
                    elif intent:
                        desc = f"✅ 准备执行 `{tool_name}`：{intent}"
                    else:
                        desc = f"⚙️ 正在调用工具 `{tool_name}`..."
                    
                    logger.info(f"Triggering intermediate status update: {desc}")
                    await on_intermediate_status(desc)
                    break # 每轮迭代仅发送一条预告，避免卡片爆炸

            # 4. 执行工具
            if actions_to_run:
                for action in actions_to_run:
                    tool_name = action.get("tool")
                    params = action.get("parameters", {})
                    call_id = action.get("call_id")
                    
                    if not tool_name or not isinstance(tool_name, str):
                        logger.error(f"Invalid tool name in action: {tool_name}")
                        continue

                    logger.info(f"Executing {'Native' if call_id else 'Text'} Action: {tool_name}")
                    
                    tool = tool_registry.get_tool(tool_name)
                    if tool:
                        try:
                            obs = await tool.execute(**params)
                        except Exception as e:
                            obs = f"Error: 执行异常 - {str(e)}"
                    else:
                        obs = f"Error: 找不到工具 {tool_name}。"

                    # 根据调用方式注入 Observation
                    if call_id:
                        # 原生工具调用要求回复角色为 tool 并带上 tool_call_id
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": tool_name,
                            "content": obs
                        })
                    else:
                        self.messages.append({"role": "user", "content": f"Observation for {tool_name}: {obs}"})

                if final:
                    final_response = final
            
            # 5. 终止检查
            elif final:
                logger.info(f"Final Answer reached at iteration {i+1}")
                return final, total_usage
            
            else:
                logger.warning("No <final> tag or Action found.")
                self.messages.append({
                    "role": "user", 
                    "content": "系统提示：请继续。如果任务已完成，请使用 <final> 标签回复；如果还需操作，请继续调用工具。"
                })

        final_ans = final_response if final_response else f"已达到最大迭代次数 ({self.max_iterations})。"
        return final_ans, total_usage

    async def _check_and_compress_context(self):
        """检测并执行上下文压缩 (80/60 准则)"""
        # 估算总 Token (保守估算: 中文 2 字符/T, 英文 4 字符/T -> 综合取 3)
        total_chars = sum(len(str(m.get("content", ""))) for m in self.messages)
        # 考虑 tool_calls 的长度
        for m in self.messages:
            if "tool_calls" in m:
                total_chars += len(str(m["tool_calls"]))
        
        estimated_tokens = total_chars // 2  # 极其保守的估算
        
        threshold = config.llm.context_window * 0.8
        if estimated_tokens < threshold:
            return

        logger.warning(f"Context window pressure detected ({estimated_tokens} tokens). Starting 80/60 compression...")
        
        # 压缩逻辑：保留 System(0) 和 最近 5 条 (Tail)
        if len(self.messages) <= 10: 
            logger.info("Message count too small for compression. Skipping.")
            return

        system_msg = self.messages[0]
        # 提取短期对话历史 (最近 5 轮消息)
        preserved_msgs = self.messages[-5:]
        # 提取中间的可压缩区域 (包含之前的摘要和中间步骤)
        compressible_msgs = self.messages[1:-5]
        
        # 4. 调用 LLM 生成技术摘要 (上下文摘要)
        summary_prompt = [
            {"role": "system", "content": "你是一个上下文管理专家。请将以下历史对话过程总结为一段技术摘要。\n重点保留：已完成的任务目标、关键参数配置、重要的 Observation 数据。\n字数压缩率需达到 90% 以上。"},
            {"role": "user", "content": f"请压缩以下消息序列：\n{json.dumps(compressible_msgs, ensure_ascii=False)}"}
        ]
        
        try:
            summary_msg, _ = await llm_backend.chat(summary_prompt)
            new_summary_content = f"[Compacted Summary]\n{summary_msg.content}\n---"
            
            # 5. 重组消息序列
            # 格式: [System] + [Compacted Summary] + [Short-term Messages]
            self.messages = [
                system_msg,
                {"role": "user", "content": new_summary_content}
            ] + preserved_msgs
            
            logger.info("Context compression completed successfully.")
        except Exception as e:
            logger.error(f"Context compression failed: {e}")

    def _parse_output(self, text: str) -> Tuple[Optional[str], Optional[str], List[Dict]]:
        """解析 LLM 输出，提取 think, final 和 文本模式的 actions"""
        think = None
        final = None
        actions = []

        # 1. 提取 think 和 final 标签
        think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
        if think_match:
            think = think_match.group(1).strip()
            
        final_match = re.search(r"<final>(.*?)</final>", text, re.DOTALL)
        if final_match:
            final = final_match.group(1).strip()

        # 2. 提取 Action (支持多 Action 链)
        # 兼容旧格式及新格式中的 Action 块
        action_matches = re.finditer(r"Action:\s*(\{.*?\})", text, re.DOTALL)
        for match in action_matches:
            try:
                action_json = json.loads(match.group(1).strip())
                actions.append(action_json)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Action JSON: {match.group(1)}")
        
        return think, final, actions
