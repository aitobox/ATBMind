"""
Antigravity-Grade Scheduler Toolset.
Implements ScheduleTool (schedule) for one-shot timers and recurring cron jobs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.runtime.tasks import TaskManager


class ScheduleInput(BaseModel):
    """Schema for schedule parameters adhering to Antigravity runtime specification."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    Prompt: str = Field(
        ...,
        description="The message content to include in the notification when the timer fires or cron triggers.",
    )
    DurationSeconds: Optional[Union[int, float]] = Field(
        None,
        description="The number of seconds to wait. Use for one-shot timers. Mutually exclusive with CronExpression.",
    )
    CronExpression: Optional[str] = Field(
        None,
        description="A standard cron expression (5 fields). Use for recurring schedules. Mutually exclusive with DurationSeconds.",
    )
    TimerCondition: Optional[str] = Field(
        "never",
        description="Controls when a one-shot timer should early terminate upon receiving a message: 'never', 'any', or sender ID.",
    )
    MaxIterations: Optional[int] = Field(
        None,
        description="Optional. Maximum number of times the cron schedule will fire before stopping.",
    )
    IsDaemon: bool = Field(
        False,
        description="Optional. Set to true for standing background jobs that persist after current task.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "prompt": "Prompt",
                "duration_seconds": "DurationSeconds",
                "duration": "DurationSeconds",
                "cron_expression": "CronExpression",
                "cron": "CronExpression",
                "timer_condition": "TimerCondition",
                "condition": "TimerCondition",
                "max_iterations": "MaxIterations",
                "is_daemon": "IsDaemon",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class ScheduleTool(AgentTool):
    """
    Schedule a one-shot timer or a recurring cron job that sends notifications in the background.
    - One-shot timer: DurationSeconds + optional TimerCondition ('never', 'any', sender-id).
    - Recurring cron: 5-field CronExpression + optional MaxIterations & IsDaemon.
    """
    name = "schedule"
    description = (
        "Schedule a one-shot timer or a recurring cron job that sends notifications in the background.\n"
        "Exactly one of DurationSeconds or CronExpression must be provided."
    )
    parameters_schema = ScheduleInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, task_manager: Optional[TaskManager] = None) -> None:
        self.task_manager = task_manager or TaskManager()

    async def execute(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        merged: Dict[str, Any] = {}
        if isinstance(args, dict):
            merged.update(args)
        merged.update(kwargs)

        try:
            params = ScheduleInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for schedule: {e}", is_error=True)

        if not params.Prompt or not params.Prompt.strip():
            return ToolResult(content="Error: Prompt is required and cannot be empty", is_error=True)

        has_duration = params.DurationSeconds is not None
        has_cron = bool(params.CronExpression and params.CronExpression.strip())

        if has_duration and has_cron:
            return ToolResult(
                content="Error: Exactly one of DurationSeconds or CronExpression must be specified, not both",
                is_error=True,
            )

        if not has_duration and not has_cron:
            return ToolResult(
                content="Error: Exactly one of DurationSeconds or CronExpression must be specified",
                is_error=True,
            )

        tm = getattr(context, "task_manager", None) or self.task_manager

        if has_duration:
            if params.DurationSeconds < 0:
                return ToolResult(content="Error: DurationSeconds must be non-negative", is_error=True)

            cond = params.TimerCondition or "never"
            try:
                timer_id = await tm.schedule_timer(
                    prompt=params.Prompt,
                    duration_s=float(params.DurationSeconds),
                    condition=cond,
                )
            except Exception as exc:
                return ToolResult(content=f"Error scheduling timer: {exc}", is_error=True)

            msg = (
                f"Scheduled one-shot timer '{timer_id}' for {params.DurationSeconds}s "
                f"with condition '{cond}'. Prompt: {params.Prompt}"
            )
            return ToolResult(
                content=msg,
                is_error=False,
                metadata={
                    "timer_id": timer_id,
                    "task_id": timer_id,
                    "prompt": params.Prompt,
                    "duration_s": params.DurationSeconds,
                    "condition": cond,
                    "is_cron": False,
                },
            )

        # Recurring cron schedule
        cron_expr = params.CronExpression.strip()
        try:
            cron_id = await tm.schedule_cron(
                prompt=params.Prompt,
                cron_expr=cron_expr,
                max_iterations=params.MaxIterations,
                is_daemon=params.IsDaemon,
            )
        except Exception as exc:
            return ToolResult(content=f"Error scheduling cron: {exc}", is_error=True)

        msg = (
            f"Scheduled recurring cron job '{cron_id}' with expression '{cron_expr}'. "
            f"Prompt: {params.Prompt}"
        )
        return ToolResult(
            content=msg,
            is_error=False,
            metadata={
                "timer_id": cron_id,
                "task_id": cron_id,
                "prompt": params.Prompt,
                "cron_expr": cron_expr,
                "max_iterations": params.MaxIterations,
                "is_daemon": params.IsDaemon,
                "is_cron": True,
            },
        )

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)
