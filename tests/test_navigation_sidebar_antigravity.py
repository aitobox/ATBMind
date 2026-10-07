import pytest
from atbmind_core.storage.schemas import SessionRecord
from apps.atbmind_desktop.widgets.navigation_sidebar import NavigationSidebar


def test_navigation_sidebar_rendering_and_signals(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    sessions = [
        SessionRecord(session_id="s1", title="Pinned Task", workspace_name="ATBMind", is_pinned=True),
        SessionRecord(session_id="s2", title="Project Task", workspace_name="ATBMind", is_pinned=False),
    ]
    sidebar.set_sessions(sessions, active_session_id="s2")

    # Verify Pinned list count is 1 and Projects list has 1 item under ATBMind
    assert sidebar.pinned_count() == 1
    assert sidebar.project_session_count("ATBMind") == 1

    # Verify new session trigger
    with qtbot.waitSignal(sidebar.new_session_requested, timeout=1000):
        sidebar.btn_new.click()

    # Verify collapse trigger
    with qtbot.waitSignal(sidebar.sidebar_collapse_requested, timeout=1000):
        sidebar.btn_toggle.click()


def test_navigation_sidebar_item_selection_and_settings(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    sessions = [
        SessionRecord(session_id="s1", title="Pinned Task", workspace_name="ATBMind", is_pinned=True),
        SessionRecord(session_id="s2", title="Project Task", workspace_name="ATBMind", is_pinned=False),
        SessionRecord(session_id="s3", title="Other Project Task", workspace_name="OtherRepo", is_pinned=False),
    ]
    sidebar.set_sessions(sessions, active_session_id="s1")

    assert sidebar.pinned_count() == 1
    assert sidebar.project_session_count("ATBMind") == 1
    assert sidebar.project_session_count("OtherRepo") == 1

    # Test selecting a session via signal
    with qtbot.waitSignal(sidebar.session_selected, timeout=1000) as sig:
        sidebar.click_session("s2")
    assert sig.args == ["s2"]

    # Test settings signal
    with qtbot.waitSignal(sidebar.open_settings_requested, timeout=1000):
        sidebar.btn_settings.click()


def test_navigation_sidebar_in_flight_and_pin_toggle(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    session1 = SessionRecord(session_id="s1", title="Task 1", workspace_name="ATBMind", is_pinned=False)
    sidebar.set_sessions([session1])

    # Check initial in-flight
    assert not sidebar.is_in_flight("s1")
    sidebar.set_in_flight("s1", True)
    assert sidebar.is_in_flight("s1")

    # Test pin toggling signal
    with qtbot.waitSignal(sidebar.session_pin_toggled, timeout=1000) as sig:
        sidebar.trigger_pin_toggle("s1")
    assert sig.args == ["s1"]


def test_navigation_sidebar_rename_and_delete_triggers(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    session1 = SessionRecord(session_id="s1", title="Old Title", workspace_name="ATBMind", is_pinned=False)
    sidebar.set_sessions([session1])

    # Rename signal
    with qtbot.waitSignal(sidebar.session_rename_requested, timeout=1000) as sig:
        sidebar.trigger_rename("s1", "New Title")
    assert sig.args == ["s1", "New Title"]

    # Delete signal
    with qtbot.waitSignal(sidebar.session_delete_requested, timeout=1000) as sig:
        sidebar.trigger_delete("s1")
    assert sig.args == ["s1"]
