"""Antigravity-Grade Subagent Orchestrator and Lifecycle Manager.

Manages subagent hierarchy, role resolution, concurrent asyncio tasks,
isolated transcript logging (no token leaking to parent session), and mailbox communication.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import json
import logging
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from atbmind_core.harness.tools.base import AgentTool
from atbmind_core.roles.registry import RobotRoleRegistry, RoleRegistry, get_role_registry
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    SubagentLifecycleEvent,
    SubagentMessageEvent,
)

logger = logging.getLogger("atbmind.runtime.subagents")


class SubagentState(StrEnum):
    """Lifecycle states for subagents matching Antigravity runtime specification."""

    RUNNING = "running"
    IDLE = "idle"
    WAITING_FOR_MESSAGE = "waiting_for_message"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_DEPENDENTS = "waiting_for_dependents"
    CANCELING = "canceling"
    ERRORED = "errored"
    DONE = "done"


@dataclass
class SubagentInstance:
    """Represents an active or terminated subagent worker instance."""

    subagent_id: str
    type_name: str
    role_title: str
    prompt: str
    parent_id: str
    state: SubagentState = SubagentState.RUNNING
    state_detail: str = "Initializing"
    model: str = "inherit"
    workspace: str = "inherit"
    system_prompt: str = ""
    tools: List[AgentTool] = field(default_factory=list)
    transcript_path: Path = field(default_factory=lambda: Path(tempfile.gettempdir()))
    mailbox: asyncio.Queue[Tuple[str, str]] = field(default_factory=asyncio.Queue)
    created_at: float = field(default_factory=time.time)
    task: Optional[asyncio.Task] = None
    step_index: int = 1
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes subagent metadata conforming to Antigravity inspection schema."""
        return {
            "conversationId": self.subagent_id,
            "conversation_id": self.subagent_id,
            "subagent_id": self.subagent_id,
            "type": self.type_name,
            "type_name": self.type_name,
            "role": self.role_title or self.type_name,
            "role_title": self.role_title or self.type_name,
            "state": self.state.value if hasattr(self.state, "value") else str(self.state),
            "stateDetail": self.state_detail,
            "state_detail": self.state_detail,
            "transcript": str(self.transcript_path),
            "parent_id": self.parent_id,
            "prompt": self.prompt,
            "model": self.model,
            "workspace": self.workspace,
            "created_at": self.created_at,
        }


class SubagentOrchestrator:
    """
    Subagent Orchestrator governing multi-agent hierarchy, role resolution,
    lifecycle state transitions, context isolation, and message exchange.
    """

    def __init__(
        self,
        event_bus: Optional[AsyncEventBus] = None,
        role_registry: Optional[Union[RoleRegistry, RobotRoleRegistry]] = None,
        transcript_dir: Optional[Union[Path, str]] = None,
    ) -> None:
        self.event_bus = event_bus or AsyncEventBus()
        self.role_registry = role_registry or get_role_registry()
        if transcript_dir is not None:
            self.transcript_dir = Path(transcript_dir).resolve()
        else:
            self.transcript_dir = Path(tempfile.gettempdir()) / "atbmind_transcripts"
        self.transcript_dir.mkdir(parents=True, exist_ok=True)

        self._subagents: Dict[str, SubagentInstance] = {}
        self._dynamic_roles: Dict[str, Dict[str, Any]] = {}
        self._parent_configs: Dict[str, Dict[str, Any]] = {}

    def register_parent_config(
        self,
        session_id: str,
        system_prompt: str,
        tools: Optional[List[AgentTool]] = None,
        model: str = "inherit",
    ) -> None:
        """Stores parent session configuration to allow 'self' subagents to clone parent state."""
        self._parent_configs[session_id] = {
            "system_prompt": system_prompt,
            "tools": list(tools or []),
            "model": model,
        }

    def define_subagent(
        self,
        name: str,
        description: str,
        system_prompt: str,
        enable_write_tools: bool = False,
        enable_subagent_tools: bool = False,
        enable_mcp_tools: bool = False,
    ) -> bool:
        """Dynamically registers a new subagent type specification."""
        self._dynamic_roles[name] = {
            "name": name,
            "description": description,
            "system_prompt": system_prompt,
            "enable_write_tools": enable_write_tools,
            "enable_subagent_tools": enable_subagent_tools,
            "enable_mcp_tools": enable_mcp_tools,
        }
        logger.info("Defined dynamic subagent role '%s': %s", name, description)
        return True

    def _resolve_role(
        self,
        type_name: str,
        role_title: str,
        parent_id: str,
        parent_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, List[AgentTool], str]:
        """
        Resolves role metadata, system prompt, and tools based on type_name:
        1. 'self': Clones parent configuration / prompt / tools
        2. 'research': Preconfigured read-only researcher
        3. Dynamic roles registered via define_subagent
        4. Predefined roles from RobotRoleRegistry (e.g. draw_expert, coordinator)
        5. Fallback generic role
        """
        norm_type = type_name.strip()
        from atbmind_core.runtime.tools.fs_tools import ViewFileTool

        # 1. 'self' role: Clones parent configuration
        if norm_type == "self":
            cfg = parent_config or self._parent_configs.get(parent_id, {})
            resolved_title = role_title or "Parent Clone"
            resolved_prompt = cfg.get(
                "system_prompt",
                "You are an isolated clone of the parent agent, continuing its work with full capabilities.",
            )
            resolved_tools = list(cfg.get("tools", []))
            resolved_model = cfg.get("model", "inherit")
            return resolved_title, resolved_prompt, resolved_tools, resolved_model

        # 2. 'research' role: Read-only researcher
        if norm_type == "research":
            from atbmind_core.runtime.tools.fs_tools import ViewFileTool
            resolved_title = role_title or "Codebase Researcher"
            resolved_prompt = (
                "You are a research subagent equipped with read-only tools for exploring "
                "the codebase, inspecting files, and reading documentation."
            )
            resolved_tools = [ViewFileTool()]
            return resolved_title, resolved_prompt, resolved_tools, "flash"

        # 3. Dynamic roles defined via define_subagent
        if norm_type in self._dynamic_roles:
            from atbmind_core.runtime.tools.fs_tools import ViewFileTool
            dyn = self._dynamic_roles[norm_type]
            resolved_title = role_title or dyn.get("description") or norm_type
            resolved_prompt = dyn.get("system_prompt", f"You are a specialized subagent for {norm_type}.")
            resolved_tools: List[AgentTool] = [ViewFileTool()]

            if dyn.get("enable_write_tools"):
                from atbmind_core.runtime.tools.fs_tools import (
                    ReplaceFileContentTool,
                    WriteToFileTool,
                )
                from atbmind_core.runtime.tools.shell_tools import RunCommandTool
                resolved_tools.extend([WriteToFileTool(), ReplaceFileContentTool(), RunCommandTool()])

            if dyn.get("enable_subagent_tools"):
                from atbmind_core.runtime.tools.subagent_tools import (
                    InvokeSubagentTool,
                    SendMessageTool,
                )
                resolved_tools.extend([
                    InvokeSubagentTool(orchestrator=self),
                    SendMessageTool(orchestrator=self),
                ])
            return resolved_title, resolved_prompt, resolved_tools, "inherit"

        # 4. Predefined roles in RobotRoleRegistry (e.g. draw_expert, coordinator)
        if self.role_registry is not None:
            role = self.role_registry.get_role(norm_type)
            if role is not None:
                resolved_title = role_title or role.name or norm_type
                resolved_prompt = role.system_prompt
                resolved_tools = []
                resolved_model = getattr(role, "model", "inherit") or "inherit"
                return resolved_title, resolved_prompt, resolved_tools, resolved_model

        # 5. Fallback generic role
        resolved_title = role_title or norm_type
        resolved_prompt = f"You are an autonomous subagent specialized as '{norm_type}'."
        return resolved_title, resolved_prompt, [ViewFileTool()], "inherit"

    def _write_transcript_step(
        self,
        instance: SubagentInstance,
        source: str,
        event_type: str,
        content: str,
        thinking: str = "",
    ) -> None:
        """Appends an isolated JSON log entry to the subagent's transcript file."""
        record = {
            "step_index": instance.step_index,
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "type": event_type,
            "content": content,
        }
        if thinking:
            record["thinking"] = thinking

        instance.step_index += 1
        try:
            with open(instance.transcript_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed writing to transcript %s: %s", instance.transcript_path, e)

    async def spawn_subagent(
        self,
        type_name: str,
        role_title: str = "",
        prompt: str = "",
        parent_id: str = "root-session",
        model: str = "inherit",
        workspace: str = "inherit",
        parent_config: Optional[Dict[str, Any]] = None,
        custom_tools: Optional[List[AgentTool]] = None,
    ) -> str:
        """
        Spawns a new isolated subagent with independent asyncio Task, mailbox, and transcript log.
        """
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        resolved_title, resolved_prompt, resolved_tools, resolved_model = self._resolve_role(
            type_name=type_name,
            role_title=role_title,
            parent_id=parent_id,
            parent_config=parent_config,
        )

        final_model = model if model != "inherit" else resolved_model
        final_tools = custom_tools if custom_tools is not None else resolved_tools
        transcript_path = self.transcript_dir / f"{sub_id}.jsonl"

        instance = SubagentInstance(
            subagent_id=sub_id,
            type_name=type_name,
            role_title=resolved_title,
            prompt=prompt,
            parent_id=parent_id,
            state=SubagentState.RUNNING,
            state_detail=f"Spawned {resolved_title}",
            model=final_model,
            workspace=workspace,
            system_prompt=resolved_prompt,
            tools=final_tools,
            transcript_path=transcript_path,
        )

        self._subagents[sub_id] = instance

        # Write initial prompt into isolated transcript
        self._write_transcript_step(
            instance=instance,
            source="USER",
            event_type="USER_INPUT",
            content=prompt,
        )

        # Publish initial lifecycle event
        await self.event_bus.publish(
            SubagentLifecycleEvent(
                subagent_id=sub_id,
                state=SubagentState.RUNNING.value,
                detail=instance.state_detail,
            )
        )

        # Launch background loop
        instance.task = asyncio.create_task(self._subagent_worker_loop(instance))
        # Yield control briefly to let worker initialize
        await asyncio.sleep(0)

        return sub_id

    async def _subagent_worker_loop(self, instance: SubagentInstance) -> None:
        """
        Subagent background task processing initial task and subsequent mailbox messages.
        Maintains isolated context and updates state transitions without leaking to parent.
        """
        try:
            # Transition to IDLE after initial launch
            instance.state = SubagentState.IDLE
            instance.state_detail = "Idle, awaiting messages"
            await self.event_bus.publish(
                SubagentLifecycleEvent(
                    subagent_id=instance.subagent_id,
                    state=SubagentState.IDLE.value,
                    detail=instance.state_detail,
                )
            )

            # Mailbox listener loop
            while not instance.stop_event.is_set():
                get_task = asyncio.create_task(instance.mailbox.get())
                stop_task = asyncio.create_task(instance.stop_event.wait())

                done, pending = await asyncio.wait(
                    [get_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()

                if instance.stop_event.is_set():
                    break

                if get_task in done:
                    sender_id, msg_content = get_task.result()
                    # Transition to RUNNING
                    instance.state = SubagentState.RUNNING
                    instance.state_detail = f"Processing message from {sender_id or 'parent'}"
                    await self.event_bus.publish(
                        SubagentLifecycleEvent(
                            subagent_id=instance.subagent_id,
                            state=SubagentState.RUNNING.value,
                            detail=instance.state_detail,
                        )
                    )

                    # Log message into isolated transcript
                    self._write_transcript_step(
                        instance=instance,
                        source=sender_id or "parent",
                        event_type="USER_MESSAGE",
                        content=msg_content,
                    )

                    # Simulate isolated execution step
                    await asyncio.sleep(0.01)

                    self._write_transcript_step(
                        instance=instance,
                        source="MODEL",
                        event_type="AGENT_RESPONSE",
                        content=f"Processed: {msg_content[:60]}",
                    )

                    # Transition back to IDLE
                    instance.state = SubagentState.IDLE
                    instance.state_detail = "Idle, awaiting messages"
                    await self.event_bus.publish(
                        SubagentLifecycleEvent(
                            subagent_id=instance.subagent_id,
                            state=SubagentState.IDLE.value,
                            detail=instance.state_detail,
                        )
                    )

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Error in subagent worker loop for %s: %s", instance.subagent_id, exc, exc_info=True)
            instance.state = SubagentState.ERRORED
            instance.state_detail = str(exc)
            await self.event_bus.publish(
                SubagentLifecycleEvent(
                    subagent_id=instance.subagent_id,
                    state=SubagentState.ERRORED.value,
                    detail=instance.state_detail,
                )
            )
            return

        instance.state = SubagentState.DONE
        instance.state_detail = "Terminated"
        await self.event_bus.publish(
            SubagentLifecycleEvent(
                subagent_id=instance.subagent_id,
                state=SubagentState.DONE.value,
                detail=instance.state_detail,
            )
        )

    async def send_message(self, recipient_id: str, message: str, sender_id: str = "") -> bool:
        """
        Sends an asynchronous message to a subagent mailbox and fires SubagentMessageEvent.
        Returns True if delivered, False if recipient does not exist or has finished.
        """
        instance = self._subagents.get(recipient_id)
        if not instance:
            return False
        if instance.state == SubagentState.DONE:
            return False

        await instance.mailbox.put((sender_id, message))
        await self.event_bus.publish(
            SubagentMessageEvent(
                sender_id=sender_id,
                recipient_id=recipient_id,
                content=message,
            )
        )
        return True

    def get_subagent_info(self, subagent_id: str) -> Optional[Dict[str, Any]]:
        """Returns Antigravity status dictionary for the given subagent ID."""
        instance = self._subagents.get(subagent_id)
        return instance.to_dict() if instance else None

    def get_instance(self, subagent_id: str) -> Optional[SubagentInstance]:
        """Returns internal SubagentInstance for runtime access."""
        return self._subagents.get(subagent_id)

    def list_subagents(self) -> List[Dict[str, Any]]:
        """Returns list of active and completed subagent descriptors."""
        return [inst.to_dict() for inst in self._subagents.values()]

    async def kill_subagent(self, subagent_id: str) -> bool:
        """Terminates an active subagent and cancels its execution task."""
        instance = self._subagents.get(subagent_id)
        if not instance:
            return False

        if instance.state == SubagentState.DONE:
            return True

        instance.state = SubagentState.CANCELING
        instance.stop_event.set()
        if instance.task and not instance.task.done():
            instance.task.cancel()
            try:
                await instance.task
            except (asyncio.CancelledError, Exception):
                pass

        instance.state = SubagentState.DONE
        instance.state_detail = "Killed"
        await self.event_bus.publish(
            SubagentLifecycleEvent(
                subagent_id=subagent_id,
                state=SubagentState.DONE.value,
                detail="Killed",
            )
        )
        return True

    async def kill_all(self) -> int:
        """Terminates all managed subagents and returns the number of killed agents."""
        count = 0
        for s_id, inst in list(self._subagents.items()):
            if inst.state != SubagentState.DONE:
                await self.kill_subagent(s_id)
                count += 1
        return count

    async def shutdown(self) -> None:
        """Gracefully shuts down the orchestrator and all managed subagents."""
        await self.kill_all()
