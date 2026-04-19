import sqlite3
import json
import os
from typing import List, Dict, Any
from rman.common.config import logger

class SessionStore:
    """会话历史持久化存储 (SQLite 实现) - 增强版"""
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 开启 WAL 模式提高并发性能
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    role TEXT,
                    content TEXT,
                    name TEXT,
                    tool_call_id TEXT,
                    tool_calls TEXT,  -- 存储结构化的 tool_calls JSON
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_chat ON session_history(chat_id)")

    def save_message(self, chat_id: str, role: str, content: str, 
                     name: str = None, tool_call_id: str = None, tool_calls: Any = None):
        """保存单条消息，支持结构化 tool_calls"""
        tool_calls_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO session_history (chat_id, role, content, name, tool_call_id, tool_calls) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, role, content, name, tool_call_id, tool_calls_json)
            )

    def load_history(self, chat_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按 ID 顺序加载历史，确保 ReAct 链条逻辑正确"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # 先取最近的 limit 条，再按 ID 正序排列
            cursor = conn.execute(
                "SELECT role, content, name, tool_call_id, tool_calls FROM (SELECT * FROM session_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
                (chat_id, limit)
            )
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                msg = {
                    "role": row["role"],
                    "content": row["content"]
                }
                if row["name"]: msg["name"] = row["name"]
                if row["tool_call_id"]: msg["tool_call_id"] = row["tool_call_id"]
                if row["tool_calls"]: 
                    try:
                        msg["tool_calls"] = json.loads(row["tool_calls"])
                    except:
                        pass
                history.append(msg)
            return history

# 单例
session_store = SessionStore()
