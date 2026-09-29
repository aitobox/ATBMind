"""
ATBMindMainWindow
Assembles SidebarWidget, ChatStreamView, and FooterDock into the unified
desktop platform window, coordinating multi-session persistence and plugin states.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.config import AppConfig, load_config
from atbmind_core.plugins.schemas import MessageRecord, SessionRecord
from atbmind_core.storage.session_store import SessionStore
from apps.atbmind_desktop.state import UIStateManager
from apps.atbmind_desktop.theme import ThemeColors, ThemeFonts
from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView
from apps.atbmind_desktop.widgets.footer_dock import FooterDock
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog
from apps.atbmind_desktop.widgets.sidebar import SidebarWidget
from apps.atbmind_desktop.workers import GenerationWorker, TitleWorker


class ATBMindMainWindow(QMainWindow):
    """
    Primary desktop window for ATBMind.
    Coordinates UIStateManager, SessionStore, and presentation widgets.
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
        self._workers: dict[str, list] = {}
        self._worker_delay_ms: int = 0

        self._init_ui()
        self._connect_signals()
        self._bootstrap_sessions()

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
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left: Navigation Sidebar
        self.sidebar = SidebarWidget()
        main_layout.addWidget(self.sidebar)

        # Right: Chat Container (ChatStreamView + FooterDock)
        right_container = QWidget()
        right_container.setStyleSheet(f"background-color: {ThemeColors.BG_CHAT};")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.chat_stream = ChatStreamView()
        right_layout.addWidget(self.chat_stream, 1)

        self.footer_dock = FooterDock()
        right_layout.addWidget(self.footer_dock)

        main_layout.addWidget(right_container, 1)

    def _connect_signals(self) -> None:
        # Sidebar Signals
        self.sidebar.new_session_requested.connect(self.create_new_session)
        self.sidebar.session_selected.connect(self.switch_session)
        self.sidebar.session_rename_requested.connect(self.rename_session)
        self.sidebar.session_delete_requested.connect(self.delete_session)
        self.sidebar.open_settings_requested.connect(self.open_settings)

        # ChatStream Signals
        self.chat_stream.clear_history_requested.connect(self.clear_current_history)
        self.chat_stream.refine_requested.connect(self.handle_refine_request)
        self.chat_stream.zoom_requested.connect(self.open_image_viewer)
        self.chat_stream.retry_requested.connect(self.handle_retry_request)
        self.chat_stream.starter_prompt_selected.connect(self.handle_starter_prompt)

        # FooterDock Signals
        self.footer_dock.submit_requested.connect(self.handle_submit_request)
        self.footer_dock.plugin_changed.connect(self.handle_plugin_changed)

        # UIStateManager Signals
        self.state_manager.session_in_flight_changed.connect(self.sidebar.set_in_flight)

    def handle_starter_prompt(self, prompt: str) -> None:
        """Handles user clicking an empty-state quick start workflow."""
        if any(kw in prompt for kw in ("磨皮", "显瘦", "写真", "塑形", "质感")):
            if not self.footer_dock.active_plugin_id:
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
        self.footer_dock.text_edit.setFocus()
        return new_record

    def switch_session(self, session_id: str) -> None:
        """Switches active session and loads messages and plugin parameters."""
        session = self.session_store.get_session(session_id)
        if not session:
            return

        self.state_manager.cache_session(session)
        self.state_manager.set_active_session(session_id)
        self.sidebar.select_session(session_id)

        # Update ChatStreamView header
        self.chat_stream.set_session_info(session.title, session.active_plugin_id)

        # Restore FooterDock plugin state
        if session.active_plugin_id:
            self.footer_dock.load_plugin(session.active_plugin_id, session.plugin_state)
        else:
            self.footer_dock.unload_plugin()

        # Clear attachment chip for newly switched session
        self.footer_dock.clear_attachment()

        # Load historical messages
        messages = self.session_store.get_messages(session_id)
        self.chat_stream.load_messages(messages)

    def rename_session(self, session_id: str, new_title: str) -> None:
        """Renames a session in store, sidebar, and chat header."""
        self.session_store.update_session_title(session_id, new_title)
        session = self.session_store.get_session(session_id)
        if session:
            self.state_manager.cache_session(session)
            self.sidebar.update_session(session)
            if self.state_manager.active_session_id == session_id:
                self.chat_stream.set_session_info(new_title, session.active_plugin_id)

    def delete_session(self, session_id: str) -> None:
        """Deletes a session and associated files, cancelling running workers and switching to adjacent session."""
        workers = self._workers.pop(session_id, [])
        for w in workers:
            if hasattr(w, "cancel"):
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
                if hasattr(w, "cancel"):
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
        attachment_path: str,
        plugin_state: dict,
    ) -> None:
        """Handles message submission from FooterDock and launches background workers."""
        active_id = self.state_manager.active_session_id
        if not active_id:
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
        active_plugin_id = self.footer_dock.active_plugin_id
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
            parent=self,
        )
        worker.progress_updated.connect(self._on_generation_progress)
        worker.finished.connect(self._on_generation_finished)
        worker.text_finished.connect(self._on_text_generation_finished)
        worker.failed.connect(self._on_generation_failed)
        self._track_worker(active_id, worker)
        worker.start()

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

        session = self.session_store.get_session(active_id)
        if session:
            self.chat_stream.set_session_info(session.title, pid)
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
                if hasattr(w, "cancel"):
                    w.cancel()
                if hasattr(w, "wait"):
                    w.wait(1000)
        super().closeEvent(event)
