import json
from unittest.mock import MagicMock, patch
import pytest
from rman.interaction.feishu import FeishuInteraction

@pytest.fixture
def mock_config():
    with patch("rman.interaction.feishu.config") as m:
        m.feishu.app_id = "test_app_id"
        m.feishu.app_secret = "test_app_secret"
        m.feishu.allowed_user_open_id = "authorized_user_123"
        yield m

@pytest.fixture
def feishu_handler(mock_config):
    # 模拟 lark.Client 和 lark_oapi.ws.Client 防止初始化时尝试网络连接
    with patch("lark_oapi.Client.builder"), \
         patch("lark_oapi.ws.Client"), \
         patch("lark_oapi.EventDispatcherHandler.builder"):
        handler = FeishuInteraction()
        yield handler

def test_on_message_received_authorized(feishu_handler):
    # 模拟接收到的飞书消息数据
    mock_data = MagicMock()
    mock_data.event.sender.sender_id.open_id = "authorized_user_123"
    mock_data.event.message.message_id = "msg_001"
    mock_data.event.message.content = json.dumps({"text": "hello r-man"})
    
    with patch.object(feishu_handler, "_reply_status") as mock_reply, \
         patch("rman.interaction.feishu.asyncio.run_coroutine_threadsafe") as mock_submit:
        
        feishu_handler._on_message_received(mock_data)
        
        # 验证是否发送了“处理中”回复
        mock_reply.assert_called_once_with("msg_001", "🤖 R-MAN 正在思考中，请稍候...")
        # 验证是否提交了异步任务
        assert mock_submit.called

def test_on_message_received_unauthorized(feishu_handler):
    # 模拟来自非授权用户的消息
    mock_data = MagicMock()
    mock_data.event.sender.sender_id.open_id = "hacker_456"
    mock_data.event.message.content = json.dumps({"text": "delete all"})
    
    with patch.object(feishu_handler, "_reply_status") as mock_reply, \
         patch("rman.interaction.feishu.asyncio.run_coroutine_threadsafe") as mock_submit:
        
        feishu_handler._on_message_received(mock_data)
        
        # 验证未发送回复且未提交任务
        assert not mock_reply.called
        assert not mock_submit.called
