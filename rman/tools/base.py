import json
import functools
from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from pydantic import BaseModel
from loguru import logger

def audit_log(func):
    """审计日志装饰器"""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        result = await func(self, *args, **kwargs)
        
        # 尝试从参数中提取“意图”
        intent = kwargs.get("instruction") or kwargs.get("description") or "No intent declared"
        
        # 构造审计报文
        audit_data = {
            "tool": self.name,
            "intent": intent,
            "params": kwargs,
            "status": "Success" if not str(result).startswith("Error") else "Fail"
        }
        
        # 使用 bind(audit=True) 触发专门的日志 Sink
        logger.bind(audit=True).info(json.dumps(audit_data, ensure_ascii=False))
        return result
    return wrapper

from typing import Dict, Any, Type, Optional

class BaseTool(ABC):
    """所有 R-MAN 工具的基类"""
    name: str = ""
    description: str = ""
    parameters_schema: Optional[Type[BaseModel]] = None

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """工具执行逻辑，必须返回字符串以便注入 Observation"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """返回符合 JSON Schema 规范的参数描述"""
        if self.parameters_schema:
            return self.parameters_schema.schema()
        return {}
