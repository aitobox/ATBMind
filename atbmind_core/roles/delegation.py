"""
ATBMind Subagent Delegation Tool
Allows Coordinator to spawn isolated sub-harness loops for specialist RobotRoles,
queries available roles, and synthesizes followup completions.
"""

from __future__ import annotations

import asyncio
import inspect
import json
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
from atbmind_core.roles.jobs import TeamJobStatus, TeamJobTracker

logger = logging.getLogger("atbmind.roles.delegation")


def compose_followup(
    role_id: str,
    role_name: str,
    task_description: str,
    subagent_result: str,
    max_sentences: int = 3,
) -> str:
    """
    Composes a structured followup wake-up message for the Coordinator upon specialist completion.
    Enforces the closing & synthesis constraint:
    - Assesses whether the original task has been satisfied
    - Strictly limits closing summary to at most max_sentences (default 3)
    - Prohibits echoing or repeating the specialist's verbatim output
    """
    return (
        f"【专家执行闭环通知】\n"
        f"专家角色：`{role_name}` (ID: `{role_id}`)\n"
        f"委派任务书：{task_description}\n"
        f"专家交付成果：\n{subagent_result}\n\n"
        f"【主持人收口守则】\n"
        f"1. 请根据上述专家成果，向用户进行简要收尾回复；\n"
        f"2. 总结内容必须精简，严格限制在 {max_sentences} 句以内；\n"
        f"3. 严禁复述或原样重复专家上墙的具体详细内容；\n"
        f"4. 明确指出任务是否已成功闭环。"
    )


class DelegateTaskInput(BaseModel):
    role_id: str = Field(..., description="目标专家角色的 ID，例如 'draw_expert'")
    task_description: str = Field(..., description="委派给专家的具体任务、背景信息及交付要求")
    async_mode: bool = Field(False, description="是否以异步非阻塞模式派工（为 True 时立即返回派工回执，子任务在后台并发运行）")


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
        job_tracker: Optional[TeamJobTracker] = None,
        completion_callback: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.team = team
        self.stream_client = stream_client
        self.event_listener = event_listener
        self.job_tracker = job_tracker or getattr(team, "job_tracker", None) or TeamJobTracker()
        self.completion_callback = completion_callback

    async def _run_subagent(
        self,
        job_id: str,
        role_id: str,
        role: Any,
        task_description: str,
    ) -> Dict[str, Any]:
        """Runs the subagent execution loop, updates job tracker, and invokes callbacks."""
        try:
            self.job_tracker.start_job(job_id)
        except Exception as e:
            logger.debug("Failed starting job %s in tracker: %s", job_id, e)

        # 1. Assemble specialist system prompt and tools
        sub_tools = self.team.collect_role_tools(role_id)
        sub_system_prompt = self.team.get_role_system_prompt(role_id)

        # 2. Setup isolated subagent context
        sub_context = AgentContext(
            tools=sub_tools,
            system_prompt=sub_system_prompt,
            metadata={"origin_role": role_id, "speaker_role": role_id, "job_id": job_id},
        )
        sub_config = AgentLoopConfig(
            stream_client=self.stream_client,
            max_turns=10,
        )

        initial_prompt = AgentMessage(
            role=Role.USER,
            content=task_description,
        )

        final_reply = ""
        last_error: Optional[str] = None
        result_metadata: Dict[str, Any] = {
            "subagent_role": role_id,
            "speaker_role": role_id,
            "job_id": job_id,
        }

        try:
            async for event in agent_loop([initial_prompt], sub_context, sub_config):
                # Tag event with subagent identity and speaker_role
                if isinstance(event.payload, dict):
                    event.payload["origin_role"] = role_id
                    event.payload["speaker_role"] = role_id
                    event.payload["job_id"] = job_id

                if self.event_listener:
                    try:
                        self.event_listener(event)
                    except Exception as el_err:
                        logger.debug("Error in delegate event listener: %s", el_err)

                if event.type == AgentEventType.TOOL_CALL_END:
                    meta = event.payload.get("metadata")
                    if isinstance(meta, dict):
                        result_metadata.update(meta)

                elif event.type == AgentEventType.TURN_END:
                    if event.payload.get("error"):
                        last_error = str(event.payload.get("error"))

                elif event.type == AgentEventType.MESSAGE_END:
                    msg = event.payload.get("message")
                    if isinstance(msg, AgentMessage) and msg.role == Role.ASSISTANT and msg.content:
                        final_reply = msg.content

            if last_error:
                self.job_tracker.fail_job(job_id, error=last_error)
                followup_content = compose_followup(
                    role_id=role_id,
                    role_name=role.name,
                    task_description=task_description,
                    subagent_result=f"【执行异常】{last_error}",
                )
                result_metadata["error"] = last_error
                if self.completion_callback:
                    try:
                        cb_res = self.completion_callback(
                            role_id, task_description, f"【执行异常】{last_error}", followup_content
                        )
                        if inspect.isawaitable(cb_res):
                            await cb_res
                    except Exception as cb_err:
                        logger.exception("Error in delegate completion_callback: %s", cb_err)

                return {
                    "followup": followup_content,
                    "is_error": True,
                    "metadata": result_metadata,
                }

            if not final_reply:
                final_reply = f"专家 {role.name} 已完成任务。"

            self.job_tracker.complete_job(job_id, result=final_reply)

            followup_content = compose_followup(
                role_id=role_id,
                role_name=role.name,
                task_description=task_description,
                subagent_result=final_reply,
            )
            result_metadata["followup_composed"] = True
            result_metadata["subagent_reply"] = final_reply

            if self.completion_callback:
                try:
                    cb_res = self.completion_callback(role_id, task_description, final_reply, followup_content)
                    if inspect.isawaitable(cb_res):
                        await cb_res
                except Exception as cb_err:
                    logger.exception("Error in delegate completion_callback: %s", cb_err)

            return {
                "followup": followup_content,
                "is_error": False,
                "metadata": result_metadata,
            }

        except Exception as exc:
            logger.exception("Subagent execution failure for role %s: %s", role_id, exc)
            self.job_tracker.fail_job(job_id, error=str(exc))
            return {
                "followup": f"委派给角色 '{role_id}' 时执行异常: {exc}",
                "is_error": True,
                "metadata": {"subagent_role": role_id, "error": str(exc), "job_id": job_id},
            }


    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        role_id = args.get("role_id", "").strip()
        task_description = args.get("task_description", "").strip()
        async_mode = bool(args.get("async_mode", False))

        if not role_id:
            return ToolResult(content="错误: 必须指定目标专家角色 role_id", is_error=True)

        role = self.team.get_role(role_id)
        if not role:
            available = self.team.list_role_ids()
            return ToolResult(
                content=f"错误: 不存在角色 '{role_id}'，团队现有可用角色: {available}",
                is_error=True,
            )

        job = self.job_tracker.submit_job(
            role_id=role_id,
            task_description=task_description,
        )

        if async_mode:
            # Launch background task and return receipt immediately
            asyncio.create_task(
                self._run_subagent(
                    job_id=job.job_id,
                    role_id=role_id,
                    role=role,
                    task_description=task_description,
                )
            )
            receipt = (
                f"已成功异步派发任务给专家【{role.name}】(ID: `{role_id}`)，作业编号: `{job.job_id}`。"
                f"该专家正在后台并发执行，执行过程将实时通过流式通知上报。"
            )
            return ToolResult(
                content=receipt,
                is_error=False,
                metadata={
                    "job_id": job.job_id,
                    "role_id": role_id,
                    "subagent_role": role_id,
                    "async": True,
                },
            )

        # Synchronous blocking mode (backward-compatible)
        sub_res = await self._run_subagent(
            job_id=job.job_id,
            role_id=role_id,
            role=role,
            task_description=task_description,
        )
        return ToolResult(
            content=sub_res["followup"],
            is_error=sub_res["is_error"],
            metadata=sub_res["metadata"],
        )



class ListRolesInput(BaseModel):
    """Input parameters for listing available team roles (empty)."""
    pass


class ListRolesTool(AgentTool):
    """Meta-tool that queries and returns the team's available specialist RobotRoles."""

    name = "list_roles"
    description = "列出团队当前可用的所有专家角色及其专长描述，供任务委派参考。"
    parameters_schema = ListRolesInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, team: Any) -> None:
        self.team = team

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        roles_data = []
        leader_id = getattr(self.team, "leader_role_id", "coordinator")
        for rid in self.team.list_role_ids():
            if rid == leader_id:
                continue
            r = self.team.get_role(rid)
            if r:
                roles_data.append({
                    "role_id": r.role_id,
                    "name": r.name,
                    "description": r.description,
                    "personality": getattr(r, "personality", ""),
                    "skills": getattr(r, "skills", []),
                })
        return ToolResult(
            content=json.dumps(roles_data, ensure_ascii=False, indent=2),
            is_error=False,
            metadata={"roles_count": len(roles_data)},
        )
