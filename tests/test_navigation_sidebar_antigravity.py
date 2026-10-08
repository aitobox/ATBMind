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


def test_navigation_sidebar_size_constraints(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    # Size constraints allow splitter resizing
    assert sidebar.minimumWidth() == 200
    assert sidebar.maximumWidth() == 360
    assert sidebar.sizeHint().width() == 260


def test_navigation_sidebar_pin_update_preserves_active_session_and_folder_states(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    sessions = [
        SessionRecord(session_id="s1", title="Task 1", workspace_name="ATBMind", is_pinned=False),
        SessionRecord(session_id="s2", title="Task 2", workspace_name="ATBMind", is_pinned=False),
    ]
    sidebar.set_sessions(sessions, active_session_id="s2")
    assert sidebar.pinned_count() == 0
    assert sidebar.project_session_count("ATBMind") == 2
    assert sidebar._active_session_id == "s2"

    # Collapse folder ATBMind
    folder = sidebar.projects_tree._folder_sections["ATBMind"]
    folder.set_expanded(False)
    assert not folder._is_expanded

    # Update sessions: toggle s2 to pinned, and omit active_session_id (should retain "s2")
    sessions_updated = [
        SessionRecord(session_id="s1", title="Task 1", workspace_name="ATBMind", is_pinned=False),
        SessionRecord(session_id="s2", title="Task 2", workspace_name="ATBMind", is_pinned=True),
    ]
    sidebar.set_sessions(sessions_updated)

    # Verify counts
    assert sidebar.pinned_count() == 1
    assert sidebar.project_session_count("ATBMind") == 1

    # Verify active session retained
    assert sidebar._active_session_id == "s2"
    assert sidebar.pinned_list._cards["s2"].is_active is True

    # Verify folder expansion state was preserved
    folder_after = sidebar.projects_tree._folder_sections["ATBMind"]
    assert folder_after._is_expanded is False


def test_navigation_sidebar_brand_header_presence(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)
    sidebar.show()
    assert hasattr(sidebar, "brand_header")
    assert not sidebar.brand_header.isHidden()
    assert sidebar.brand_header.isVisible()

