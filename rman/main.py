import asyncio
import sys
import os
from loguru import logger

# 必须在所有业务模块导入前初始化日志
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level="DEBUG")
logger.add("logs/rman.log", rotation="10 MB", level="DEBUG", enqueue=True)

from rman.interaction.feishu import feishu_handler
from rman.common.config import config
import rman.tools  # 触发工具注册

async def main():
    logger.info("Initializing r-man...")
    
    if not config.feishu.app_id or not config.feishu.app_secret:
        logger.error("Feishu App ID or App Secret is missing in config/config.yaml.")
        sys.exit(1)
        
    stop_event = asyncio.Event()

    try:
        await feishu_handler.start()
        logger.info("r-man is up and running. Press Ctrl+C to stop.")
        
        # 持续运行直到 stop_event 被触发
        await stop_event.wait()
                
    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down...")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        feishu_handler.stop()
        # 给异步组件（如任务队列）一点清理时间
        await asyncio.sleep(0.5)
        logger.info("r-man has been stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 捕获 asyncio.run 抛出的中断，保持静默
        pass
