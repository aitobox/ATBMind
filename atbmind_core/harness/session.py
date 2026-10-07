"""
ATBMind AgentSession and Persistence Adapter
Manages conversation state, steering queues, compaction, and SQLite synchronization.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from atbmind_core.harness.loop import (
    AgentContext,
    AgentLoopConfig,
    agent_loop,
)
from atbmind_core.harness.tools.base import AgentTool, ToolResult
from atbmind_core.harness.types import (
    AgentEvent,
    AgentEventType,
    AgentMessage,
    Role,
    ToolCall,
)
from atbmind_core.storage.session_store import SessionStore

logger = logging.getLogger("atbmind.harness.session")

class AgentSession:
    """
    Session coordinator that manages the lifecycle of a single conversation,
    linking the Agent Loop with persistent storage and interactive steering.
    """

    def __init__(
        self,
        session_id: str,
        stream_client: Any,
        tools: Optional[List[AgentTool]] = None,
        system_prompt: Optional[str] = None,
        store: Optional[SessionStore] = None,
        max_context_tokens: int = 32000,
        compaction_threshold: float = 0.75,
        before_tool_call: Optional[Callable] = None,
        after_tool_call: Optional[Callable] = None,
    ) -> None:
        self.session_id = session_id
        self.stream_client = stream_client
        self.tools: List[AgentTool] = tools or []
        self.system_prompt = system_prompt
        self.store = store
        self.max_context_tokens = max_context_tokens
        self.compaction_threshold = compaction_threshold
        self.before_tool_call = before_tool_call
        self.after_tool_call = after_tool_call

        import collections
        import threading

        self.messages: List[AgentMessage] = []
        self._steering_queue: collections.deque[AgentMessage] = collections.deque()
        self._steering_lock: threading.Lock = threading.Lock()
        self._persisted_count: int = 0

        # Load existing messages if store is provided
        if self.store is not None:
            self._load_from_store()

    def _load_from_store(self) -> None:
        try:
            records = self.store.get_messages(self.session_id)
            for rec in records:
                role = Role(rec.role)
                meta: Dict[str, Any] = {}
                if rec.attachment_path:
                    meta["image_path"] = rec.attachment_path
                if rec.plugin_payload:
                    try:
                        meta.update(json.loads(rec.plugin_payload))
                    except Exception:
                        pass
                msg = AgentMessage(
                    role=role,
                    content=rec.content,
                    name=rec.plugin_id,
                    metadata=meta,
                )
                self.messages.append(msg)
            self._persisted_count = len(self.messages)
        except Exception as e:
            logger.warning("Failed loading messages from store for session %s: %s", self.session_id, e)

    def send_steering(self, content: str) -> None:
        """Injects an out-of-band steering message to alter agent behavior mid-run. Thread-safe."""
        msg = AgentMessage(
            role=Role.USER,
            content=content,
            metadata={"is_steering": True},
        )
        with self._steering_lock:
            self._steering_queue.append(msg)

    async def get_steering_messages(self) -> List[AgentMessage]:
        """Drains pending steering messages from the queue. Thread-safe."""
        with self._steering_lock:
            messages = list(self._steering_queue)
            self._steering_queue.clear()
        return messages

    def estimate_tokens(self) -> int:
        """Heuristic token estimation: ~3 characters per token on average."""
        total_chars = 0
        for m in self.messages:
            if m.content:
                total_chars += len(m.content)
            if m.tool_calls:
                for tc in m.tool_calls:
                    total_chars += len(tc.name) + len(json.dumps(tc.arguments))
        return total_chars // 3

    def maybe_compact(self) -> bool:
        """
        Compacts the conversation history if total tokens exceed compaction threshold.
        Keeps system message and recent turns while collapsing older turns into a summary.
        """
        if self.estimate_tokens() <= self.max_context_tokens * self.compaction_threshold:
            return False

        if len(self.messages) <= 4:
            return False

        # Split into historical messages to summarize and recent messages to keep
        keep_recent_count = 4
        start_idx = 1 if (self.messages and self.messages[0].role == Role.SYSTEM) else 0
        messages_to_summarize = self.messages[start_idx:-keep_recent_count]
        recent_messages = self.messages[-keep_recent_count:]

        if not messages_to_summarize:
            return False

        summary_snippets = []
        for m in messages_to_summarize:
            role_tag = m.role.value
            snippet = (m.content or "")[:80].replace("\n", " ")
            summary_snippets.append(f"{role_tag}: {snippet}...")

        summary_text = f"[Previous Conversation Summary: Collapsed {len(messages_to_summarize)} turns. Snippets: {' | '.join(summary_snippets)}]"
        summary_msg = AgentMessage(role=Role.SYSTEM, content=summary_text)

        new_messages: List[AgentMessage] = []
        if start_idx == 1:
            new_messages.append(self.messages[0])
        new_messages.append(summary_msg)
        new_messages.extend(recent_messages)

        self.messages = new_messages
        return True

    def _sync_to_store(self) -> None:
        """Persists newly appended messages into SQLite store."""
        if self.store is None:
            return

        import time
        import uuid
        from atbmind_core.storage.schemas import MessageRecord

        while self._persisted_count < len(self.messages):
            msg = self.messages[self._persisted_count]
            attachment_path = msg.metadata.get("image_path")
            plugin_id = msg.name or msg.metadata.get("plugin_id")
            plugin_payload = msg.metadata if msg.metadata else None

            try:
                rec = MessageRecord(
                    message_id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    role=msg.role.value,
                    content=msg.content or "",
                    attachment_path=attachment_path,
                    plugin_id=plugin_id,
                    plugin_payload=plugin_payload,
                    created_at=time.time(),
                )
                self.store.append_message(rec)
            except Exception as e:
                logger.error("Failed persisting message to store: %s", e)
            self._persisted_count += 1

    async def prompt(
        self,
        content: str,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[AgentEvent]:
        """
        Executes a prompt turn using the underlying Agent Loop and synchronizes state.
        """
        self.maybe_compact()

        user_message = AgentMessage(role=Role.USER, content=content)

        context = AgentContext(
            messages=self.messages,
            tools=self.tools,
            system_prompt=self.system_prompt,
        )

        config = AgentLoopConfig(
            stream_client=self.stream_client,
            before_tool_call=self.before_tool_call,
            after_tool_call=self.after_tool_call,
            get_steering_messages=self.get_steering_messages,
        )

        async for event in agent_loop([user_message], context, config, cancellation_token):
            yield event
            if event.type in (AgentEventType.TURN_END, AgentEventType.AGENT_END):
                self._sync_to_store()
