"""
Tests for ATBMindMainWindow 3-Pane QSplitter Assembly & Full Integration (Task 7).
Verifies 3-pane QSplitter layout (NavigationSidebar, WorkStreamArea, InspectorPanel),
sidebar and inspector toggle actions, keyboard shortcuts, EventBusQtBridge signal wiring,
prompt queuing dispatcher, and breadcrumb path synchronization.
"""

from __future__ import annotations

import time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter

from atbmind_core.config import AppConfig
from atbmind_core.storage.schemas import SessionRecord
from atbmind_core.storage.session_store import SessionStore
from apps.atbmind_desktop.main_window import ATBMindMainWindow
from apps.atbmind_desktop.widgets.navigation_sidebar import NavigationSidebar
from apps.atbmind_desktop.widgets.work_stream import WorkStreamArea
from apps.atbmind_desktop.widgets.inspector_panel import InspectorPanel


@pytest.fixture
def in_memory_store(tmp_path):
    return SessionStore(
        db_path=":memory:",
        generated_images_dir=str(tmp_path / "gen_imgs"),
    )


def test_main_window_3_pane_splitter(qtbot, in_memory_store):
    win = ATBMindMainWindow(session_store=in_memory_store, config=AppConfig())
    qtbot.addWidget(win)

    # Verify 3 panes exist in splitter
    assert isinstance(win.splitter, QSplitter)
    assert win.splitter.orientation() == Qt.Orientation.Horizontal
    assert win.splitter.count() == 3
    assert not win.splitter.childrenCollapsible()

    assert isinstance(win.sidebar, NavigationSidebar)
    assert isinstance(win.work_stream, WorkStreamArea)
    assert isinstance(win.inspector, InspectorPanel)

    assert win.sidebar.isVisible()
    assert win.work_stream.isVisible()
    assert win.inspector.isVisible()

    # Toggle sidebar
    win.toggle_sidebar()
    assert not win.sidebar.isVisible()
    win.toggle_sidebar()
    assert win.sidebar.isVisible()

    # Toggle inspector
    win.toggle_inspector()
    assert not win.inspector.isVisible()
    win.toggle_inspector()
    assert win.inspector.isVisible()

    # Breadcrumb syncs with session
    assert win.work_stream.header.get_project_name() == "ATBMind"


def test_main_window_toggle_buttons_and_caching(qtbot, in_memory_store):
    win = ATBMindMainWindow(session_store=in_memory_store, config=AppConfig())
    qtbot.addWidget(win)

    # Toggle via sidebar signal
    win.sidebar.sidebar_collapse_requested.emit()
    assert not win.sidebar.isVisible()
    win.sidebar.sidebar_collapse_requested.emit()
    assert win.sidebar.isVisible()

    # Toggle via inspector header signal
    win.inspector.header.collapse_requested.emit()
    assert not win.inspector.isVisible()
    win.inspector.header.collapse_requested.emit()
    assert win.inspector.isVisible()


def test_breadcrumb_sync_on_session_switch(qtbot, in_memory_store):
    win = ATBMindMainWindow(session_store=in_memory_store, config=AppConfig())
    qtbot.addWidget(win)

    # Create session with custom workspace
    now = time.time()
    custom_session = SessionRecord(
        session_id="custom-sess-1",
        title="Layout Optimization",
        workspace_name="CoreWorkspace",
        active_plugin_id=None,
        plugin_state={},
        created_at=now,
        updated_at=now,
    )
    in_memory_store.create_session(custom_session)
    win.state_manager.cache_session(custom_session)
    win.sidebar.add_session(custom_session, select=True)
    win.switch_session("custom-sess-1")

    assert win.work_stream.header.get_project_name() == "CoreWorkspace"
    assert win.work_stream.header.get_session_title() == "Layout Optimization"


def test_event_bus_bridge_signal_wiring(qtbot, in_memory_store):
    win = ATBMindMainWindow(session_store=in_memory_store, config=AppConfig())
    qtbot.addWidget(win)

    # 1. Subagent lifecycle
    win.event_bridge.emit_subagent_lifecycle("sub-1", "running", "Analyzing diff")
    assert win.inspector.subagent_count() == 1
    assert win.work_stream.prompt_dock.running_banner.isVisible()

    win.event_bridge.emit_subagent_lifecycle("sub-1", "done", "Diff analyzed")
    assert not win.work_stream.prompt_dock.running_banner.isVisible()

    # 2. Background tasks
    win.event_bridge.emit_task_status("task-1", "running", "Building project")
    assert win.inspector.tasks_count() == 1

    # 3. Skills activated
    win.event_bridge.emit_skill_activated("writing-plans", "skills/writing-plans")
    assert win.inspector.skills_count() == 1

    # 4. Files changed
    win.event_bridge.emit_files_changed([
        {"path": "apps/atbmind_desktop/main_window.py", "status": "modified", "insertions": 10, "deletions": 5}
    ])
    assert win.inspector.files_count() == 1


def test_prompt_queuing_and_auto_dispatch(qtbot, in_memory_store):
    win = ATBMindMainWindow(session_store=in_memory_store, config=AppConfig())
    qtbot.addWidget(win)

    sess_id = win.state_manager.active_session_id
    assert sess_id is not None

    # Simulate in-flight state
    win.state_manager.set_in_flight(sess_id, True)

    # Submitting prompt while in flight queues it
    win.handle_submit_request("Queued prompt 1", "", {})
    assert win.state_manager.get_queued_prompts(sess_id) == ["Queued prompt 1"]
    assert win.work_stream.prompt_dock.queued_widget.isVisible()
    assert win.work_stream.prompt_dock.queued_widget.count() == 1

    # Add second queued prompt
    win.handle_submit_request("Queued prompt 2", "", {})
    assert win.state_manager.get_queued_prompts(sess_id) == ["Queued prompt 1", "Queued prompt 2"]
    assert win.work_stream.prompt_dock.queued_widget.count() == 2

    # Queue action: delete index 0
    win.work_stream.prompt_dock.queue_action.emit("delete", 0)
    assert win.state_manager.get_queued_prompts(sess_id) == ["Queued prompt 2"]

    # When worker finishes (in_flight becomes False), queued prompt is popped & submitted automatically
    dispatched = []
    win.handle_submit_request = lambda prompt, att="", ps=None: dispatched.append(prompt)

    win.state_manager.set_in_flight(sess_id, False)
    assert "Queued prompt 2" in dispatched
    assert win.state_manager.get_queued_prompts(sess_id) == []


def test_backwards_compatibility_aliases(qtbot, in_memory_store):
    win = ATBMindMainWindow(session_store=in_memory_store, config=AppConfig())
    qtbot.addWidget(win)

    # chat_stream alias
    assert win.chat_stream is win.work_stream.chat_stream
    # footer_dock alias
    assert win.footer_dock is win.work_stream.prompt_dock
