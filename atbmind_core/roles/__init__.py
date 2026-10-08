"""
ATBMind Roles Package
"""

from atbmind_core.roles.delegation import (
    DelegateTaskInput,
    DelegateTaskTool,
    ListRolesTool,
    compose_followup,
)
from atbmind_core.roles.loader import RoleLoader
from atbmind_core.roles.registry import RoleRegistry, RobotRoleRegistry, get_role_registry
from atbmind_core.roles.schema import RobotRole
from atbmind_core.roles.team import RobotTeam, COORDINATOR_ALLOWED_TOOLS

__all__ = [
    "RobotRole",
    "RoleLoader",
    "RoleRegistry",
    "RobotRoleRegistry",
    "get_role_registry",
    "RobotTeam",
    "DelegateTaskTool",
    "DelegateTaskInput",
    "ListRolesTool",
    "ListRolesInput",
    "compose_followup",
    "COORDINATOR_ALLOWED_TOOLS",
]
