"""Unified Asynchronous Event Bus (AsyncEventBus) for ATBMind Runtime.

Provides typed event contracts and pub/sub routing across background tasks,
subagents, and UI bridges without polling.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
import inspect
import logging
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional, Type, TypeVar, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RuntimeEvent(BaseModel):
    """Base event model for all ATBMind runtime events."""

    timestamp: datetime = Field(default_factory=datetime.now)
    source_id: str = ""

    model_config = {"extra": "allow"}


class TaskOutputEvent(RuntimeEvent):
    """Fired when a background task produces incremental stdout/stderr output."""

    chunk: str = ""
    stream: Literal["stdout", "stderr"] = "stdout"


class TaskStatusChangedEvent(RuntimeEvent):
    """Fired when a background task transitions its lifecycle status."""

    old_status: str = ""
    new_status: str = ""  # e.g., "running", "done", "failed", "killed"
    exit_code: Optional[int] = None
    summary: str = ""


class TimerFiredEvent(RuntimeEvent):
    """Fired when a scheduled timer or cron trigger activates."""

    timer_id: str = ""
    prompt: str = ""
    is_cron: bool = False

    def model_post_init(self, __context: Any) -> None:
        if not self.source_id and self.timer_id:
            self.source_id = self.timer_id


class SubagentLifecycleEvent(RuntimeEvent):
    """Fired when a subagent transitions lifecycle states."""

    subagent_id: str = ""
    state: Literal[
        "running",
        "idle",
        "waiting_for_message",
        "waiting_for_input",
        "waiting_for_dependents",
        "canceling",
        "errored",
        "done",
    ] = "idle"
    detail: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.source_id and self.subagent_id:
            self.source_id = self.subagent_id


class SubagentMessageEvent(RuntimeEvent):
    """Fired when messages are exchanged between agents (e.g. parent <-> subagent)."""

    sender_id: str = ""
    recipient_id: str = ""
    content: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.source_id and self.sender_id:
            self.source_id = self.sender_id


class SkillActivatedEvent(RuntimeEvent):
    """Fired when a skill is activated or triggered."""

    skill_name: str = ""
    skill_path: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.source_id and self.skill_name:
            self.source_id = self.skill_name


class FilesChangedEvent(RuntimeEvent):
    """Fired when workspace files are modified, created, or deleted."""

    files: List[Any] = Field(default_factory=list)


class AskQuestionEvent(RuntimeEvent):
    """Fired when an agent requests interactive user input or multiple choice answers."""

    model_config = {"extra": "allow", "arbitrary_types_allowed": True}

    questions: List[Dict[str, Any]] = Field(default_factory=list)
    future: Optional[Any] = None
    response_future: Optional[Any] = None
    tool_action: str = ""
    tool_summary: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.source_id:
            self.source_id = "ask_question"
        if self.future is None and self.response_future is not None:
            self.future = self.response_future
        elif self.response_future is None and self.future is not None:
            self.response_future = self.future



EventHandler = Union[
    Callable[[Any], Coroutine[Any, Any, None]],
    Callable[[Any], None],
]

T = TypeVar("T", bound=RuntimeEvent)


class AsyncEventBus:
    """In-memory typed asynchronous event bus with ring buffer history."""

    def __init__(self, max_history: int = 1000) -> None:
        self.max_history = max_history
        self._history: deque[RuntimeEvent] = deque(maxlen=max_history)
        self._subscribers: Dict[Type[RuntimeEvent], List[EventHandler]] = {}

    def subscribe(self, event_cls: Type[T], handler: EventHandler) -> None:
        """Register a handler for a specific event type or its subclasses."""
        if event_cls not in self._subscribers:
            self._subscribers[event_cls] = []
        if handler not in self._subscribers[event_cls]:
            self._subscribers[event_cls].append(handler)

    def unsubscribe(self, event_cls: Type[T], handler: EventHandler) -> bool:
        """Unregister a handler for an event type. Returns True if removed."""
        if event_cls in self._subscribers and handler in self._subscribers[event_cls]:
            self._subscribers[event_cls].remove(handler)
            return True
        return False

    async def publish(self, event: RuntimeEvent) -> None:
        """Publish an event to all matching subscribers and append to ring buffer."""
        self._history.append(event)

        # Find matching handlers (supporting polymorphism / inheritance)
        matched_handlers: List[EventHandler] = []
        for subscribed_cls, handlers in list(self._subscribers.items()):
            if isinstance(event, subscribed_cls):
                matched_handlers.extend(handlers)

        for handler in matched_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    res = handler(event)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                logger.error(
                    "Error executing event handler %s for %s: %s",
                    handler,
                    type(event).__name__,
                    e,
                    exc_info=True,
                )

    def get_history(
        self,
        limit: Optional[int] = None,
        event_cls: Optional[Type[T]] = None,
        source_id: Optional[str] = None,
        event_type: Optional[Type[T]] = None,
    ) -> List[RuntimeEvent]:
        """Query historical events with optional type, source_id, and limit filtering."""
        target_cls = event_cls or event_type
        items = list(self._history)
        if target_cls is not None:
            items = [e for e in items if isinstance(e, target_cls)]
        if source_id is not None:
            items = [e for e in items if e.source_id == source_id]
        if limit is not None:
            if limit <= 0:
                return []
            items = items[-limit:]
        return items

    def clear(self) -> None:
        """Clear all event history and subscribers."""
        self._history.clear()
        self._subscribers.clear()
