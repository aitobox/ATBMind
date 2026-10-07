"""
ATBMindMainWindow
Assembles NavigationSidebar, WorkStreamArea, and InspectorPanel into the unified
Google Antigravity 3-pane desktop layout with horizontal QSplitter, coordinating
multi-session persistence, event-bus telemetry, prompt queuing, and plugin states.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QWidget,
)

from atbmind_core.config import AppConfig, load_config
from atbmind_core.storage.schemas import MessageRecord, SessionRecord
from atbmind_core.storage.session_store import SessionStore
from atbmind_core.runtime.event_bus import get_global_event_bus
from atbmind_core.runtime.tasks import TaskManager
from atbmind_core.runtime.subagents import SubagentOrchestrator
from apps.atbmind_desktop.bridge import EventBusQtBridge
from apps.atbmind_desktop.state import UIStateManager
from apps.atbmind_desktop.theme import ThemeColors, ThemeFonts
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog
from apps.atbmind_desktop.widgets.inspector_panel import InspectorPanel
from apps.atbmind_desktop.widgets.navigation_sidebar import NavigationSidebar
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog
from apps.atbmind_desktop.widgets.work_stream import WorkStreamArea
from apps.atbmind_desktop.workers import GenerationWorker, TitleWorker



class ATBMindMainWindow(QMainWindow):
    """
    Primary desktop window for ATBMind.
    Coordinates UIStateManager, SessionStore, EventBusQtBridge, and 3-pane QSplitter widgets:
    - Left: NavigationSidebar (260px)
    - Center: WorkStreamArea (flexible stretch=1)
    - Right: InspectorPanel (300px)
    """

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        config: Optional[AppConfig] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.config = config or load_config()
        self.session_store = session_store or SessionStore(
            db_path=self.config.storage.db_path,
        )
        self.state_manager = UIStateManager(self)
        self.event_bus = get_global_event_bus()
        self.task_manager = TaskManager(event_bus=self.event_bus)
        self.orchestrator = SubagentOrchestrator(event_bus=self.event_bus)
        self.event_bridge = EventBusQtBridge(self)
        self.event_bridge.attach_bus(self.event_bus)
        self._workers: dict[str, list] = {}
        self._worker_delay_ms: int = 0
        self._sidebar_cached_width: int = 260
        self._inspector_cached_width: int = 300
        self._active_subagents: dict[str, tuple[str, str]] = {}
        self._active_tasks: dict[str, dict] = {}
        self._skills_used: list[tuple[str, str]] = []

        self._init_ui()
        self._connect_signals()
        self._bootstrap_sessions()
        self.show()

    def _init_ui(self) -> None:
        self.setWindowTitle("ATBMind")
        self.resize(1200, 780)
        self.setMinimumSize(1024, 640)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {ThemeColors.BG_WINDOW};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)

        # Central Widget & Split Layout
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 3-Pane Horizontal QSplitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal, central)
        self.splitter.setObjectName("mainSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {ThemeColors.BORDER_SUBTLE};
            }}
        """)

        # 1. Left pane: Navigation Sidebar
        self.sidebar = NavigationSidebar(self.splitter)
        self.splitter.addWidget(self.sidebar)

        # 2. Center pane: WorkStreamArea (BreadcrumbHeaderBar + ChatStreamView + AgentPromptDock)
        self.work_stream = WorkStreamArea(self.splitter)
        self.splitter.addWidget(self.work_stream)

        # 3. Right pane: InspectorPanel
        self.inspector = InspectorPanel(self.splitter)
        self.splitter.addWidget(self.inspector)

        # Splitter sizing constraints: [260, 640, 300]
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([260, 640, 300])

        main_layout.addWidget(self.splitter)

        # Compatibility aliases for legacy callers
        self.chat_stream = self.work_stream.chat_stream
        self.footer_dock = self.work_stream.prompt_dock

        # Keyboard shortcuts
        self.shortcut_sidebar = QShortcut(QKeySequence("Ctrl+B"), self)
        self.shortcut_sidebar.activated.connect(self.toggle_sidebar)

        self.shortcut_inspector = QShortcut(QKeySequence("Ctrl+Shift+I"), self)
        self.shortcut_inspector.activated.connect(self.toggle_inspector)

    def toggle_sidebar(self) -> None:
        """Toggles sidebar visibility, caching and restoring previous width."""
        if self.sidebar.isVisible():
            self._sidebar_cached_width = max(self.sidebar.width(), 200)
            self.sidebar.setVisible(False)
        else:
            self.sidebar.setVisible(True)
            sizes = self.splitter.sizes()
            sizes[0] = self._sidebar_cached_width
            self.splitter.setSizes(sizes)

    def toggle_inspector(self) -> None:
        """Toggles inspector visibility, caching and restoring previous width."""
        if self.inspector.isVisible():
            self._inspector_cached_width = max(self.inspector.width(), 240)
            self.inspector.setVisible(False)
        else:
            self.inspector.setVisible(True)
            sizes = self.splitter.sizes()
            sizes[2] = self._inspector_cached_width
            self.splitter.setSizes(sizes)

    def _connect_signals(self) -> None:
        # Sidebar Signals
        self.sidebar.new_session_requested.connect(self.create_new_session)
        self.sidebar.session_selected.connect(self.switch_session)
        self.sidebar.session_rename_requested.connect(self.rename_session)
        self.sidebar.session_delete_requested.connect(self.delete_session)
        self.sidebar.open_settings_requested.connect(self.open_settings)
        self.sidebar.sidebar_collapse_requested.connect(self.toggle_sidebar)

        # Inspector Signals
        self.inspector.header.collapse_requested.connect(self.toggle_inspector)

        # WorkStreamArea Signals
        self.work_stream.submit_requested.connect(self.handle_submit_request)
        self.work_stream.clear_history_requested.connect(self.clear_current_history)
        self.work_stream.queue_action.connect(self._on_queue_action)

        # ChatStream Signals (under work_stream.chat_stream)
        self.chat_stream.refine_requested.connect(self.handle_refine_request)
        self.chat_stream.zoom_requested.connect(self.open_image_viewer)
        self.chat_stream.retry_requested.connect(self.handle_retry_request)
        self.chat_stream.starter_prompt_selected.connect(self.handle_starter_prompt)

        # FooterDock / AgentPromptDock plugin changed
        if hasattr(self.footer_dock, "plugin_changed"):
            self.footer_dock.plugin_changed.connect(self.handle_plugin_changed)

        # UIStateManager Signals
        self.state_manager.session_in_flight_changed.connect(self._on_session_in_flight_changed)
        self.state_manager.queued_prompts_changed.connect(self._on_queued_prompts_changed)

        # EventBusQtBridge Signals
        self.event_bridge.subagent_lifecycle_changed.connect(self._on_subagent_lifecycle)
        self.event_bridge.task_status_changed.connect(self._on_task_status_changed)
        self.event_bridge.task_output_received.connect(self._on_task_output_received)
        self.event_bridge.skill_activated.connect(self._on_skill_activated)
        self.event_bridge.files_changed_updated.connect(self._on_files_changed)

    # ------------------------------------------------------------------
    # EventBusQtBridge Handlers
    # ------------------------------------------------------------------

    def _on_subagent_lifecycle(self, subagent_id: str, state: str, detail: str) -> None:
        """Handles subagent lifecycle updates for inspector and work stream running banner."""
        self.inspector.update_subagent(subagent_id, subagent_id, state, detail)

        st = state.lower()
        if st in ("running", "active", "in_progress", "working"):
            self._active_subagents[subagent_id] = (subagent_id, detail or subagent_id)
            if hasattr(self, "work_stream") and self.work_stream:
                self.work_stream.add_subagent_notice(
                    message=f"Subagent '{subagent_id}' is running: {detail}",
                    badge="Subagent",
                )
        else:
            self._active_subagents.pop(subagent_id, None)
            if st in ("done", "completed"):
                if hasattr(self, "work_stream") and self.work_stream:
                    self.work_stream.add_subagent_notice(
                        message=f"Subagent '{subagent_id}' completed work: {detail}",
                        badge="Subagent Completed",
                    )

        self.work_stream.prompt_dock.set_running_subagents(list(self._active_subagents.values()))

    def _on_task_status_changed(self, task_id: str, status: str, summary: str) -> None:
        """Handles background task status changes for inspector panel."""
        if task_id not in self._active_tasks:
            self._active_tasks[task_id] = {"id": task_id, "name": task_id, "output": ""}
        self._active_tasks[task_id]["status"] = status
        self._active_tasks[task_id]["elapsed"] = summary or status
        self.inspector.update_background_tasks(list(self._active_tasks.values()))

    def _on_task_output_received(self, task_id: str, chunk: str) -> None:
        """Handles background task incremental stdout/stderr output."""
        if task_id not in self._active_tasks:
            self._active_tasks[task_id] = {
                "id": task_id,
                "name": task_id,
                "status": "running",
                "elapsed": "Running...",
                "output": "",
            }
        prev_output = self._active_tasks[task_id].get("output", "")
        self._active_tasks[task_id]["output"] = (prev_output + chunk)[-4000:]
        last_line = chunk.strip().splitlines()[-1] if chunk.strip() else ""
        if last_line:
            self._active_tasks[task_id]["elapsed"] = last_line[:30]
        self.inspector.update_background_tasks(list(self._active_tasks.values()))

    def _on_skill_activated(self, skill_name: str, skill_path: str) -> None:
        """Handles skill activation events for inspector skills accordion."""
        if (skill_name, skill_path) not in self._skills_used:
            self._skills_used.append((skill_name, skill_path))
            self.inspector.update_skills_used(self._skills_used)

    def _on_files_changed(self, files: list) -> None:
        """Handles changed files telemetry for inspector files accordion."""
        if not hasattr(self, "_changed_files_list"):
            self._changed_files_list = []
        file_map = {f.get("path"): f for f in self._changed_files_list if isinstance(f, dict)}
        for f in files:
            if isinstance(f, dict) and "path" in f:
                file_map[f["path"]] = f
        self._changed_files_list = list(file_map.values())
        self.inspector.update_files_changed(self._changed_files_list)

    def _on_worker_step_done(self, session_id: str, message: str) -> None:
        """Appends step elapsed pills or status notices to chat stream."""
        if self.state_manager.active_session_id == session_id and message:
            if any(k in message for k in ("正在执行工具:", "Worked for", "Layer")):
                self.work_stream.add_step_elapsed_pill(text=message, details="")

    # ------------------------------------------------------------------
    # Prompt Queue Handlers
    # ------------------------------------------------------------------

    def _on_session_in_flight_changed(self, session_id: str, is_in_flight: bool) -> None:
        """Notifies sidebar and auto-dispatches queued prompts when session turns idle."""
        self.sidebar.set_in_flight(session_id, is_in_flight)
        if not is_in_flight and session_id == self.state_manager.active_session_id:
            queued = self.state_manager.get_queued_prompts(session_id)
            if queued:
                next_prompt = self.state_manager.pop_queued_prompt(session_id)
                self._sync_queue_widget(session_id)
                if next_prompt:
                    session = self.session_store.get_session(session_id)
                    p_state = session.plugin_state if session else {}
                    self.handle_submit_request(next_prompt, "", p_state)

    def _on_queued_prompts_changed(self, session_id: str, prompts: list) -> None:
        """Updates queued messages widget for active session."""
        if self.state_manager.active_session_id == session_id:
            self.work_stream.prompt_dock.set_queued_messages(prompts)

    def _sync_queue_widget(self, session_id: Optional[str] = None) -> None:
        """Refreshes queued messages widget from UIStateManager."""
        active_id = self.state_manager.active_session_id
        sid = session_id or active_id
        if sid and sid == active_id:
            prompts = self.state_manager.get_queued_prompts(active_id)
            self.work_stream.prompt_dock.set_queued_messages(prompts)

    def _on_queue_action(self, action: str, idx: int) -> None:
        """Handles queue item actions (delete, edit, send-now)."""
        active_id = self.state_manager.active_session_id
        if not active_id:
            return
        queued = self.state_manager.get_queued_prompts(active_id)
        if idx < 0 or idx >= len(queued):
            return

        if action == "delete":
            self.state_manager.remove_queued_prompt(active_id, idx)
            self._sync_queue_widget(active_id)
        elif action == "edit":
            prompt = queued[idx]
            self.state_manager.remove_queued_prompt(active_id, idx)
            self._sync_queue_widget(active_id)
            self.work_stream.prompt_dock.set_prompt_text(prompt)
        elif action in ("send_now", "send-now"):
            prompt = queued[idx]
            self.state_manager.remove_queued_prompt(active_id, idx)
            self._sync_queue_widget(active_id)
            session = self.session_store.get_session(active_id)
            p_state = session.plugin_state if session else {}
            self.handle_submit_request(prompt, "", p_state, force=True)

    def handle_starter_prompt(self, prompt: str) -> None:
        """Handles user clicking an empty-state quick start workflow."""
        if any(kw in prompt for kw in ("磨皮", "显瘦", "写真", "塑形", "质感")):
            if not getattr(self.footer_dock, "active_plugin_id", None):
                self.footer_dock.load_plugin("draw")
        self.footer_dock.set_prompt_text(prompt)

    def _bootstrap_sessions(self) -> None:
        """Loads sessions from SessionStore or creates initial session."""
        sessions = self.session_store.list_sessions()
        if not sessions:
            init_session = self._create_empty_session_record(title="新对话")
            self.session_store.create_session(init_session)
            sessions = [init_session]

        for s in sessions:
            self.state_manager.cache_session(s)

        # Set first session as active
        active_session = sessions[0]
        self.sidebar.set_sessions(sessions, active_session_id=active_session.session_id)
        self.switch_session(active_session.session_id)

    def _create_empty_session_record(self, title: str = "新对话") -> SessionRecord:
        now = time.time()
        return SessionRecord(
            session_id=str(uuid.uuid4()),
            title=title,
            workspace_name="ATBMind",
            is_pinned=False,
            active_plugin_id=None,
            plugin_state={},
            created_at=now,
            updated_at=now,
        )

    # ------------------------------------------------------------------
    # Session Management Actions
    # ------------------------------------------------------------------

    def create_new_session(self) -> SessionRecord:
        """Creates and switches to a fresh session."""
        new_record = self._create_empty_session_record(title="新对话")
        self.session_store.create_session(new_record)
        self.state_manager.cache_session(new_record)
        self.sidebar.add_session(new_record, select=True)
        self.switch_session(new_record.session_id)
        if hasattr(self.footer_dock, "text_edit"):
            self.footer_dock.text_edit.setFocus()
        return new_record

    def _get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Fetches session preserving cached metadata like workspace_name and is_pinned."""
        cached = self.state_manager.get_cached_session(session_id)
        store_sess = self.session_store.get_session(session_id)
        if cached and store_sess:
            store_sess.workspace_name = cached.workspace_name
            store_sess.is_pinned = cached.is_pinned
            return store_sess
        return cached or store_sess

    def switch_session(self, session_id: str) -> None:
        """Switches active session and loads messages and plugin parameters."""
        session = self._get_session(session_id)
        if not session:
            return

        self.state_manager.cache_session(session)
        self.state_manager.set_active_session(session_id)
        self.sidebar.select_session(session_id)

        # Update BreadcrumbHeaderBar and ChatStreamView info
        ws_name = getattr(session, "workspace_name", None) or "ATBMind"
        self.work_stream.set_breadcrumb(ws_name, session.title)

        # Restore FooterDock plugin state
        if session.active_plugin_id:
            self.footer_dock.load_plugin(session.active_plugin_id, session.plugin_state)
        else:
            self.footer_dock.unload_plugin()

        # Clear attachment chip for newly switched session
        self.footer_dock.clear_attachment()

        # Sync prompt queue for this session
        self._sync_queue_widget(session_id)

        # Load historical messages
        messages = self.session_store.get_messages(session_id)
        self.chat_stream.load_messages(messages)

    def rename_session(self, session_id: str, new_title: str) -> None:
        """Renames a session in store, sidebar, and breadcrumb header."""
        self.session_store.update_session_title(session_id, new_title)
        session = self._get_session(session_id)
        if session:
            self.state_manager.cache_session(session)
            self.sidebar.update_session(session)
            if self.state_manager.active_session_id == session_id:
                ws_name = getattr(session, "workspace_name", None) or "ATBMind"
                self.work_stream.set_breadcrumb(ws_name, new_title)

    def delete_session(self, session_id: str) -> None:
        """Deletes a session and associated files, cancelling running workers and switching to adjacent session."""
        workers = self._workers.pop(session_id, [])
        for w in workers:
            if hasattr(w, "stop"):
                w.stop()
            elif hasattr(w, "cancel"):
                w.cancel()
            if hasattr(w, "wait"):
                w.wait(500)
        self.state_manager.set_in_flight(session_id, False)

        self.session_store.delete_session(session_id)
        self.state_manager.remove_cached_session(session_id)
        self.sidebar.remove_session(session_id)

        if self.state_manager.active_session_id == session_id:
            remaining = self.session_store.list_sessions()
            if remaining:
                self.switch_session(remaining[0].session_id)
            else:
                self.create_new_session()

    def clear_current_history(self) -> None:
        """Clears messages for current active session and cancels active workers."""
        active_id = self.state_manager.active_session_id
        if active_id:
            workers = self._workers.pop(active_id, [])
            for w in workers:
                if hasattr(w, "stop"):
                    w.stop()
                elif hasattr(w, "cancel"):
                    w.cancel()
            self.state_manager.set_in_flight(active_id, False)
            self.session_store.clear_session_messages(active_id)
            self.chat_stream.clear_messages()

    def _track_worker(self, session_id: str, worker: Any) -> None:
        """Tracks active workers per session and removes them on completion."""
        if session_id not in self._workers:
            self._workers[session_id] = []
        self._workers[session_id].append(worker)

        def _cleanup(*args: Any) -> None:
            active_list = self._workers.get(session_id, [])
            if worker in active_list:
                active_list.remove(worker)

        if hasattr(worker, "finished"):
            worker.finished.connect(_cleanup)
        if hasattr(worker, "title_generated"):
            worker.title_generated.connect(_cleanup)
        if hasattr(worker, "failed"):
            worker.failed.connect(_cleanup)
        if hasattr(worker, "text_finished"):
            worker.text_finished.connect(_cleanup)

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def handle_submit_request(
        self,
        prompt: str,
        attachment_path: Any = "",
        plugin_state: Optional[dict] = None,
        force: bool = False,
    ) -> None:
        """Handles message submission from prompt dock and launches background workers."""
        active_id = self.state_manager.active_session_id
        if not active_id:
            return

        # Adapt payload dict if emitted from WorkStreamArea / AgentPromptDock
        if isinstance(attachment_path, dict) and plugin_state is None:
            payload = attachment_path
            attachment_path = payload.get("attachment_path", "")
            plugin_state = payload.get("plugin_state", {})

        if not attachment_path and hasattr(self.footer_dock, "attachment_path"):
            attachment_path = getattr(self.footer_dock, "attachment_path", "") or ""
        if plugin_state is None and hasattr(self.footer_dock, "plugin_state"):
            plugin_state = getattr(self.footer_dock, "plugin_state", {}) or {}

        # If currently in flight and not forced, queue prompt
        if not force and self.state_manager.is_in_flight(active_id):
            self.state_manager.queue_prompt(active_id, prompt)
            self._sync_queue_widget(active_id)
            return

        now = time.time()
        msg_id = str(uuid.uuid4())
        msg = MessageRecord(
            message_id=msg_id,
            session_id=active_id,
            role="user",
            content=prompt,
            attachment_path=attachment_path or None,
            created_at=now,
        )
        self.session_store.append_message(msg)

        # Render user bubble immediately
        self.chat_stream.add_user_message(prompt, attachment_path=attachment_path or None)

        # Clear attachment chip after submit
        self.footer_dock.clear_attachment()

        # Update session plugin state and updated_at
        active_plugin_id = getattr(self.footer_dock, "active_plugin_id", None)
        if not active_plugin_id:
            sess = self.session_store.get_session(active_id)
            if sess:
                active_plugin_id = sess.active_plugin_id

        self.session_store.update_session_plugin_state(
            active_id,
            active_plugin_id,
            plugin_state,
        )

        session = self.session_store.get_session(active_id)
        if session:
            self.state_manager.cache_session(session)
            self.sidebar.update_session(session)

        # Mark session in-flight immediately
        self.state_manager.set_in_flight(active_id, True)

        # Check for first-turn title generation
        all_msgs = self.session_store.get_messages(active_id)
        user_msgs = [m for m in all_msgs if m.role == "user"]
        if len(user_msgs) == 1 and session and (session.title == "新对话" or not session.title):
            title_worker = TitleWorker(
                session_id=active_id,
                first_prompt=prompt,
                config=self.config,
                parent=self,
            )
            title_worker.title_generated.connect(self._on_title_generated)
            self._track_worker(active_id, title_worker)
            title_worker.start()

        # Launch GenerationWorker
        gen_dir = getattr(
            self.session_store, "generated_images_dir", "data/generated_images"
        )
        worker = GenerationWorker(
            session_id=active_id,
            prompt=prompt,
            attachment_path=attachment_path or None,
            active_plugin_id=active_plugin_id,
            plugin_state=plugin_state,
            config=self.config,
            generated_images_dir=str(gen_dir),
            delay_ms=getattr(self, "_worker_delay_ms", 0),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
            orchestrator=self.orchestrator,
            parent=self,
        )
        worker.progress_updated.connect(self._on_generation_progress)
        worker.progress_updated.connect(lambda msg, sid=active_id: self._on_worker_step_done(sid, msg))
        worker.finished.connect(self._on_generation_finished)
        worker.text_finished.connect(self._on_text_generation_finished)
        worker.failed.connect(self._on_generation_failed)
        worker.sig_ask_question.connect(self._on_ask_question)
        worker.sig_subagent_state.connect(self._on_subagent_lifecycle)
        worker.sig_task_output.connect(self._on_task_output_received)
        worker.sig_task_completed.connect(self._on_task_status_changed)
        self._track_worker(active_id, worker)
        worker.start()

    def _on_ask_question(self, question_data: dict, response_future: Any) -> None:
        """Renders inline QuestionCardItem in chat stream when agent requests user confirmation."""
        self.chat_stream.add_question_card(question_data, response_future)

    def handle_retry_request(self) -> None:
        """Retries last failed request for active session."""
        active_id = self.state_manager.active_session_id
        if not active_id:
            return
        messages = self.session_store.get_messages(active_id)
        user_msgs = [m for m in messages if m.role == "user"]
        if not user_msgs:
            return
        last_user_msg = user_msgs[-1]
        session = self.session_store.get_session(active_id)
        plugin_state = session.plugin_state if session else {}
        self.handle_submit_request(
            prompt=last_user_msg.content,
            attachment_path=last_user_msg.attachment_path or "",
            plugin_state=plugin_state,
        )

    def _on_title_generated(self, session_id: str, new_title: str) -> None:
        """Updates conversation title on main thread."""
        if not self.session_store.get_session(session_id):
            return
        self.rename_session(session_id, new_title)

    def _on_generation_progress(self, session_id: str, message: str) -> None:
        """Progress updates for long-running pipeline execution."""
        pass

    def _on_generation_finished(
        self, session_id: str, report: Any, saved_image_path: str
    ) -> None:
        """Main thread single-writer handler for completed Draw generation."""
        if not self.session_store.get_session(session_id):
            return

        sender = self.sender()
        before_img = getattr(sender, "attachment_path", "") if sender else ""
        if not before_img:
            msgs = self.session_store.get_messages(session_id)
            user_msgs = [m for m in msgs if m.role == "user"]
            if user_msgs and user_msgs[-1].attachment_path:
                before_img = user_msgs[-1].attachment_path

        template_name = "人像精修"
        if hasattr(report, "executed_steps") and report.executed_steps:
            template_name = report.executed_steps[0].name
        elif hasattr(report, "step_results") and report.step_results:
            template_name = getattr(
                report.step_results[0], "step_name", None
            ) or getattr(report, "template_name", "人像精修")

        total_time_ms = getattr(report, "total_execution_time_ms", 0.0)
        elapsed_seconds = float(total_time_ms / 1000.0) if total_time_ms > 0 else 0.1

        plugin_payload = {
            "before_img": str(before_img or ""),
            "after_img": saved_image_path,
            "elapsed_seconds": elapsed_seconds,
            "template_name": template_name,
        }

        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content="",
            plugin_id="draw",
            plugin_payload=plugin_payload,
            created_at=time.time(),
        )
        self.session_store.append_message(msg)
        self.state_manager.set_in_flight(session_id, False)

        if self.state_manager.active_session_id == session_id:
            self.chat_stream.add_plugin_result(plugin_payload)

    def _on_text_generation_finished(self, session_id: str, reply_text: str) -> None:
        """Main thread single-writer handler for plain-text LLM completion."""
        if not self.session_store.get_session(session_id):
            return

        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=reply_text,
            plugin_id=None,
            plugin_payload=None,
            created_at=time.time(),
        )
        self.session_store.append_message(msg)
        self.state_manager.set_in_flight(session_id, False)

        if self.state_manager.active_session_id == session_id:
            self.chat_stream.add_assistant_message(reply_text)

    def _on_generation_failed(self, session_id: str, error_message: str) -> None:
        """Main thread single-writer handler for generation failure."""
        self.state_manager.set_in_flight(session_id, False)

        if self.state_manager.active_session_id == session_id:
            self.chat_stream.add_error_card(error_message)

    def handle_plugin_changed(self, plugin_id: str, plugin_state: dict) -> None:
        """Handles plugin activation/deactivation or parameter changes."""
        active_id = self.state_manager.active_session_id
        if not active_id:
            return

        pid = plugin_id if plugin_id else None
        self.session_store.update_session_plugin_state(active_id, pid, plugin_state)
        self.state_manager.update_plugin_state(active_id, pid, plugin_state)

        session = self._get_session(active_id)
        if session:
            ws_name = getattr(session, "workspace_name", None) or "ATBMind"
            self.work_stream.set_breadcrumb(ws_name, session.title)
            self.sidebar.update_session(session)

    def handle_refine_request(self, image_path: str, prefix: str) -> None:
        """Populates FooterDock with refined image and prefill text."""
        self.footer_dock.set_attachment(image_path)
        self.footer_dock.set_prompt_text(prefix)

    def open_image_viewer(self, image_path: str) -> None:
        """Opens full resolution image modal preview."""
        dialog = ImageViewerDialog(image_path, self)
        dialog.exec()

    def open_settings(self) -> None:
        """Opens global settings dialog."""
        dialog = SettingsDialog(self, config=self.config)
        dialog.config_updated.connect(self._on_config_updated)
        dialog.exec()

    def _on_config_updated(self, new_config: AppConfig) -> None:
        self.config = new_config

    def closeEvent(self, event) -> None:
        """Ensures clean shutdown of all background workers before closing."""
        for workers in list(self._workers.values()):
            for w in list(workers):
                if hasattr(w, "stop"):
                    w.stop()
                elif hasattr(w, "cancel"):
                    w.cancel()
                if hasattr(w, "wait"):
                    w.wait(1000)
        super().closeEvent(event)
