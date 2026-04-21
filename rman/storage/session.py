import sqlite3
import json
import os
from typing import List, Dict, Any
from loguru import logger

class SessionStore:
    """会话历史持久化存储 (SQLite FTS5 原生实现)"""
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            self._create_fts_table(conn)

    def _create_fts_table(self, conn: sqlite3.Connection):
        """创建 FTS5 虚拟表，配置多语言分词"""
        # 注意：FTS5 表不支持 PRIMARY KEY 声明，自动使用 rowid
        # 使用 unicode61 分词器以支持中文和多国语言
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS session_history USING fts5(
                chat_id, 
                role, 
                content, 
                name, 
                tool_call_id, 
                tool_calls, 
                timestamp,
                tokenize='unicode61'
            )
        """)

    def save_message(self, chat_id: str, role: str, content: str, 
                     name: str = None, tool_call_id: str = None, tool_calls: Any = None):
        """保存单条消息到 FTS5 表"""
        tool_calls_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO session_history (chat_id, role, content, name, tool_call_id, tool_calls) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, role, content, name, tool_call_id, tool_calls_json)
            )

    def load_history(self, chat_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """从 FTS5 表加载历史，使用 rowid 替代 id 进行排序"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # FTS5 默认拥有 rowid 字段
            cursor = conn.execute(
                "SELECT role, content, name, tool_call_id, tool_calls FROM (SELECT rowid, * FROM session_history WHERE chat_id = ? ORDER BY rowid DESC LIMIT ?) ORDER BY rowid ASC",
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

    def search_sessions(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """全局全文搜索入口：基于 FTS5 的跨会话检索"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 使用 FTS5 的 MATCH 语法进行关键词搜索，不再区分 chat_id
            sql = "SELECT rowid, chat_id, role, content, timestamp FROM session_history WHERE session_history MATCH ?"
            params = [query]
            
            sql += " ORDER BY rank LIMIT ?" # rank 是 FTS5 的内置相关性评分
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "rowid": row["rowid"],
                    "chat_id": row["chat_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"]
                })
            return results

# 单例
session_store = SessionStore()
