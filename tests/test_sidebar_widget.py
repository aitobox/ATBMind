"""
Unit & Integration Tests for ATBMind SidebarWidget (Issue #33).
Validates Apple HIG styling, session creation, selection, context menu,
in-flight loading spinners, and settings action.
"""

from __future__ import annotations

import time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox

from atbmind_core.storage.schemas import SessionRecord
from apps.atbmind_desktop.widgets.sidebar import (
    LoadingSpinner,
    SessionItemWidget,
    SidebarWidget,
)


@pytest.fixture
def sample_sessions():
    now = time.time()
    s1 = SessionRecord(
        session_id="session-draw-1",
        title="AI Portrait Generation",
        active_plugin_id="draw",
        plugin_state={"model": "Flux.1", "style_id": "portrait"},
        created_at=now - 3600,
        updated_at=now - 1800,
    )
    s2 = SessionRecord(
        session_id="session-chat-2",
        title="General Chat Discussion",
        active_plugin_id=None,
        plugin_state={},
        created_at=now - 7200,
        updated_at=now - 600,
    )
    return [s1, s2]


def test_loading_spinner_component(qtbot):
    spinner = LoadingSpinner()
    qtbot.addWidget(spinner)
    assert not spinner.is_spinning()

    spinner.start()
    assert spinner.is_spinning()

    spinner.stop()
    assert not spinner.is_spinning()


def test_sidebar_render_and_dimensions(qtbot):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    assert sidebar.width() == 250 or sidebar.maximumWidth() == 250
    assert hasattr(sidebar, "new_btn")
    assert hasattr(sidebar, "settings_btn")
    assert hasattr(sidebar, "list_widget")


def test_sidebar_new_session_action(qtbot):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    signals_emitted = []
    sidebar.new_session_requested.connect(lambda: signals_emitted.append(True))

    # Click + 新对话 button
    qtbot.mouseClick(sidebar.new_btn, Qt.MouseButton.LeftButton)
    assert len(signals_emitted) == 1


def test_sidebar_session_selection(qtbot, sample_sessions):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    selected_ids = []
    sidebar.session_selected.connect(selected_ids.append)

    sidebar.set_sessions(sample_sessions, active_session_id="session-draw-1")
    assert sidebar.list_widget.count() == 2

    # Click the second session
    item2 = sidebar._session_items["session-chat-2"]
    sidebar.list_widget.itemClicked.emit(item2)
    assert selected_ids == ["session-chat-2"]


def test_sidebar_in_flight_spinner(qtbot, sample_sessions):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    sidebar.set_sessions(sample_sessions)
    assert not sidebar.is_in_flight("session-draw-1")

    # Set in-flight
    sidebar.set_in_flight("session-draw-1", True)
    assert sidebar.is_in_flight("session-draw-1") is True

    # Retrieve widget and check spinner
    item = sidebar._session_items["session-draw-1"]
    row_widget = sidebar.list_widget.itemWidget(item)
    assert isinstance(row_widget, SessionItemWidget)
    assert row_widget.in_flight is True
    if hasattr(row_widget, "spinner") and isinstance(row_widget.spinner, LoadingSpinner):
        assert row_widget.spinner.is_spinning()

    # Turn off in-flight
    sidebar.set_in_flight("session-draw-1", False)
    assert sidebar.is_in_flight("session-draw-1") is False
    assert row_widget.in_flight is False


def test_sidebar_context_menu_actions(qtbot, sample_sessions, monkeypatch):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    sidebar.set_sessions(sample_sessions)

    rename_signals = []
    delete_signals = []
    sidebar.session_rename_requested.connect(lambda sid, title: rename_signals.append((sid, title)))
    sidebar.session_delete_requested.connect(delete_signals.append)

    item = sidebar._session_items["session-draw-1"]
    menu = sidebar.create_context_menu("session-draw-1", item)
    actions = {act.text(): act for act in menu.actions()}

    assert any("重命名" in text for text in actions.keys())
    assert any("删除" in text for text in actions.keys())

    # Test Rename action with monkeypatched QInputDialog
    rename_act = next(act for text, act in actions.items() if "重命名" in text)
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Updated Title", True))
    rename_act.trigger()
    assert rename_signals == [("session-draw-1", "Updated Title")]

    # Test Delete action with monkeypatched QMessageBox
    delete_act = next(act for text, act in actions.items() if "删除" in text)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    delete_act.trigger()
    assert delete_signals == ["session-draw-1"]


def test_sidebar_settings_action(qtbot):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    settings_emitted = []
    sidebar.open_settings_requested.connect(lambda: settings_emitted.append(True))

    qtbot.mouseClick(sidebar.settings_btn, Qt.MouseButton.LeftButton)
    assert len(settings_emitted) == 1
