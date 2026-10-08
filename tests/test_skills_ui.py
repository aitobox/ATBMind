"""
Unit and GUI tests for ATBMind Skill Manager Desktop UI.
Verifies NavigationSidebar integration, SkillCard rendering, SkillHubView
filtering and search, and WorkStreamArea view stack switching.
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import pytest

from apps.atbmind_desktop.icons import get_apple_icon
from apps.atbmind_desktop.widgets.navigation_sidebar import NavigationSidebar
from apps.atbmind_desktop.widgets.skill_hub import SkillCard, SkillHubView
from apps.atbmind_desktop.widgets.work_stream import WorkStreamArea
from atbmind_core.skills.schema import Skill, SkillMetadata, SkillSourceInfo
from atbmind_core.storage.schemas import SessionRecord


@pytest.fixture
def sample_skills(tmp_path: Path):
    """Fixture providing a diverse set of test skills for rendering and filtering."""
    dir1 = tmp_path / "code_wizard"
    dir1.mkdir(parents=True, exist_ok=True)
    s1 = Skill(
        metadata=SkillMetadata(
            name="code_wizard",
            description="Intelligent coding assistant for refactoring and debugging",
            version="1.2.0",
            tags=["coding", "python", "developer"],
            author="Dev Team",
            enabled=True,
            bound_roles=["coder_expert"],
        ),
        source=SkillSourceInfo(
            source_type="github",
            repo_url="https://github.com/aitobox/code-wizard.git",
            has_update=True,
        ),
        scope="global",
        skill_dir=str(dir1),
    )

    dir2 = tmp_path / "art_studio"
    dir2.mkdir(parents=True, exist_ok=True)
    s2 = Skill(
        metadata=SkillMetadata(
            name="art_studio",
            description="Creative visual art prompt engineering guidelines",
            version="0.9.5",
            tags=["art", "design", "creative"],
            author="Design Lab",
            enabled=False,
            bound_roles=["designer_role"],
        ),
        source=SkillSourceInfo(
            source_type="scaffold",
            has_update=False,
        ),
        scope="project",
        skill_dir=str(dir2),
    )

    dir3 = tmp_path / "doc_writer"
    dir3.mkdir(parents=True, exist_ok=True)
    s3 = Skill(
        metadata=SkillMetadata(
            name="doc_writer",
            description="Documentation generator and technical writer",
            version="2.0.0",
            tags=["docs", "writing"],
            author="Tech Writer",
            enabled=True,
            bound_roles=[],
        ),
        source=SkillSourceInfo(
            source_type="local",
            has_update=False,
        ),
        scope="global",
        skill_dir=str(dir3),
    )

    return [s1, s2, s3]


def test_navigation_sidebar_skills_button_and_signal(qtbot):
    """Verifies that NavigationSidebar includes the Skills item and emits skills_requested."""
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)
    sidebar.show()

    assert hasattr(sidebar, "btn_skills")
    assert sidebar.btn_skills.text() == "Skills"

    emitted = []
    sidebar.skills_requested.connect(lambda: emitted.append(True))

    sidebar.btn_skills.click()
    assert len(emitted) == 1
    assert sidebar.btn_skills.property("active") is True

    # Selecting a session should reset active status
    s = SessionRecord(session_id="sess_1", title="Test Session", workspace_name="WS")
    sidebar.set_sessions([s])
    sidebar.select_session("sess_1")
    assert sidebar.btn_skills.property("active") is False


def test_skill_card_rendering_and_badges(qtbot, sample_skills):
    """Verifies that SkillCard renders title, badges, description, and update button correctly."""
    s1 = sample_skills[0]  # code_wizard (github, has_update=True, enabled=True)
    card = SkillCard(s1)
    qtbot.addWidget(card)
    card.show()

    assert card.title_label.text() == "code_wizard"
    assert "v1.2.0" in card.version_badge.text()
    assert "GitHub" in card.source_badge.text()
    assert "coding assistant" in card.desc_label.text()
    assert card.enable_switch.isChecked() is True
    assert card.btn_update.isVisible() is True

    # s2 (art_studio, scaffold, has_update=False, enabled=False)
    s2 = sample_skills[1]
    card2 = SkillCard(s2)
    qtbot.addWidget(card2)
    card2.show()

    assert card2.title_label.text() == "art_studio"
    assert card2.enable_switch.isChecked() is False
    assert card2.btn_update.isVisible() is False
    assert "Custom" in card2.source_badge.text()


def test_skill_card_signals(qtbot, sample_skills):
    """Verifies signal emissions for toggle, update, and card click."""
    s1 = sample_skills[0]
    card = SkillCard(s1)
    qtbot.addWidget(card)
    card.show()

    # 1. Toggle switch
    toggled_records = []
    card.skill_toggled.connect(lambda name, enabled: toggled_records.append((name, enabled)))
    card.enable_switch.setChecked(False)
    assert len(toggled_records) == 1
    assert toggled_records[0] == ("code_wizard", False)

    # 2. Update button click
    updates_records = []
    card.update_requested.connect(lambda name: updates_records.append(name))
    card.btn_update.click()
    assert len(updates_records) == 1
    assert updates_records[0] == "code_wizard"

    # 3. Card body click
    clicks = []
    card.card_clicked.connect(lambda name: clicks.append(name))
    # Click card title area
    qtbot.mouseClick(card.title_label, Qt.MouseButton.LeftButton)
    assert len(clicks) == 1
    assert clicks[0] == "code_wizard"


def test_skill_hub_view_search_filtering(qtbot, sample_skills):
    """Verifies real-time search filtering by name, description, and tags."""
    hub = SkillHubView()
    qtbot.addWidget(hub)
    hub.show()
    hub.set_skills(sample_skills)

    assert hub.count() == 3

    # Search by tag
    hub.search_input.setText("python")
    assert hub.count() == 1
    assert "code_wizard" in hub._cards

    # Search by description keyword
    hub.search_input.setText("creative")
    assert hub.count() == 1
    assert "art_studio" in hub._cards

    # Search by name
    hub.search_input.setText("doc")
    assert hub.count() == 1
    assert "doc_writer" in hub._cards

    # Clear search
    hub.search_input.clear()
    assert hub.count() == 3


def test_skill_hub_view_pill_category_filtering(qtbot, sample_skills):
    """Verifies filtering by category pills (all, enabled, updates, project, global)."""
    hub = SkillHubView()
    qtbot.addWidget(hub)
    hub.show()
    hub.set_skills(sample_skills)

    # 1. Enabled filter
    hub.pill_buttons["enabled"].click()
    assert hub.count() == 2  # code_wizard and doc_writer

    # 2. Updates filter
    hub.pill_buttons["updates"].click()
    assert hub.count() == 1  # code_wizard only

    # 3. Project filter
    hub.pill_buttons["project"].click()
    assert hub.count() == 1  # art_studio only

    # 4. Global filter
    hub.pill_buttons["global"].click()
    assert hub.count() == 2  # code_wizard and doc_writer

    # 5. Empty result check and reset button
    hub.search_input.setText("non_existent_skill_xyz")
    assert hub.count() == 0
    assert hub.empty_widget.isVisible() is True

    # Click reset button
    hub.btn_reset_filter.click()
    assert hub.count() == 3
    assert hub.empty_widget.isVisible() is False


def test_skill_hub_view_action_buttons(qtbot):
    """Verifies top action buttons emit their corresponding signals."""
    hub = SkillHubView()
    qtbot.addWidget(hub)
    hub.show()

    new_emitted = []
    import_emitted = []
    updates_emitted = []

    hub.new_skill_requested.connect(lambda: new_emitted.append(True))
    hub.import_requested.connect(lambda: import_emitted.append(True))
    hub.check_updates_requested.connect(lambda: updates_emitted.append(True))

    hub.btn_new.click()
    assert len(new_emitted) == 1

    hub.btn_import.click()
    assert len(import_emitted) == 1

    hub.btn_check_updates.click()
    assert len(updates_emitted) == 1


def test_work_stream_stacked_routing(qtbot):
    """Verifies WorkStreamArea switches properly between ChatStreamView and SkillHubView."""
    area = WorkStreamArea()
    qtbot.addWidget(area)
    area.show()

    assert area.current_view_name() == "chat"
    assert area.dock_container.isVisible() is True

    # Switch to Skills Hub
    area.show_skill_hub_view()
    assert area.current_view_name() == "skills"
    assert area.dock_container.isVisible() is False
    assert area.header.label_path.text() == "ATBMind  /  Skills Hub"

    # Switch back to Chat
    area.show_chat_view()
    assert area.current_view_name() == "chat"
    assert area.dock_container.isVisible() is True
    assert "Skills Hub" not in area.header.label_path.text()


def test_main_window_skills_navigation_integration(qtbot, tmp_path, monkeypatch):
    """Verifies ATBMindMainWindow navigates to SkillHubView on sidebar skills click and back on new session."""
    from apps.atbmind_desktop.main_window import ATBMindMainWindow

    db_file = tmp_path / "test_main.db"
    monkeypatch.setenv("ATBMIND_DB_PATH", str(db_file))

    window = ATBMindMainWindow()
    qtbot.addWidget(window)
    window.show()

    # Initial state is Chat
    assert window.work_stream.current_view_name() == "chat"

    # Click Skills button on sidebar
    window.sidebar.btn_skills.click()
    assert window.work_stream.current_view_name() == "skills"
    assert window.sidebar.btn_skills.property("active") is True

    # Click New Conversation button on sidebar
    window.sidebar.btn_new.click()
    assert window.work_stream.current_view_name() == "chat"
    assert window.sidebar.btn_skills.property("active") is False

    window.close()


def test_skill_check_updates_worker_async(qtbot):
    """Verifies SkillCheckUpdatesWorker executes in background thread and emits finished signal."""
    from apps.atbmind_desktop.workers import SkillCheckUpdatesWorker
    from unittest.mock import MagicMock

    mock_mgr = MagicMock()
    mock_mgr.check_updates.return_value = {"skill_a": True, "skill_b": False}

    worker = SkillCheckUpdatesWorker(skill_manager=mock_mgr)
    results_received = []
    worker.finished.connect(lambda res: results_received.append(res))

    with qtbot.waitSignal(worker.finished, timeout=3000):
        worker.start()

    assert len(results_received) == 1
    assert results_received[0] == {"skill_a": True, "skill_b": False}
    mock_mgr.check_updates.assert_called_once()


def test_skill_hub_view_check_updates_async(qtbot):
    """Verifies SkillHubView.check_updates launches asynchronous worker, disables button, and refreshes on finish."""
    from apps.atbmind_desktop.widgets.skill_hub import SkillHubView
    from unittest.mock import MagicMock

    mock_mgr = MagicMock()
    mock_mgr.list_skills.return_value = []
    mock_mgr.check_updates.return_value = {"skill_x": True}

    hub = SkillHubView(skill_manager=mock_mgr)
    qtbot.addWidget(hub)
    hub.show()

    worker = hub.check_updates()
    assert hub.btn_check_updates.isEnabled() is False
    assert "检查中" in hub.btn_check_updates.text()

    with qtbot.waitSignal(worker.finished, timeout=5000):
        pass

    assert hub.btn_check_updates.isEnabled() is True
    assert "检查更新" in hub.btn_check_updates.text()
    assert "1 个技能" in hub.btn_check_updates.toolTip()


def test_skill_hub_view_esc_key_closes_drawer(qtbot, sample_skills):
    """Verifies that pressing ESC key within SkillHubView dismisses visible drawer."""
    from apps.atbmind_desktop.widgets.skill_hub import SkillHubView
    from unittest.mock import MagicMock

    mock_mgr = MagicMock()
    mock_mgr.list_skills.return_value = sample_skills
    mock_mgr.get_skill.side_effect = lambda name: next((s for s in sample_skills if s.metadata.name == name), None)

    hub = SkillHubView(skill_manager=mock_mgr)
    qtbot.addWidget(hub)
    hub.show()

    # Open drawer
    hub.open_skill_drawer("code_wizard")
    assert hub.drawer.isVisible() is True

    # Press ESC
    qtbot.keyPress(hub, Qt.Key.Key_Escape)
    assert hub.drawer.isVisible() is False
