import asyncio
import json
import os
import socket
import re
from typing import Optional, List, Dict, Any
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    P2ImMessageReceiveV1, 
    CreateMessageRequest, 
    CreateMessageRequestBody,
    ListChatRequest
)
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
        self.last_active_time = datetime.now()
        self.hostname = socket.gethostname()
        
        # 初始化 API Client
        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
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
            log_level=lark.LogLevel.DEBUG
        )
        # 挂载内部回调以追踪连接状态
        self.ws_client._on_connected = self._on_ws_connected  # type: ignore
        self.ws_client._on_disconnected = self._on_ws_disconnected  # type: ignore

    async def start(self):
        logger.info("Starting Feishu WebSocket client and task queue...")
        await task_queue.start()
        self.loop = asyncio.get_running_loop()
        
        # 改用显式的守护线程，防止阻塞进程退出
        import threading
        self._ws_thread = threading.Thread(target=self.ws_client.start, daemon=True)
        self._ws_thread.start()

    def _on_ws_connected(self):
        """连接成功回调"""
        logger.success("🚀 Feishu WebSocket Connected Successfully!")
        self.last_active_time = datetime.now()

    def _on_ws_disconnected(self):
        """连接断开回调"""
        logger.error("⚠️ Feishu WebSocket Disconnected! SDK will auto-reconnect...")

    async def check_connection(self) -> bool:
        """主动探活：调用极简 API 验证连通性"""
        try:
            from datetime import timedelta
            if datetime.now() - self.last_active_time < timedelta(minutes=1):
                return True
                
            req = ListChatRequest.builder().build()
            response = await self.loop.run_in_executor(None, self.client.im.v1.chat.list, req)
            
            if response.success():
                self.last_active_time = datetime.now()
                logger.info("Connection heartbeat: ACTIVE") 
                return True
            else:
                logger.warning(f"Active connection check: FAILED ({response.msg})")
        except Exception as e:
            logger.error(f"Active heartbeat error: {e}")
        return False

    def stop(self):
        """停止飞书交互服务相关资源"""
        logger.info("Closing Feishu Interaction service...")
        if self.loop and self.loop.is_running():
            self.loop.create_task(task_queue.stop())

    async def upload_image(self, image_bytes: bytes) -> Optional[str]:
        """上传图片到飞书并返回 image_key"""
        from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody
        import io
        try:
            img_io = io.BytesIO(image_bytes)
            # 关键：手动注入 name 属性，帮助 SDK 识别格式并封装 Multipart
            img_io.name = "upload.png" 
            
            request = CreateImageRequest.builder() \
                .request_body(CreateImageRequestBody.builder() \
                    .image_type("message") \
                    .image(img_io) \
                    .build()) \
                .build()
            
            response = await self.loop.run_in_executor(None, self.client.im.v1.image.create, request)
            if response.success():
                return response.data.image_key
            else:
                logger.error(f"Failed to upload image: {response.code}, {response.msg}")
                return None
        except Exception as e:
            logger.error(f"Exception during image upload: {e}")
            return None

    async def download_image(self, image_key: str) -> Optional[bytes]:
        """从飞书下载图片并返回二进制流"""
        from lark_oapi.api.im.v1 import GetImageRequest
        try:
            request = GetImageRequest.builder() \
                .image_key(image_key) \
                .build()
            
            response = await self.loop.run_in_executor(None, self.client.im.v1.image.get, request)
            if response.success():
                return response.file.read()
            else:
                logger.error(f"Failed to download image: {response.code}, {response.msg}")
                return None
        except Exception as e:
            logger.error(f"Exception during image download: {e}")
            return None

    def _on_message_received(self, data: P2ImMessageReceiveV1) -> None:
        self.last_active_time = datetime.now() # 更新活跃时间
        message = data.event.message
        sender_id = data.event.sender.sender_id.open_id
        chat_id = message.chat_id
        
        # 仅处理文本消息且来自授权用户
        if message.message_type != "text":
            return
        
        if self.allowed_user != "*" and sender_id != self.allowed_user:
            logger.warning(f"Message from unauthorized user: {sender_id}. Dropping.")
            return

        text_json = json.loads(message.content)
        text = text_json.get("text", "").strip()
        
        # 1. 发送“思考中”卡片
        self.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._send_card(
                chat_id, 
                "🤖 R-MAN 正在思考中...",
                f"正在处理用户消息: `{text}`",
                template="blue"
            ))
        )
        
        # 2. 提交任务
        coro = self._process_agent_task(message.message_id, text, chat_id)
        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(task_queue.add_task(coro)))

    async def _process_agent_task(self, message_id: str, text: str, chat_id: str):
        """调用真实的 AgentRunner 进行推理处理"""
        from rman.agent.runner import AgentRunner
        from rman.storage.session import session_store
        from rman.agent.summarizer import memory_summarizer

        logger.info(f"Task started for message {message_id}: {text}")
        
        try:
            # 传入 chat_id 以加载历史
            runner = AgentRunner(session_id=message_id, chat_id=chat_id)
            
            # 定义回调逻辑
            async def intermediate_callback(content: str):
                if config.agent.enable_intermediate_status:
                    # 采用更稳健的解析逻辑：首行为意图，余下全部为指令代码
                    parts = content.split('\n', 1)
                    if len(parts) == 2:
                        formatted_content = f"**{parts[0]}**\n```bash\n{parts[1].strip()}\n```"
                    else:
                        formatted_content = content
                    await self._send_card(chat_id, "⚙️ R-MAN 执行中...", formatted_content, template="turquoise")
            
            # 运行 Agent
            final_answer, usage = await runner.run(text, on_intermediate_status=intermediate_callback)
            
            # 发送结果卡片
            await self._send_card(chat_id, "🤖 R-MAN 执行报告", final_answer, template="green", usage=usage)
            logger.info(f"Task finished for message {message_id}")
            
        except Exception as e:
            logger.exception(f"Agent execution failed: {e}")
            await self._send_card(
                chat_id, 
                "❌ R-MAN 执行出错", 
                f"处理用户消息时发生了错误:\n```text\n{str(e)}\n```", 
                template="red"
            )

    async def _send_card(self, chat_id: str, title: str, content_md: str, template: str = "blue", usage: Optional[dict] = None):
        """发送智能增强的交互式卡片消息"""
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        from rman.common.card_utils import CardFormatter
        
        # 1. 自动 Header 颜色推断
        inferred_template = template
        if content_md.startswith("✅"): inferred_template = "green"
        elif content_md.startswith("❌"): inferred_template = "red"
        elif content_md.startswith("⚠️"): inferred_template = "orange"
        
        # 2. 调用增强版渲染 Pipeline (分离 Markdown / 表格 / 嵌入组件)
        final_elements = CardFormatter.format_with_components(content_md)
        
        # 3. 如果提供了 usage，增加分栏展示
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
                            {"tag": "div", "text": {"tag": "lark_md", "content": f"🏷 {usage.get('model', 'N/A')}"}}
                        ]
                    },
                    {
                        "tag": "column",
                        "width": "weighted", "weight": 1,
                        "elements": [
                            {"tag": "div", "text": {"tag": "lark_md", "content": f"📊 Tokens In: {usage.get('input', 0)} / Out: {usage.get('output', 0)}"}}
                        ]
                    }
                ]
            })

        # 5. 注脚
        curr_time = datetime.now().strftime('%H:%M:%S')
        final_elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"⏱ {curr_time} | R-MAN | {self.hostname}"}]
        })

        card_json = {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
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
            
        # 执行发送（带重试机制）
        for attempt in range(3):
            try:
                response = await self.loop.run_in_executor(None, self.client.im.v1.message.create, request)
                if response.success():
                    logger.debug(f"Card sent successfully (Attempt {attempt+1})")
                    return
                else:
                    logger.error(f"Failed to send card (Attempt {attempt+1}): {response.code}, {response.msg}")
            except Exception as e:
                logger.error(f"Network error sending card (Attempt {attempt+1}): {e}")
            
            if attempt < 2:
                await asyncio.sleep(2)

        logger.critical(f"Failed to send card after all attempts.")

# 单例
feishu_handler = FeishuInteraction()
