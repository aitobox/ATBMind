"""Antigravity-Grade Multi-Agent Collaboration and Lifecycle Management Toolset.

Implements:
- InvokeSubagentTool (invoke_subagent)
- SendMessageTool (send_message)
- ManageSubagentsTool (manage_subagents)
- DefineSubagentTool (define_subagent)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult

if TYPE_CHECKING:
    from atbmind_core.runtime.subagents import SubagentOrchestrator


def _get_default_orchestrator() -> Any:
    from atbmind_core.runtime.subagents import SubagentOrchestrator
    return SubagentOrchestrator()


# ============================================================================
# 1. InvokeSubagentTool (invoke_subagent)
# ============================================================================

class SubagentSpec(BaseModel):
    """Specification for invoking a subagent instance."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    TypeName: str = Field(..., description="Type name of the subagent to invoke.")
    Role: str = Field(..., description="A 2-5 word description of the subagent's role.")
    Prompt: str = Field(..., description="A clear, actionable task description for the subagent.")
    Model: Optional[str] = Field("inherit", description="Model to use: 'inherit', 'flash_lite', 'flash', 'pro'.")
    Workspace: Optional[str] = Field("inherit", description="Workspace mode: 'inherit', 'branch', 'share'.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "type_name": "TypeName",
                "name": "TypeName",
                "type": "TypeName",
                "role": "Role",
                "role_title": "Role",
                "prompt": "Prompt",
                "task": "Prompt",
                "model": "Model",
                "workspace": "Workspace",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class InvokeSubagentInput(BaseModel):
    """Schema for invoke_subagent tool parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    Subagents: List[SubagentSpec] = Field(..., description="Array of subagents to invoke concurrently.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "subagents" in data and "Subagents" not in data:
                d = dict(data)
                d["Subagents"] = d.pop("subagents")
                return d
        return data


class InvokeSubagentTool(AgentTool):
    """
    Invokes one or more subagents by name with a single tool call.
    Each subagent runs in the background with its own prompt, isolated transcript, and reports back when done.
    """
    name = "invoke_subagent"
    description = (
        "Invokes one or more subagents by name with a single tool call. "
        "Each subagent runs in the background with its own prompt and reports back when done."
    )
    parameters_schema = InvokeSubagentInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, orchestrator: Optional[SubagentOrchestrator] = None) -> None:
        self.orchestrator = orchestrator if orchestrator is not None else _get_default_orchestrator()

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
            params = InvokeSubagentInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for invoke_subagent: {e}", is_error=True)

        if not params.Subagents:
            return ToolResult(content="Error: Subagents array cannot be empty.", is_error=True)

        orch = getattr(context, "subagent_orchestrator", None) or getattr(context, "orchestrator", None) or self.orchestrator
        parent_id = getattr(context, "session_id", "root-session")

        spawned_results: List[Dict[str, Any]] = []
        output_lines: List[str] = []

        for spec in params.Subagents:
            try:
                sub_id = await orch.spawn_subagent(
                    type_name=spec.TypeName,
                    role_title=spec.Role,
                    prompt=spec.Prompt,
                    parent_id=parent_id,
                    model=spec.Model or "inherit",
                    workspace=spec.Workspace or "inherit",
                )
                info = orch.get_subagent_info(sub_id) or {}
                spawned_results.append({
                    "conversationId": sub_id,
                    "type": spec.TypeName,
                    "role": spec.Role,
                    "state": info.get("state", "running"),
                })
                output_lines.append(f"- Spawned [{spec.Role}] ({spec.TypeName}) with conversation ID: {sub_id}")
            except Exception as e:
                return ToolResult(
                    content=f"Error spawning subagent '{spec.Role}' ({spec.TypeName}): {e}",
                    is_error=True,
                )

        header = f"Successfully launched {len(spawned_results)} subagent(s):\n"
        content_text = header + "\n".join(output_lines)
        return ToolResult(content=content_text, is_error=False, metadata={"spawned": spawned_results})

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)


# ============================================================================
# 2. SendMessageTool (send_message)
# ============================================================================

class SendMessageInput(BaseModel):
    """Schema for send_message tool parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    Recipient: str = Field(..., description="The recipient ID to send the message to, e.g. a subagent conversation ID.")
    Message: str = Field(..., description="The message content.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "recipient": "Recipient",
                "recipient_id": "Recipient",
                "conversation_id": "Recipient",
                "conversationId": "Recipient",
                "message": "Message",
                "content": "Message",
                "text": "Message",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class SendMessageTool(AgentTool):
    """
    Send a message to another agent. This tool can be used to communicate with subagents,
    peer agents, etc. Do not use this tool to communicate with the user.
    """
    name = "send_message"
    description = (
        "Send a message to another agent. This tool can be used to communicate with subagents, "
        "peer agents, etc. Do not use this tool to communicate with the user."
    )
    parameters_schema = SendMessageInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, orchestrator: Optional[SubagentOrchestrator] = None) -> None:
        self.orchestrator = orchestrator if orchestrator is not None else _get_default_orchestrator()

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
            params = SendMessageInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for send_message: {e}", is_error=True)

        if not params.Recipient.strip():
            return ToolResult(content="Error: Recipient is required.", is_error=True)
        if not params.Message.strip():
            return ToolResult(content="Error: Message content cannot be empty.", is_error=True)

        orch = getattr(context, "subagent_orchestrator", None) or getattr(context, "orchestrator", None) or self.orchestrator
        sender_id = getattr(context, "session_id", "root-session")

        success = await orch.send_message(
            recipient_id=params.Recipient,
            message=params.Message,
            sender_id=sender_id,
        )

        if success:
            return ToolResult(
                content=f"Message successfully sent to subagent '{params.Recipient}'.",
                is_error=False,
                metadata={"recipient": params.Recipient, "delivered": True},
            )
        else:
            return ToolResult(
                content=f"Error: Subagent '{params.Recipient}' not found or is no longer active.",
                is_error=True,
                metadata={"recipient": params.Recipient, "delivered": False},
            )

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)


# ============================================================================
# 3. ManageSubagentsTool (manage_subagents)
# ============================================================================

class ManageSubagentsInput(BaseModel):
    """Schema for manage_subagents tool parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    Action: Literal["list", "kill", "kill_all"] = Field(..., description="Action to perform: 'list', 'kill', 'kill_all'.")
    ConversationIds: Optional[List[str]] = Field(None, description="The IDs of the subagents to kill. Required for 'kill'.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "action": "Action",
                "conversation_ids": "ConversationIds",
                "conversationIds": "ConversationIds",
                "ids": "ConversationIds",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class ManageSubagentsTool(AgentTool):
    """
    Manage existing subagents.
    Actions:
    - 'list': List active subagents with conversation IDs, state, and logs
    - 'kill': Terminate specific subagents by ConversationIds
    - 'kill_all': Terminate all active subagents
    """
    name = "manage_subagents"
    description = (
        "Manage existing subagents.\n"
        "Actions: 'list' (list active subagents), 'kill' (terminate specific subagents), "
        "'kill_all' (terminate all active subagents)."
    )
    parameters_schema = ManageSubagentsInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, orchestrator: Optional[SubagentOrchestrator] = None) -> None:
        self.orchestrator = orchestrator if orchestrator is not None else _get_default_orchestrator()

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
            params = ManageSubagentsInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for manage_subagents: {e}", is_error=True)

        orch = getattr(context, "subagent_orchestrator", None) or getattr(context, "orchestrator", None) or self.orchestrator

        if params.Action == "list":
            subagents = orch.list_subagents()
            formatted = json.dumps(subagents, indent=2, ensure_ascii=False)
            return ToolResult(content=formatted, is_error=False, metadata={"subagents": subagents})

        if params.Action == "kill":
            if not params.ConversationIds:
                return ToolResult(
                    content="Error: ConversationIds is required when Action is 'kill'.",
                    is_error=True,
                )
            killed: List[str] = []
            for cid in params.ConversationIds:
                ok = await orch.kill_subagent(cid)
                if ok:
                    killed.append(cid)
            return ToolResult(
                content=f"Terminated subagents: {', '.join(killed) if killed else 'None'}",
                is_error=False,
                metadata={"killed": killed},
            )

        if params.Action == "kill_all":
            count = await orch.kill_all()
            return ToolResult(
                content=f"Terminated all {count} active subagent(s).",
                is_error=False,
                metadata={"count": count},
            )

        return ToolResult(content=f"Error: Unsupported action '{params.Action}'.", is_error=True)

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)


# ============================================================================
# 4. DefineSubagentTool (define_subagent)
# ============================================================================

class DefineSubagentInput(BaseModel):
    """Schema for define_subagent tool parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(..., description="Unique name for the subagent. Used to invoke it via invoke_subagent.")
    description: str = Field(..., description="Human-readable description of what this subagent does.")
    system_prompt: str = Field(..., description="A detailed system prompt for this subagent.")
    enable_write_tools: bool = Field(False, description="Set true to equip the subagent with tools to create/edit files and run commands.")
    enable_subagent_tools: bool = Field(False, description="Set true to equip the subagent with tools to define and invoke its own subagents.")
    enable_mcp_tools: bool = Field(False, description="Set true to enable MCP tools.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "Name": "name",
                "Description": "description",
                "SystemPrompt": "system_prompt",
                "systemPrompt": "system_prompt",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class DefineSubagentTool(AgentTool):
    """
    Defines a new type of subagent that can be invoked via invoke_subagent.
    """
    name = "define_subagent"
    description = (
        "Defines a new type of subagent that can be invoked via invoke_subagent.\n"
        "Registers dynamic role specification with customized prompt and capability flags."
    )
    parameters_schema = DefineSubagentInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, orchestrator: Optional[SubagentOrchestrator] = None) -> None:
        self.orchestrator = orchestrator if orchestrator is not None else _get_default_orchestrator()

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
            params = DefineSubagentInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for define_subagent: {e}", is_error=True)

        orch = getattr(context, "subagent_orchestrator", None) or getattr(context, "orchestrator", None) or self.orchestrator

        orch.define_subagent(
            name=params.name,
            description=params.description,
            system_prompt=params.system_prompt,
            enable_write_tools=params.enable_write_tools,
            enable_subagent_tools=params.enable_subagent_tools,
            enable_mcp_tools=params.enable_mcp_tools,
        )

        return ToolResult(
            content=f"Subagent type '{params.name}' defined successfully and ready for invocation.",
            is_error=False,
            metadata={"name": params.name},
        )

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return await self.execute(args, context, **kwargs)
