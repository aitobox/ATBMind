"""
ATBMind Desktop UI State Coordinator
Manages in-memory active session pointers, loaded sessions, plugin states, and in-flight async workers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from PySide6.QtCore import QObject, Signal

from atbmind_core.storage.schemas import SessionRecord


class UIStateManager(QObject):
    """
    Central in-memory state manager coordinating session selections,
    active plugin parameters, and execution state across PySide6 widgets.
    """

    # Signals
    active_session_changed = Signal(str)               # session_id
    session_in_flight_changed = Signal(str, bool)       # session_id, is_in_flight
    plugin_state_changed = Signal(str, str, dict)       # session_id, plugin_id, plugin_state
    queued_prompts_changed = Signal(str, list)          # session_id, queued_prompts

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.active_session_id: Optional[str] = None
        self.sessions_cache: Dict[str, SessionRecord] = {}
        self.in_flight_sessions: Set[str] = set()
        self._queued_prompts: Dict[str, List[str]] = {}

    def set_active_session(self, session_id: Optional[str]) -> None:
        """Sets current active session and emits active_session_changed if changed."""
        if self.active_session_id != session_id:
            self.active_session_id = session_id
            if session_id:
                self.active_session_changed.emit(session_id)

    def get_active_session(self) -> Optional[SessionRecord]:
        """Returns the SessionRecord of the currently active session if cached."""
        if not self.active_session_id:
            return None
        return self.sessions_cache.get(self.active_session_id)

    def cache_session(self, session: SessionRecord) -> None:
        """Caches or updates a session in local memory."""
        self.sessions_cache[session.session_id] = session

    def get_cached_session(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieves a cached session by ID."""
        return self.sessions_cache.get(session_id)

    def remove_cached_session(self, session_id: str) -> None:
        """Removes a session from local memory cache."""
        self.sessions_cache.pop(session_id, None)
        self.in_flight_sessions.discard(session_id)
        if session_id in self._queued_prompts:
            self._queued_prompts.pop(session_id, None)
            self.queued_prompts_changed.emit(session_id, [])
        if self.active_session_id == session_id:
            self.active_session_id = None

    def set_in_flight(self, session_id: str, in_flight: bool) -> None:
        """Marks or unmarks a session as having a running background task."""
        was_in_flight = session_id in self.in_flight_sessions
        if in_flight:
            self.in_flight_sessions.add(session_id)
        else:
            self.in_flight_sessions.discard(session_id)

        if was_in_flight != in_flight:
            self.session_in_flight_changed.emit(session_id, in_flight)

    def is_in_flight(self, session_id: str) -> bool:
        """Checks if a session is actively executing a task."""
        return session_id in self.in_flight_sessions

    def update_plugin_state(
        self,
        session_id: str,
        plugin_id: Optional[str],
        plugin_state: Dict[str, Any],
    ) -> None:
        """Updates the cached plugin state for a session and emits plugin_state_changed."""
        session = self.sessions_cache.get(session_id)
        if session:
            session.active_plugin_id = plugin_id
            session.plugin_state = dict(plugin_state)
        self.plugin_state_changed.emit(session_id, plugin_id or "", plugin_state)

    def toggle_session_pinned(self, session_id: str) -> bool:
        """Toggles the pinned state of a cached session and returns the new is_pinned value."""
        session = self.sessions_cache.get(session_id)
        if not session:
            return False
        session.is_pinned = not session.is_pinned
        return session.is_pinned

    def queue_prompt(self, session_id: str, prompt: str) -> int:
        """Appends a prompt to the session's prompt queue and emits queued_prompts_changed."""
        if session_id not in self._queued_prompts:
            self._queued_prompts[session_id] = []
        self._queued_prompts[session_id].append(prompt)
        prompts = list(self._queued_prompts[session_id])
        self.queued_prompts_changed.emit(session_id, prompts)
        return len(prompts)

    def pop_queued_prompt(self, session_id: str) -> Optional[str]:
        """Pops and returns the first prompt from the session's queue, or None if empty."""
        queue = self._queued_prompts.get(session_id)
        if not queue:
            return None
        popped = queue.pop(0)
        self.queued_prompts_changed.emit(session_id, list(queue))
        return popped

    def get_queued_prompts(self, session_id: str) -> List[str]:
        """Returns a copy of the queued prompts for the given session."""
        return list(self._queued_prompts.get(session_id, []))

    def remove_queued_prompt(self, session_id: str, index: int) -> bool:
        """Removes the queued prompt at the given index and emits queued_prompts_changed."""
        queue = self._queued_prompts.get(session_id)
        if queue is None or index < 0 or index >= len(queue):
            return False
        queue.pop(index)
        self.queued_prompts_changed.emit(session_id, list(queue))
        return True
