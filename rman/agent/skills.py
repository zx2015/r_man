import os
import re
import yaml
from typing import List, Dict, Optional
from pydantic import BaseModel
from loguru import logger

class SkillDefinition(BaseModel):
    """技能定义对象"""
    name: str
    description: str
    location: str
    body: str

class SkillManager:
    """技能管理器：负责扫描、解析与内存快照维护"""
    def __init__(self):
        self.skills_snapshot: List[SkillDefinition] = []
        # 寻找 rman/skills 目录
        self.skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills"))
        # 正则逻辑：匹配 Frontmatter (YAML) 和 Body
        self.parse_pattern = re.compile(r'^---([\s\S]*?)---(?:\r?\n([\s\S]*))?', re.MULTILINE)

    def scan_skills(self):
        """服务初始化时触发的扫描逻辑"""
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir, exist_ok=True)
            logger.info(f"Created skills directory at {self.skills_dir}")
            return

        new_snapshot = []
        logger.info(f"Scanning directory {self.skills_dir} for skills...")

        # 遍历子目录寻找 SKILL.md
        for root, dirs, files in os.walk(self.skills_dir):
            if "SKILL.md" in files:
                file_path = os.path.join(root, "SKILL.md")
                skill = self._parse_skill_file(file_path)
                if skill:
                    new_snapshot.append(skill)
                    logger.success(f"Loaded skill: {skill.name}")

        self.skills_snapshot = new_snapshot
        logger.info(f"Skill scanning completed. {len(self.skills_snapshot)} skills loaded.")

    def _parse_skill_file(self, file_path: str) -> Optional[SkillDefinition]:
        """解析单个 SKILL.md 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            match = self.parse_pattern.match(content)
            if not match:
                logger.warning(f"Invalid SKILL.md format (missing frontmatter) at {file_path}")
                return None

            # 1. 解析 YAML 元数据
            try:
                frontmatter = yaml.safe_load(match.group(1))
                if not frontmatter or 'name' not in frontmatter:
                    return None
            except Exception as e:
                logger.error(f"Failed to parse YAML in {file_path}: {e}")
                return None

            # 2. 清洗名称并组装对象
            sanitized_name = re.sub(r'[^a-zA-Z0-9\-_]', '-', frontmatter['name']).lower()
            
            return SkillDefinition(
                name=sanitized_name,
                description=frontmatter.get('description', ''),
                location=os.path.abspath(file_path),
                body=(match.group(2) or "").strip()
            )

        except Exception as e:
            logger.error(f"Error reading skill file {file_path}: {e}")
            return None

    def get_snapshot(self) -> List[SkillDefinition]:
        """获取当前内存中的技能列表"""
        return self.skills_snapshot

# 全局单例
skill_manager = SkillManager()
