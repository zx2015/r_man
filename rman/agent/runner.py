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
        # 获取工具定义
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
