"""
ATBMind RobotTeam Architecture
Coordinates multi-agent specialist teams, roster awareness, session creation,
and enforces tool whitelist and Anti-Pass-Through guidelines for the Coordinator.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Set

from atbmind_core.harness.session import AgentSession
from atbmind_core.harness.tools.base import AgentTool
from atbmind_core.roles.delegation import DelegateTaskTool, ListRolesTool
from atbmind_core.roles.jobs import TeamJobTracker
from atbmind_core.roles.registry import RoleRegistry, get_role_registry
from atbmind_core.roles.schema import RobotRole
from atbmind_core.skills.registry import SkillRegistry, get_skill_registry

logger = logging.getLogger("atbmind.roles.team")

COORDINATOR_ALLOWED_TOOLS: frozenset[str] = frozenset({
    "delegate_task",
    "list_roles",
    "get_current_time",
    "current_time",
    "time",
    "memory_query",
    "memory_recall",
    "memory_store",
    "context_search",
})


class RobotTeam:
    """Manages a team of specialist RobotRoles coordinated by a designated leader."""

    def __init__(
        self,
        leader_role_id: str = "coordinator",
        role_registry: Optional[RoleRegistry] = None,
        skill_registry: Optional[SkillRegistry] = None,
        job_tracker: Optional[TeamJobTracker] = None,
    ) -> None:
        self.leader_role_id = leader_role_id
        self.role_registry = role_registry or get_role_registry()
        self.skill_registry = skill_registry or get_skill_registry()
        self.job_tracker = job_tracker or TeamJobTracker()

    def get_role(self, role_id: str) -> Optional[RobotRole]:
        return self.role_registry.get_role(role_id)

    def list_role_ids(self) -> List[str]:
        return self.role_registry.list_roles()

    def collect_role_tools(self, role_id: str) -> List[AgentTool]:
        role = self.get_role(role_id)
        if not role:
            return []
        all_skills = self.skill_registry.get_all_skills()
        return role.collect_tools(all_skills)

    def get_role_system_prompt(self, role_id: str) -> str:
        role = self.get_role(role_id)
        if not role:
            return ""
        all_skills = self.skill_registry.get_all_skills()
        return role.build_system_prompt(all_skills)

    def build_coordinator_system_prompt(self) -> str:
        leader = self.get_role(self.leader_role_id)
        base_prompt = leader.build_system_prompt(self.skill_registry.get_all_skills()) if leader else (
            "你是 ATBMind 团队主协调官。你负责统筹用户指令、意图理解，并在必要时调度团队专家角色协同完成任务。"
        )

        anti_pass_through_rules = (
            "\n\n【主持人守则与 Anti-Pass-Through 准则】\n"
            "1. 严禁自己干重活：主持人严禁直接承担长篇编码、生图、写文件或运行命令等重型执行工作，所有专业事务必须委派给专精专家；\n"
            "2. 禁止原样转发用户原话：严禁将用户的原始提问直接扔给专家，必须经过理解消化，改写为包含【任务目标】、【边界约束】、【交付格式】的专业结构化任务说明书；\n"
            "3. 闭环收口原则：专家完成任务后，主持人仅评估交付结果是否符合用户预期，并向用户提供不超过 3 句的精简总结，严禁机械式复述专家已输出的细节。"
        )

        base_prompt += anti_pass_through_rules

        # Build roster of available specialists (excluding the leader itself)
        roster_lines = []
        for rid in self.list_role_ids():
            if rid == self.leader_role_id:
                continue
            r = self.get_role(rid)
            if r:
                roster_lines.append(f"- `{r.role_id}`: {r.name} — {r.description}")

        if roster_lines:
            roster_text = (
                "\n\n【团队专家名录 (可通过 delegate_task 委派任务)】\n"
                + "\n".join(roster_lines)
                + "\n\n当用户提出需要专业视觉设计、修图、或深入领域计算的任务时，请调用 delegate_task 工具；"
                "若是日常交谈、需求澄清或任务汇总，请直接亲切回答用户。"
            )
            base_prompt += roster_text

        return base_prompt

    def create_coordinator_session(
        self,
        session_id: str,
        stream_client: Any,
        store: Optional[Any] = None,
        event_listener: Optional[Callable] = None,
    ) -> AgentSession:
        """Instantiates an AgentSession configured for the team leader with delegate_task, list_roles, and strict whitelist filtering."""
        delegate_tool = DelegateTaskTool(
            team=self,
            stream_client=stream_client,
            event_listener=event_listener,
            job_tracker=self.job_tracker,
        )
        list_roles_tool = ListRolesTool(team=self)

        tools: List[AgentTool] = [delegate_tool, list_roles_tool]
        
        # Collect tools configured directly on the leader, but filter strictly through whitelist
        leader_tools = self.collect_role_tools(self.leader_role_id)
        for t in leader_tools:
            if t.name in COORDINATOR_ALLOWED_TOOLS and t.name not in {"delegate_task", "list_roles"}:
                tools.append(t)
            else:
                logger.info(
                    "Filtered out non-whitelisted/heavy tool '%s' from Coordinator session",
                    t.name,
                )

        system_prompt = self.build_coordinator_system_prompt()

        return AgentSession(
            session_id=session_id,
            stream_client=stream_client,
            tools=tools,
            system_prompt=system_prompt,
            store=store,
        )

    def create_role_session(
        self,
        role_id: str,
        session_id: str,
        stream_client: Any,
        store: Optional[Any] = None,
    ) -> AgentSession:
        """Instantiates an AgentSession configured directly for a specialist role."""
        tools = self.collect_role_tools(role_id)
        system_prompt = self.get_role_system_prompt(role_id)
        return AgentSession(
            session_id=session_id,
            stream_client=stream_client,
            tools=tools,
            system_prompt=system_prompt,
            store=store,
        )
