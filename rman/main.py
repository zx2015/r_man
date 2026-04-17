import asyncio
import sys
import os
import signal
from loguru import logger

# 先加载配置
from rman.common.config import config

# 必须在所有业务模块导入前初始化日志
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level="DEBUG")
logger.add("logs/rman.log", rotation="10 MB", level="DEBUG", enqueue=True)

# 审计日志处理器
logger.add(
    config.agent.audit_log_path,
    rotation=f"{config.agent.audit_log_max_size} MB",
    retention=config.agent.audit_log_retention,
    filter=lambda record: "audit" in record.get("extra", {}),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | AUDIT | {message}",
    enqueue=True
)

from rman.interaction.feishu import feishu_handler
import rman.tools  # 触发工具注册

async def main():
    logger.info("Initializing r-man...")
    
    # 检查长期记忆环境
    try:
        import sqlite3
        import sqlite_vec
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        logger.info("Memory System [sqlite-vec] initialized successfully.")
    except Exception as e:
        logger.warning(f"Memory System [sqlite-vec] unavailable: {e}")
        logger.warning("To enable memory, run: pip install sqlite-vec")
    
    if not config.feishu.app_id or not config.feishu.app_secret:
        logger.error("Feishu App ID or App Secret is missing in config/config.yaml.")
        sys.exit(1)
        
    # 使用 Event 替代 sleep 循环
    stop_event = asyncio.Event()

    # --- 新增：独立的后台维护任务 ---
    async def maintenance_task():
        """每 24 小时执行一次内存维护"""
        logger.info("Background maintenance task started.")
        while not stop_event.is_set():
            try:
                # 每 24 小时检查一次
                await asyncio.sleep(3600 * 24)
                if not stop_event.is_set():
                    from rman.storage.memory import memory_store
                    import sqlite3
                    logger.info("Executing scheduled memory cleanup...")
                    conn = sqlite3.connect(config.memory.db_path)
                    memory_store._cleanup_expired(conn)
                    conn.close()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance task error: {e}")
                await asyncio.sleep(60) # 报错后等一分钟重试

    m_task = asyncio.create_task(maintenance_task())
    # ----------------------------

    # 注册信号处理器 (处理 Ctrl+C)
    def handle_signal():
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        await feishu_handler.start()
        logger.info("r-man is up and running. Press Ctrl+C to stop.")
        
        # 阻塞直到收到停止信号
        await stop_event.wait()
                
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        logger.info("Shutting down components...")
        feishu_handler.stop()
        logger.info("r-man has been stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
