"""Thread-safe PySide6 Qt Bridge for ATBMind Runtime Event Telemetry.

Subscribes to atbmind_core.runtime.event_bus.AsyncEventBus and re-emits PySide6
Qt signals on the main thread for subagent lifecycle, background tasks,
timers, skills, and file change telemetry.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal

from atbmind_core.runtime.event_bus import (
    ArtifactCreatedEvent,
    ArtifactUpdatedEvent,
    AsyncEventBus,
    FilesChangedEvent,
    SkillActivatedEvent,
    SkillBoundRoleEvent,
    SkillInstalledEvent,
    SkillUpdatedEvent,
    SubagentLifecycleEvent,
    TaskOutputEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
)

logger = logging.getLogger(__name__)


class EventBusQtBridge(QObject):
    """Thread-safe bridge receiving AsyncEventBus runtime events and emitting Qt signals."""

    # Qt Signals for runtime UI updates
    subagent_lifecycle_changed = Signal(str, str, str)  # id, state, detail
    task_status_changed = Signal(str, str, str)         # id, status, summary
    task_output_received = Signal(str, str)             # id, chunk
    timer_fired = Signal(str, str, bool)                # id, prompt, is_cron
    skill_activated = Signal(str, str)                  # skill_name, skill_path
    skill_installed = Signal(str, str, str)             # skill_name, source_type, scope
    skill_updated = Signal(str, str, str)               # skill_name, version, message
    skill_bound_role = Signal(str, str, str)            # skill_name, role_id, action
    files_changed_updated = Signal(list)                # diff_list / files
    artifact_created = Signal(dict)                     # artifact dict
    artifact_updated = Signal(dict)                     # artifact dict
    queued_message_dispatched = Signal(str)             # prompt

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bus: Optional[AsyncEventBus] = None

    @property
    def bus(self) -> Optional[AsyncEventBus]:
        """Returns the currently attached AsyncEventBus, if any."""
        return self._bus

    def attach_bus(self, bus: AsyncEventBus) -> None:
        """Attaches to an AsyncEventBus and registers typed event handlers."""
        if self._bus is not None:
            self.detach_bus()

        self._bus = bus
        self._bus.subscribe(SubagentLifecycleEvent, self._handle_subagent_lifecycle)
        self._bus.subscribe(TaskStatusChangedEvent, self._handle_task_status_changed)
        self._bus.subscribe(TaskOutputEvent, self._handle_task_output)
        self._bus.subscribe(TimerFiredEvent, self._handle_timer_fired)
        self._bus.subscribe(SkillActivatedEvent, self._handle_skill_activated)
        self._bus.subscribe(SkillInstalledEvent, self._handle_skill_installed)
        self._bus.subscribe(SkillUpdatedEvent, self._handle_skill_updated)
        self._bus.subscribe(SkillBoundRoleEvent, self._handle_skill_bound_role)
        self._bus.subscribe(FilesChangedEvent, self._handle_files_changed)
        self._bus.subscribe(ArtifactCreatedEvent, self._handle_artifact_created)
        self._bus.subscribe(ArtifactUpdatedEvent, self._handle_artifact_updated)
        logger.debug("Attached EventBusQtBridge to AsyncEventBus %s", bus)

    def detach_bus(self) -> None:
        """Detaches from the current AsyncEventBus and unregisters handlers."""
        if self._bus is None:
            return

        self._bus.unsubscribe(SubagentLifecycleEvent, self._handle_subagent_lifecycle)
        self._bus.unsubscribe(TaskStatusChangedEvent, self._handle_task_status_changed)
        self._bus.unsubscribe(TaskOutputEvent, self._handle_task_output)
        self._bus.unsubscribe(TimerFiredEvent, self._handle_timer_fired)
        self._bus.unsubscribe(SkillActivatedEvent, self._handle_skill_activated)
        self._bus.unsubscribe(SkillInstalledEvent, self._handle_skill_installed)
        self._bus.unsubscribe(SkillUpdatedEvent, self._handle_skill_updated)
        self._bus.unsubscribe(SkillBoundRoleEvent, self._handle_skill_bound_role)
        self._bus.unsubscribe(FilesChangedEvent, self._handle_files_changed)
        self._bus.unsubscribe(ArtifactCreatedEvent, self._handle_artifact_created)
        self._bus.unsubscribe(ArtifactUpdatedEvent, self._handle_artifact_updated)
        logger.debug("Detached EventBusQtBridge from AsyncEventBus %s", self._bus)
        self._bus = None

    # Internal event bus handler callbacks
    def _handle_task_output(self, event: TaskOutputEvent) -> None:
        try:
            self.task_output_received.emit(
                event.source_id,
                event.chunk,
            )
        except Exception as e:
            logger.error("Error emitting task_output_received signal: %s", e, exc_info=True)

    def _handle_subagent_lifecycle(self, event: SubagentLifecycleEvent) -> None:
        try:
            self.subagent_lifecycle_changed.emit(
                event.subagent_id or event.source_id,
                event.state,
                event.detail,
            )
        except Exception as e:
            logger.error("Error emitting subagent_lifecycle_changed signal: %s", e, exc_info=True)

    def _handle_task_status_changed(self, event: TaskStatusChangedEvent) -> None:
        try:
            self.task_status_changed.emit(
                event.source_id,
                event.new_status,
                event.summary,
            )
        except Exception as e:
            logger.error("Error emitting task_status_changed signal: %s", e, exc_info=True)

    def _handle_timer_fired(self, event: TimerFiredEvent) -> None:
        try:
            self.timer_fired.emit(
                event.timer_id or event.source_id,
                event.prompt,
                event.is_cron,
            )
        except Exception as e:
            logger.error("Error emitting timer_fired signal: %s", e, exc_info=True)

    def _handle_skill_activated(self, event: SkillActivatedEvent) -> None:
        try:
            self.skill_activated.emit(
                event.skill_name or event.source_id,
                event.skill_path,
            )
        except Exception as e:
            logger.error("Error emitting skill_activated signal: %s", e, exc_info=True)

    def _handle_skill_installed(self, event: SkillInstalledEvent) -> None:
        try:
            self.skill_installed.emit(
                event.skill_name or event.source_id,
                event.source_type,
                event.scope,
            )
        except Exception as e:
            logger.error("Error emitting skill_installed signal: %s", e, exc_info=True)

    def _handle_skill_updated(self, event: SkillUpdatedEvent) -> None:
        try:
            self.skill_updated.emit(
                event.skill_name or event.source_id,
                event.version,
                event.message,
            )
        except Exception as e:
            logger.error("Error emitting skill_updated signal: %s", e, exc_info=True)

    def _handle_skill_bound_role(self, event: SkillBoundRoleEvent) -> None:
        try:
            self.skill_bound_role.emit(
                event.skill_name or event.source_id,
                event.role_id,
                event.action,
            )
        except Exception as e:
            logger.error("Error emitting skill_bound_role signal: %s", e, exc_info=True)

    def _handle_files_changed(self, event: FilesChangedEvent) -> None:
        try:
            self.files_changed_updated.emit(
                list(event.files),
            )
        except Exception as e:
            logger.error("Error emitting files_changed_updated signal: %s", e, exc_info=True)

    def _handle_artifact_created(self, event: ArtifactCreatedEvent) -> None:
        try:
            self.artifact_created.emit(dict(event.artifact))
        except Exception as e:
            logger.error("Error emitting artifact_created signal: %s", e, exc_info=True)

    def _handle_artifact_updated(self, event: ArtifactUpdatedEvent) -> None:
        try:
            self.artifact_updated.emit(dict(event.artifact))
        except Exception as e:
            logger.error("Error emitting artifact_updated signal: %s", e, exc_info=True)

    # Direct emission fallback helpers
    def emit_subagent_lifecycle(self, subagent_id: str, state: str, detail: str = "") -> None:
        """Directly emits subagent_lifecycle_changed for fallback or testing."""
        self.subagent_lifecycle_changed.emit(subagent_id, state, detail)

    def emit_task_status(self, task_id: str, status: str, summary: str = "") -> None:
        """Directly emits task_status_changed for fallback or testing."""
        self.task_status_changed.emit(task_id, status, summary)

    def emit_task_output(self, task_id: str, chunk: str) -> None:
        """Directly emits task_output_received for fallback or testing."""
        self.task_output_received.emit(task_id, chunk)

    def emit_timer_fired(self, timer_id: str, prompt: str = "", is_cron: bool = False) -> None:
        """Directly emits timer_fired for fallback or testing."""
        self.timer_fired.emit(timer_id, prompt, is_cron)

    def emit_skill_activated(self, skill_name: str, skill_path: str = "") -> None:
        """Directly emits skill_activated for fallback or testing."""
        self.skill_activated.emit(skill_name, skill_path)

    def emit_skill_installed(self, skill_name: str, source_type: str = "", scope: str = "") -> None:
        """Directly emits skill_installed for fallback or testing."""
        self.skill_installed.emit(skill_name, source_type, scope)

    def emit_skill_updated(self, skill_name: str, version: str = "", message: str = "") -> None:
        """Directly emits skill_updated for fallback or testing."""
        self.skill_updated.emit(skill_name, version, message)

    def emit_skill_bound_role(self, skill_name: str, role_id: str, action: str = "bind") -> None:
        """Directly emits skill_bound_role for fallback or testing."""
        self.skill_bound_role.emit(skill_name, role_id, action)

    def emit_files_changed(self, files: list) -> None:
        """Directly emits files_changed_updated for fallback or testing."""
        self.files_changed_updated.emit(list(files))

    def emit_artifact_created(self, artifact: dict) -> None:
        """Directly emits artifact_created for fallback or testing."""
        self.artifact_created.emit(dict(artifact))

    def emit_artifact_updated(self, artifact: dict) -> None:
        """Directly emits artifact_updated for fallback or testing."""
        self.artifact_updated.emit(dict(artifact))

    def emit_queued_message_dispatched(self, prompt: str) -> None:
        """Directly emits queued_message_dispatched for fallback or testing."""
        self.queued_message_dispatched.emit(prompt)
