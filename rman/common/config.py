import os
from typing import Optional
from pydantic import BaseModel, Field
import yaml
from dotenv import load_dotenv

load_dotenv()

class AgentConfig(BaseModel):
    max_iterations: int = 20
    tool_timeout: int = 30
    process_session_max_ttl: int = 3600
    audit_log_path: str = "./logs/audit.log"
    workspace_dir: str = "workspace"
    enable_intermediate_status: bool = True

class LLMConfig(BaseModel):
    provider: str = "openai"
    base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = "gpt-4o"
    temperature: float = 0.2
    context_window: int = 128000
    max_tokens: int = 4096
    timeout: int = 60

class FeishuConfig(BaseModel):
    app_id: str = Field(default_factory=lambda: os.getenv("FEISHU_APP_ID", ""))
    app_secret: str = Field(default_factory=lambda: os.getenv("FEISHU_APP_SECRET", ""))
    receive_mode: str = "websocket"
    allowed_user_open_id: str = Field(default_factory=lambda: os.getenv("FEISHU_ALLOWED_USER", ""))
    agent_response_timeout: int = 120

class EmbeddingConfig(BaseModel):
    base_url: str = Field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", ""))
    api_key: str = Field(default_factory=lambda: os.getenv("EMBEDDING_API_KEY", ""))
    model: str = "BAAI/bge-m3"

class MemoryConfig(BaseModel):
    provider: str = "sqlite_vec"
    db_path: str = "./data/memory.db"
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    top_k: int = 3
    score_floor: float = 0.0

class Config(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

def load_config(config_path: str = "config/config.yaml") -> Config:
    if not os.path.exists(config_path):
        return Config()
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return Config.parse_obj(data)

# 全局单例配置
config = load_config()
