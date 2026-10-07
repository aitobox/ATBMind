"""
ATBMind Skill Registry
Manages discovery, registration, and retrieval of active Skills.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from atbmind_core.skills.loader import SkillLoader
from atbmind_core.skills.schema import Skill

logger = logging.getLogger("atbmind.skills.registry")


class SkillRegistry:
    """Central repository for available skills."""

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}

    def register_skill(self, skill: Skill) -> None:
        name = skill.metadata.name
        self._skills[name] = skill
        logger.info("Registered skill '%s' from %s", name, skill.skill_dir)

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        return sorted(list(self._skills.keys()))

    def get_all_skills(self) -> Dict[str, Skill]:
        return dict(self._skills)

    def clear(self) -> None:
        self._skills.clear()

    def scan_directory(self, dir_path: Path | str) -> int:
        root = Path(dir_path).resolve()
        if not root.is_dir():
            return 0

        count = 0
        for item in root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Candidate skill directory
                if (item / "SKILL.md").exists() or (item / "tools.py").exists():
                    try:
                        skill = SkillLoader.load_from_dir(item)
                        self.register_skill(skill)
                        count += 1
                    except Exception as e:
                        logger.warning("Failed loading skill from %s: %s", item, e)
        return count


_global_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = SkillRegistry()
    return _global_skill_registry
