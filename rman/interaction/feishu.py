import asyncio
import json
from typing import Optional
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1, CreateMessageRequest, CreateMessageRequestBody
from rman.common.config import config
from rman.interaction.queue import task_queue
from loguru import logger
from datetime import datetime

class FeishuInteraction:
    def __init__(self):
        self.app_id = config.feishu.app_id
        self.app_secret = config.feishu.app_secret
        self.allowed_user = config.feishu.allowed_user_open_id
        self.loop = None
        
        # 初始化 API Client
        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()
            
        # 注册事件分发器
        self.event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(self._on_message_received) \
            .build()
            
        # 初始化 WebSocket Client
        from lark_oapi.ws import Client as WSClient
        self.ws_client = WSClient(
            self.app_id, 
            self.app_secret, 
            event_handler=self.event_handler,
            log_level=lark.LogLevel.INFO
        )

    async def start(self):
        logger.info("Starting Feishu WebSocket client and task queue...")
        await task_queue.start()
        self.loop = asyncio.get_running_loop()
        
        # 改用显式的守护线程，防止阻塞进程退出
        import threading
        self._ws_thread = threading.Thread(target=self.ws_client.start, daemon=True)
        self._ws_thread.start()

    def stop(self):
        """停止飞书交互服务相关资源"""
        # WSClient 在守护线程运行且无 stop 方法，无需手动调用
        logger.info("Closing Feishu Interaction service...")

        # 任务队列的停止是异步的
        if self.loop and self.loop.is_running():
            self.loop.create_task(task_queue.stop())


    def _on_message_received(self, data: P2ImMessageReceiveV1) -> None:
        message = data.event.message
        sender_id = data.event.sender.sender_id.open_id
        chat_id = message.chat_id
        
        # 鉴权
        is_allowed = (not self.allowed_user or self.allowed_user == "*" or sender_id == self.allowed_user)
        if not is_allowed:
            logger.warning(f"Unauthorized message from user: {sender_id}. Ignored.")
            return
            
        content_raw = json.loads(message.content)
        text = content_raw.get("text", "").strip()
        logger.info(f"Received message from [UserID: {sender_id}, ChatID: {chat_id}]: {text}")
        
        # 1. 发送“思考中”卡片
        self.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._send_card(
                chat_id, 
                "🤖 R-MAN 正在思考中...", 
                f"正在处理指令: `{text}`",
                template="blue"
            ))
        )
        
        # 2. 提交任务
        coro = self._process_agent_task(message.message_id, text, chat_id)
        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(task_queue.add_task(coro)))

    async def _process_agent_task(self, message_id: str, text: str, chat_id: str):
        """调用真实的 AgentRunner 进行推理处理"""
        from rman.agent.runner import AgentRunner
        logger.info(f"Task started for message {message_id}: {text}")

        try:
            runner = AgentRunner(session_id=message_id)

            # 定义回调逻辑
            async def intermediate_callback(content: str):
                if config.agent.enable_intermediate_status:
                    await self._send_card(
                        chat_id, 
                        "⚙️ R-MAN 执行中...", 
                        content, 
                        template="turquoise" # 使用青色区分中间过程
                    )

            # 运行 Agent 并传入回调
            final_answer, usage = await runner.run(text, on_intermediate_status=intermediate_callback)

            # 发送结果卡片
            await self._send_card(
                chat_id, 
                "🤖 R-MAN 执行报告", 
                final_answer, 
                template="green",
                usage=usage
            )
            logger.info(f"Task finished for message {message_id}")
            
        except Exception as e:
            logger.exception(f"Agent execution failed: {e}")
            await self._send_card(
                chat_id, 
                "❌ R-MAN 执行出错", 
                f"处理指令时发生了错误:\n```text\n{str(e)}\n```", 
                template="red"
            )

    async def _send_card(self, chat_id: str, title: str, content_md: str, template: str = "blue", usage: Optional[dict] = None):
        """发送智能增强的交互式卡片消息"""
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        from rman.common.card_utils import CardFormatter
        
        # 1. 自动 Header 颜色推断
        # 映射规则：✅->green, ❌->red, ⚠️->orange, 其他/ℹ️->blue
        inferred_template = template
        if content_md.startswith("✅"): inferred_template = "green"
        elif content_md.startswith("❌"): inferred_template = "red"
        elif content_md.startswith("⚠️"): inferred_template = "orange"
        
        # 2. 调用增强版渲染 Pipeline
        # 该 Pipeline 会自动转换表格、注入间距、处理 Emoji
        elements = CardFormatter.format_with_components(content_md)
        
        # 3. 注入 手动嵌入 JSON 组件的识别 (降级兼容)
        # 此逻辑用于处理 Prompt 中推荐的极简组件，如 {"tag": "tag"}
        final_elements = []
        import re
        for elem in elements:
            if elem.get("tag") == "div" and "lark_md" in elem.get("text", {}):
                text = elem["text"]["lark_md"]["content"]
                # 识别内联 JSON 组件
                comp_pattern = r'(\{[\s\n]*"tag"[\s\n]*:[\s\n]*"(table|column_set|div|tag)"[\s\n]*,.*?\})'
                matches = list(re.finditer(comp_pattern, text, re.DOTALL))
                if matches:
                    last_pos = 0
                    for match in matches:
                        if text[last_pos:match.start()].strip():
                            final_elements.append({"tag": "div", "text": {"tag": "lark_md", "content": text[last_pos:match.start()].strip()}})
                        try:
                            final_elements.append(json.loads(match.group(1)))
                        except: pass
                        last_pos = match.end()
                    if text[last_pos:].strip():
                        final_elements.append({"tag": "div", "text": {"tag": "lark_md", "content": text[last_pos:].strip()}})
                else:
                    final_elements.append(elem)
            else:
                final_elements.append(elem)

        # 4. 如果提供了 usage，增加分栏展示
        if usage:
            final_elements.append({"tag": "hr"})
            final_elements.append({
                "tag": "column_set",
                "flex_mode": "stretch",
                "columns": [
                    {
                        "tag": "column",
                        "width": "weighted", "weight": 1,
                        "elements": [
                            {"tag": "div", "text": {"tag": "lark_md", "content": f"🏷 **Model**\n{usage.get('model', 'N/A')}"}}
                        ]
                    },
                    {
                        "tag": "column",
                        "width": "weighted", "weight": 1,
                        "elements": [
                            {"tag": "div", "text": {"tag": "lark_md", "content": f"📊 **Tokens**\nIn: {usage.get('input', 0)} / Out: {usage.get('output', 0)}"}}
                        ]
                    }
                ]
            })

        # 5. 注脚
        curr_time = datetime.now().strftime('%H:%M:%S')
        final_elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"⏱ {curr_time} | R-MAN Intelligence Service"}]
        })

        card_json = {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": inferred_template
            },
            "elements": final_elements
        }

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder() \
                .receive_id(chat_id) \
                .msg_type("interactive") \
                .content(json.dumps(card_json)) \
                .build()) \
            .build()
            
        response = await self.loop.run_in_executor(None, self.client.im.v1.message.create, request)
        if not response.success():
            logger.error(f"Failed to send card: {response.code}, {response.msg}")

# 单例
feishu_handler = FeishuInteraction()
