import sqlite3
import json
import os
from typing import List, Dict, Any
from loguru import logger

class SessionStore:
    """会话历史持久化存储 (SQLite 实现) - 增强版"""
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            
            # 1. 定义最新的目标架构
            target_schema = {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "chat_id": "TEXT",
                "role": "TEXT",
                "content": "TEXT",
                "name": "TEXT",
                "tool_call_id": "TEXT",
                "tool_calls": "TEXT",
                "timestamp": "DATETIME DEFAULT CURRENT_TIMESTAMP"
            }
            
            # 2. 检查当前表状态
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_history'")
            if not cursor.fetchone():
                # 表不存在，直接创建
                cols_str = ", ".join([f"{k} {v}" for k, v in target_schema.items()])
                conn.execute(f"CREATE TABLE session_history ({cols_str})")
            else:
                # 表已存在，执行系统性迁移
                cursor = conn.execute("PRAGMA table_info(session_history)")
                current_columns = {info[1]: info for info in cursor.fetchall()}
                
                # 判定是否需要重建（缺少 id 或 字段不全）
                needs_rebuild = "id" not in current_columns
                needs_add_cols = [col for col in target_schema if col not in current_columns]
                
                if needs_rebuild:
                    logger.warning("Systematic migration: Rebuilding session_history table...")
                    # 重命名旧表
                    conn.execute("ALTER TABLE session_history RENAME TO session_history_old")
                    # 创建新表
                    cols_str = ", ".join([f"{k} {v}" for k, v in target_schema.items()])
                    conn.execute(f"CREATE TABLE session_history ({cols_str})")
                    
                    # 动态获取旧表中实际存在的、且新表也需要的列
                    cursor = conn.execute("PRAGMA table_info(session_history_old)")
                    old_cols = [info[1] for info in cursor.fetchall() if info[1] in target_schema]
                    
                    if old_cols:
                        old_cols_str = ", ".join(old_cols)
                        conn.execute(f"""
                            INSERT INTO session_history ({old_cols_str})
                            SELECT {old_cols_str} FROM session_history_old
                        """)
                    conn.execute("DROP TABLE session_history_old")
                    logger.info("Systematic migration completed via rebuild.")
                elif needs_add_cols:
                    for col in needs_add_cols:
                        logger.info(f"Adding missing column '{col}' to session_history.")
                        conn.execute(f"ALTER TABLE session_history ADD COLUMN {col} {target_schema[col]}")

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
