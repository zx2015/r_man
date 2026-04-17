from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from pydantic import BaseModel
from loguru import logger

class BaseTool(ABC):
    """所有 R-MAN 工具的基类"""
    name: str = ""
    description: str = ""
    parameters_schema: Type[BaseModel] = None

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """工具执行逻辑，必须返回字符串以便注入 Observation"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """返回符合 JSON Schema 规范的参数描述"""
        if self.parameters_schema:
            return self.parameters_schema.schema()
        return {}
