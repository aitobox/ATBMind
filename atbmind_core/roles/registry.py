"""
ATBMind Role Registry
Discovers, registers, and manages RobotRole expert definitions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from atbmind_core.roles.loader import RoleLoader
from atbmind_core.roles.schema import RobotRole
from atbmind_core.skills.registry import SkillRegistry, get_skill_registry

logger = logging.getLogger("atbmind.roles.registry")


class RoleRegistry:
    """Registry for expert agent roles."""

    def __init__(self, skill_registry: Optional[SkillRegistry] = None) -> None:
        self._roles: Dict[str, RobotRole] = {}
        self.skill_registry = skill_registry or get_skill_registry()

    def register_role(self, role: RobotRole) -> None:
        self._roles[role.role_id] = role
        logger.info("Registered RobotRole '%s' (%s)", role.role_id, role.name)

    def get_role(self, role_id: str) -> Optional[RobotRole]:
        return self._roles.get(role_id)

    def list_roles() -> List[str]:
        return sorted(list(self._roles.keys()))

    def list_roles(self) -> List[str]:
        return sorted(list(self._roles.keys()))

    def get_all_roles(self) -> Dict[str, RobotRole]:
        return dict(self._roles)

    def clear(self) -> None:
        self._roles.clear()

    def scan_directory(self, dir_path: Path | str) -> int:
        root = Path(dir_path).resolve()
        if not root.is_dir():
            return 0

        count = 0
        for item in root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                if (item / "role.yaml").exists() or (item / "role.yml").exists():
                    try:
                        role = RoleLoader.load_from_dir(item)
                        self.register_role(role)
                        count += 1
                    except Exception as e:
                        logger.warning("Failed loading role from %s: %s", item, e)
        return count


_global_role_registry: Optional[RoleRegistry] = None


def get_role_registry() -> RoleRegistry:
    global _global_role_registry
    if _global_role_registry is None:
        _global_role_registry = RoleRegistry()
    return _global_role_registry
