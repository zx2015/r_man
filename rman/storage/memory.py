import sqlite3
import sqlite_vec
import os
import uuid
import json
from typing import List, Dict, Optional
from loguru import logger
from rman.common.config import config

class MemoryStore:
    """长期记忆存储层 (SQLite + sqlite-vec)"""
    def __init__(self):
        self.db_path = config.memory.db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return conn

    def _init_db(self):
        """初始化表结构"""
        conn = self._get_connection()
        try:
            # 1. 元数据表 (增加 expires_at)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    tag TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
            """)
            # ... (保持虚拟表初始化不变)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding float[1024]
                )
            """)
            conn.commit()
            self._cleanup_expired(conn)
            logger.info("Memory database initialized and cleaned up.")
        except Exception as e:
            logger.error(f"Failed to init memory DB: {e}")
        finally:
            conn.close()

    def _cleanup_expired(self, conn):
        """物理删除过期记忆"""
        try:
            # 获取要删除的 ID 列表
            expired = conn.execute("SELECT id FROM memory_entries WHERE expires_at < CURRENT_TIMESTAMP").fetchall()
            ids = [row[0] for row in expired]
            
            if not ids:
                return

            for mem_id in ids:
                # 同步删除元数据和向量数据
                conn.execute("DELETE FROM memory_vectors WHERE id = ?", (mem_id,))
                conn.execute("DELETE FROM memory_entries WHERE id = ?", (mem_id,))
            
            conn.commit()
            logger.info(f"Cleaned up {len(ids)} expired memory entries.")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    async def save(self, summary: str, embedding: List[float], tag: str = "general", ttl_days: int = 90):
        """存入摘要与向量，带过期时间"""
        mem_id = str(uuid.uuid4())
        conn = self._get_connection()
        try:
            # 写入元数据 (计算 expires_at)
            conn.execute(
                "INSERT INTO memory_entries (id, summary, tag, expires_at) VALUES (?, ?, ?, datetime('now', ?))",
                (mem_id, summary, tag, f"+{ttl_days} days")
            )
            # 写入向量
            import struct
            buf = struct.pack(f"{len(embedding)}f", *embedding)
            conn.execute(
                "INSERT INTO memory_vectors (id, embedding) VALUES (?, ?)",
                (mem_id, buf)
            )
            conn.commit()
            logger.info(f"Memory saved: {mem_id[:8]} (Expires in {ttl_days} days)")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
        finally:
            conn.close()

    async def search(self, query_embedding: List[float], limit: int = 3) -> List[Dict]:
        """语义搜索"""
        conn = self._get_connection()
        import struct
        buf = struct.pack(f"{len(query_embedding)}f", *query_embedding)
        
        try:
            # 执行相似度检索
            # 使用 vec_distance_cosine 或默认的 vec_distance_L2
            cursor = conn.execute("""
                SELECT 
                    e.summary, 
                    e.tag,
                    e.created_at,
                    v.distance
                FROM memory_vectors v
                JOIN memory_entries e ON v.id = e.id
                WHERE embedding MATCH ? AND k = ?
                ORDER BY distance ASC
            """, (buf, limit))
            
            results = []
            for row in cursor:
                results.append({
                    "summary": row[0],
                    "tag": row[1],
                    "time": row[2],
                    "score": 1.0 - row[3] # 简单转换为匹配分
                })
            return results
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []
        finally:
            conn.close()

# 单例
memory_store = MemoryStore()
