import sqlite3
import os
import sys
from loguru import logger
from rman.common.config import config

def migrate_database():
    """手动将旧版 session_history 表迁移为 FTS5 虚拟表"""
    db_path = config.memory.db_path
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        sys.exit(1)
        
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='session_history'")
        row = cursor.fetchone()
        
        if not row:
            logger.info("No session_history table found. Nothing to migrate.")
            return
            
        sql = row[0]
        if "USING fts5" in sql.upper() or "USING FTS5" in sql.upper():
            logger.info("The session_history table is already an FTS5 virtual table. No migration needed.")
            return
            
        logger.warning("Detected legacy session_history table. Starting migration to FTS5...")
        
        try:
            # 清理可能残留的旧备份表
            conn.execute("DROP TABLE IF EXISTS session_history_old")
            
            # 重命名旧表用于数据备份与迁移
            conn.execute("ALTER TABLE session_history RENAME TO session_history_old")
            
            # 创建新的 FTS5 虚拟表
            conn.execute("""
                CREATE VIRTUAL TABLE session_history USING fts5(
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
            
            # 迁移数据
            logger.info("Transferring data to the new FTS5 table...")
            conn.execute("""
                INSERT INTO session_history (chat_id, role, content, name, tool_call_id, tool_calls, timestamp)
                SELECT chat_id, role, content, name, tool_call_id, tool_calls, timestamp FROM session_history_old
            """)
            
            # 清理旧表
            conn.execute("DROP TABLE session_history_old")
            
            logger.success("Migration to FTS5 completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            logger.info("Attempting to rollback...")
            # 简单回滚逻辑：如果 FTS5 表已创建则删除，并将 old 表改回原名
            try:
                conn.execute("DROP TABLE IF EXISTS session_history")
                conn.execute("ALTER TABLE session_history_old RENAME TO session_history")
                logger.success("Rollback successful. The original table was restored.")
            except Exception as rollback_err:
                logger.critical(f"Rollback failed: {rollback_err}. Manual intervention required.")
            sys.exit(1)

if __name__ == "__main__":
    # 配置日志输出到终端
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    migrate_database()
