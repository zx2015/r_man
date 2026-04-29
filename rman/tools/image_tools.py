import os
from pydantic import BaseModel, Field
from typing import Optional
from rman.tools.base import BaseTool, audit_log
from rman.interaction.feishu import feishu_handler
from rman.common.config import config
from loguru import logger

class UploadImageParams(BaseModel):
    path: str = Field(..., description="要上传的本地图片文件路径。")

class UploadImageTool(BaseTool):
    name = "upload_image"
    description = "将本地图片上传到飞书服务器，并返回用于在卡片中展示的 image_key。上传后，你需要在回复中使用 {'tag': 'img', 'img_key': '...'} 来展示它。"
    parameters_schema = UploadImageParams

    @audit_log
    async def execute(self, path: str, **kwargs) -> str:
        if not os.path.exists(path):
            return f"Error: 找不到文件 {path}。"

        try:
            with open(path, "rb") as f:
                image_bytes = f.read()
            
            image_key = await feishu_handler.upload_image(image_bytes)
            
            if image_key:
                return f"Success: 图片已上传。image_key: {image_key}\n请在最终回复中使用以下 JSON 片段来展示图片：\n{{\"tag\": \"img\", \"img_key\": \"{image_key}\"}}"
            else:
                return "Error: 图片上传失败，请检查 API 权限。"
                
        except Exception as e:
            logger.error(f"Failed to upload image {path}: {e}")
            return f"Error: 上传异常 - {str(e)}"

class DownloadImageParams(BaseModel):
    image_key: str = Field(..., description="飞书图片的唯一标识符 (img_v3_...)。")
    file_name: Optional[str] = Field(None, description="保存的文件名（可选）。")

class DownloadImageTool(BaseTool):
    name = "download_image"
    description = "根据 image_key 从飞书服务器下载图片到本地。图片将保存在 workspace/downloads/ 目录下。"
    parameters_schema = DownloadImageParams

    @audit_log
    async def execute(self, image_key: str, file_name: Optional[str] = None, **kwargs) -> str:
        try:
            # 1. 确定保存目录
            workspace = os.path.abspath(config.agent.workspace_dir.replace("@", ""))
            download_dir = os.path.join(workspace, "downloads")
            os.makedirs(download_dir, exist_ok=True)

            # 2. 确定文件名
            if not file_name:
                import time
                file_name = f"img_{int(time.time())}.png"
            
            save_path = os.path.join(download_dir, file_name)

            # 3. 执行下载
            image_bytes = await feishu_handler.download_image(image_key)
            
            if image_bytes:
                with open(save_path, "wb") as f:
                    f.write(image_bytes)
                return f"Success: 图片已成功下载至 {save_path}"
            else:
                return "Error: 图片下载失败，请检查 image_key 是否正确或 API 权限。"
                
        except Exception as e:
            logger.error(f"Failed to download image {image_key}: {e}")
            return f"Error: 下载异常 - {str(e)}"
