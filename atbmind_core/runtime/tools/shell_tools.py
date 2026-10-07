"""
Antigravity-Grade Shell Execution and Task Governance Toolset.
Implements RunCommandTool (run_command) and ManageTaskTool (manage_task).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Literal, Optional, Type
from pydantic import BaseModel, ConfigDict, Field, model_validator

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.runtime.tasks import TaskManager


# ============================================================================
# 1. RunCommandTool (run_command)
# ============================================================================

class RunCommandInput(BaseModel):
    """Schema for run_command parameters adhering to Antigravity runtime specification."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    CommandLine: str = Field(..., description="The exact command line string to execute.")
    Cwd: str = Field(..., description="The current working directory for the command.")
    WaitMsBeforeAsync: int = Field(5000, description="Milliseconds to wait before sending command to background.")
    IsDaemon: bool = Field(False, description="Set to true for long-running support processes.")
    RunPersistent: bool = Field(False, description="Set to true to run in a persistent terminal preserving environment.")
    RequestedTerminalID: Optional[str] = Field(None, description="Optional ID of a persistent terminal to reuse.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "command": "CommandLine",
                "command_line": "CommandLine",
                "cmd": "CommandLine",
                "cwd": "Cwd",
                "wait_ms": "WaitMsBeforeAsync",
                "wait_ms_before_async": "WaitMsBeforeAsync",
                "is_daemon": "IsDaemon",
                "run_persistent": "RunPersistent",
                "requested_terminal_id": "RequestedTerminalID",
                "terminal_id": "RequestedTerminalID",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class RunCommandTool(AgentTool):
    """
    PROPOSE a command to run on behalf of the user. Operating System: mac. Shell: zsh.
    **NEVER PROPOSE A cd COMMAND**.
    Adaptive execution: completes synchronously within WaitMsBeforeAsync or smoothly
    transitions to background task streaming output to persistent log file.
    """
    name = "run_command"
    description = (
        "PROPOSE a command to run on behalf of the user. Operating System: mac. Shell: zsh.\n"
        "**NEVER PROPOSE A cd COMMAND**.\n"
        "Executes with adaptive synchronous/asynchronous transition. If command completes within "
        "WaitMsBeforeAsync, returns output synchronously. Otherwise transitions to background task."
    )
    parameters_schema = RunCommandInput
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
            params = RunCommandInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for run_command: {e}", is_error=True)

        if not params.CommandLine.strip():
            return ToolResult(content="Error: CommandLine is required and cannot be empty", is_error=True)

        cwd_path = os.path.abspath(params.Cwd)
        if not os.path.exists(cwd_path):
            return ToolResult(content=f"Error: Working directory '{cwd_path}' does not exist", is_error=True)
        if not os.path.isdir(cwd_path):
            return ToolResult(content=f"Error: Working directory '{cwd_path}' is not a directory", is_error=True)

        # Contextual task manager override if provided
        tm = getattr(context, "task_manager", None) or self.task_manager

        try:
            res_dict = await tm.run_command(
                command=params.CommandLine,
                cwd=cwd_path,
                wait_ms_before_async=params.WaitMsBeforeAsync,
                is_daemon=params.IsDaemon,
                run_persistent=params.RunPersistent,
                requested_terminal_id=params.RequestedTerminalID,
            )
        except Exception as exc:
            return ToolResult(content=f"Error running command: {exc}", is_error=True)

        if res_dict.get("is_async") is True:
            task_id = res_dict.get("task_id", "")
            log_file = res_dict.get("log_file", "")
            msg = f"Command sent to background as task '{task_id}'. Log file: {log_file}."
            return ToolResult(content=msg, is_error=False, metadata=res_dict)

        # Synchronous execution finished
        exit_code = res_dict.get("exit_code", 0)
        output = res_dict.get("output", "")

        if exit_code != 0:
            err_msg = output if output else f"Command failed with exit code {exit_code}"
            if f"code {exit_code}" not in err_msg and f"{exit_code}" not in err_msg:
                err_msg = f"Command failed with exit code {exit_code}:\n{err_msg}"
            return ToolResult(content=err_msg, is_error=True, metadata=res_dict)

        content = output if output else "(Command finished with exit code 0 and no output)"
        return ToolResult(content=content, is_error=False, metadata=res_dict)

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)


# ============================================================================
# 2. ManageTaskTool (manage_task)
# ============================================================================

class ManageTaskInput(BaseModel):
    """Schema for manage_task parameters adhering to Antigravity runtime specification."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    Action: Literal["list", "kill", "status", "send_input"] = Field(
        ...,
        description="The action to perform: 'list' (list all), 'kill' (cancel), 'status' (check status), 'send_input' (send input).",
    )
    TaskId: Optional[str] = Field(
        None,
        description="The task ID to manage. Required when Action is 'kill', 'status', or 'send_input'.",
    )
    Input: Optional[str] = Field(
        None,
        description="The input to send to the task. Required when Action is 'send_input'.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "action": "Action",
                "task_id": "TaskId",
                "input": "Input",
                "input_text": "Input",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class ManageTaskTool(AgentTool):
    """
    Manage background tasks. Use this tool to list running tasks or interact with tasks
    that were sent to the background.
    Actions: 'list', 'kill', 'status', 'send_input'.
    """
    name = "manage_task"
    description = (
        "Manage background tasks. Use this tool to list running tasks or interact with tasks that were "
        "sent to the background.\n"
        "Actions: 'list', 'kill', 'status', 'send_input'."
    )
    parameters_schema = ManageTaskInput
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
            params = ManageTaskInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for manage_task: {e}", is_error=True)

        if params.Action in ("kill", "status", "send_input") and not params.TaskId:
            return ToolResult(content=f"Error: TaskId is required for action '{params.Action}'", is_error=True)

        if params.Action == "send_input" and params.Input is None:
            return ToolResult(content="Error: Input is required for send_input action", is_error=True)

        tm = getattr(context, "task_manager", None) or self.task_manager

        try:
            res = await tm.manage_task(
                action=params.Action,
                task_id=params.TaskId,
                input_text=params.Input or "",
            )
        except Exception as exc:
            return ToolResult(content=f"Error executing manage_task: {exc}", is_error=True)

        if params.Action == "list":
            return ToolResult(
                content=json.dumps(res, indent=2, ensure_ascii=False),
                is_error=False,
                metadata=res,
            )

        if params.Action == "status":
            if res.get("error") or res.get("success") is False:
                return ToolResult(content=f"Error: {res.get('error', 'Task not found')}", is_error=True, metadata=res)
            return ToolResult(
                content=json.dumps(res, indent=2, ensure_ascii=False),
                is_error=False,
                metadata=res,
            )

        if params.Action == "kill":
            if res.get("success") is True:
                return ToolResult(
                    content=f"Task '{params.TaskId}' successfully killed.",
                    is_error=False,
                    metadata=res,
                )
            return ToolResult(
                content=f"Error: Failed to kill task '{params.TaskId}' (not found or already stopped).",
                is_error=True,
                metadata=res,
            )

        if params.Action == "send_input":
            if res.get("success") is True:
                return ToolResult(
                    content=f"Input sent to task '{params.TaskId}'.",
                    is_error=False,
                    metadata=res,
                )
            return ToolResult(
                content=f"Error: Failed to send input to task '{params.TaskId}' (not running or stdin closed).",
                is_error=True,
                metadata=res,
            )

        return ToolResult(content=f"Error: Unsupported action '{params.Action}'", is_error=True)

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)
