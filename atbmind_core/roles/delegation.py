"""
ATBMind Subagent Delegation Tool
Allows Coordinator to spawn isolated sub-harness loops for specialist RobotRoles.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field

from atbmind_core.harness.loop import AgentContext, AgentLoopConfig, agent_loop
from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.harness.types import (
    AgentEvent,
    AgentEventType,
    AgentMessage,
    Role,
)

logger = logging.getLogger("atbmind.roles.delegation")


class DelegateTaskInput(BaseModel):
    role_id: str = Field(..., description="目标专家角色的 ID，例如 'draw_expert'")
    task_description: str = Field(..., description="委派给专家的具体任务、背景信息及交付要求")


class DelegateTaskTool(AgentTool):
    """Meta-tool that dispatches specialized tasks to team member RobotRoles."""

    name = "delegate_task"
    description = (
        "将特定领域的专业任务委派给团队内的专家角色（例如 'draw_expert'）独立执行，"
        "并获取该专家生成的回复、图片路径或执行成果。"
    )
    parameters_schema = DelegateTaskInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(
        self,
        team: Any,
        stream_client: Any,
        event_listener: Optional[Callable[[AgentEvent], None]] = None,
    ) -> None:
        self.team = team
        self.stream_client = stream_client
        self.event_listener = event_listener

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        role_id = args.get("role_id", "").strip()
        task_description = args.get("task_description", "").strip()

        if not role_id:
            return ToolResult(content="错误: 必须指定目标专家角色 role_id", is_error=True)

        role = self.team.get_role(role_id)
        if not role:
            available = self.team.list_role_ids()
            return ToolResult(
                content=f"错误: 不存在角色 '{role_id}'，团队现有可用角色: {available}",
                is_error=True,
            )

        # 1. Assemble specialist system prompt and tools
        sub_tools = self.team.collect_role_tools(role_id)
        sub_system_prompt = self.team.get_role_system_prompt(role_id)

        # 2. Setup isolated subagent context
        sub_context = AgentContext(
            tools=sub_tools,
            system_prompt=sub_system_prompt,
            metadata={"origin_role": role_id},
        )
        sub_config = AgentLoopConfig(
            stream_client=self.stream_client,
            max_turns=10,
        )

        initial_prompt = AgentMessage(
            role=Role.USER,
            content=task_description,
        )

        # 3. Execute subagent loop
        final_reply = ""
        result_metadata: Dict[str, Any] = {"subagent_role": role_id}

        try:
            async for event in agent_loop([initial_prompt], sub_context, sub_config):
                # Tag event with subagent origin and bubble to listener
                if isinstance(event.payload, dict):
                    event.payload["origin_role"] = role_id

                if self.event_listener:
                    try:
                        self.event_listener(event)
                    except Exception as el_err:
                        logger.debug("Error in delegate event listener: %s", el_err)

                if event.type == AgentEventType.TOOL_CALL_END:
                    meta = event.payload.get("metadata")
                    if isinstance(meta, dict):
                        result_metadata.update(meta)

                elif event.type == AgentEventType.MESSAGE_END:
                    msg = event.payload.get("message")
                    if isinstance(msg, AgentMessage) and msg.role == Role.ASSISTANT and msg.content:
                        final_reply = msg.content

            if not final_reply:
                final_reply = f"专家 {role.name} 已完成任务。"

            return ToolResult(
                content=final_reply,
                is_error=False,
                metadata=result_metadata,
            )

        except Exception as exc:
            logger.exception("Subagent execution failure for role %s: %s", role_id, exc)
            return ToolResult(
                content=f"委派给角色 '{role_id}' 时执行异常: {exc}",
                is_error=True,
                metadata={"subagent_role": role_id, "error": str(exc)},
            )
