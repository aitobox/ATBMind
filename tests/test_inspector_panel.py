"""
Unit tests for InspectorPanel and Accordion framework (Task 6).
Tests AccordionSection, InspectorHeaderBar, and InspectorPanel telemetry and interactions.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from apps.atbmind_desktop.widgets.inspector_panel import (
    AccordionSection,
    InspectorHeaderBar,
    InspectorPanel,
)


def test_accordion_section(qtbot):
    section = AccordionSection(title="Subagents", count=2)
    qtbot.addWidget(section)
    section.show()
    assert section.is_expanded()
    assert "Subagents" in section.header_title.text()
    assert "2" in section.count_badge.text()

    section.toggle_expanded()
    assert not section.is_expanded()

    section.set_expanded(True)
    assert section.is_expanded()

    # Title & count badge updates
    section.set_title("Active Agents", count=5)
    assert "Active Agents" in section.header_title.text()
    assert "5" in section.count_badge.text()
    assert section.count_badge.isVisible()

    section.set_title("No Count Section", count=None)
    assert not section.count_badge.isVisible()

    # Add and clear items
    item1 = QLabel("Item 1")
    item2 = QLabel("Item 2")
    section.add_item(item1)
    section.add_item(item2)
    assert section.item_count() == 2

    section.clear_items()
    assert section.item_count() == 0


def test_accordion_header_click(qtbot):
    section = AccordionSection(title="Files Changed", count=1)
    qtbot.addWidget(section)
    assert section.is_expanded()

    # Click on the header to toggle
    qtbot.mouseClick(section.header, Qt.MouseButton.LeftButton)
    assert not section.is_expanded()

    qtbot.mouseClick(section.header, Qt.MouseButton.LeftButton)
    assert section.is_expanded()


def test_inspector_header_bar(qtbot):
    header = InspectorHeaderBar()
    qtbot.addWidget(header)

    # Test tab change signal
    with qtbot.waitSignal(header.tab_changed, timeout=1000) as blocker:
        header.set_current_tab(1)
    assert blocker.args == [1]

    # Test action button signals
    with qtbot.waitSignal(header.add_requested, timeout=1000):
        header.btn_add.click()

    with qtbot.waitSignal(header.fullscreen_requested, timeout=1000):
        header.btn_fullscreen.click()

    with qtbot.waitSignal(header.collapse_requested, timeout=1000):
        header.btn_collapse.click()


def test_inspector_panel_updates(qtbot):
    panel = InspectorPanel()
    qtbot.addWidget(panel)

    panel.update_subagent("sub1", "Task 1 Reviewer", "running", "Working...")
    panel.update_subagent("sub2", "Task 1 Implementer", "done", "Worked for 6m")
    assert panel.subagent_count() == 2

    # Updating existing subagent updates in place
    panel.update_subagent("sub1", "Task 1 Reviewer", "done", "Finished in 2m")
    assert panel.subagent_count() == 2

    panel.update_skills_used([
        ("subagent-driven-development", "skills/sdd"),
        ("writing-plans", "skills/writing-plans"),
    ])
    assert panel.skills_count() == 2

    with qtbot.waitSignal(panel.header.collapse_requested, timeout=1000):
        panel.header.btn_collapse.click()


def test_inspector_panel_files_and_tasks(qtbot):
    panel = InspectorPanel()
    qtbot.addWidget(panel)

    panel.update_files_changed([
        {
            "path": "apps/atbmind_desktop/widgets/inspector_panel.py",
            "status": "added",
            "insertions": 120,
            "deletions": 0,
        },
        {
            "path": "tests/test_inspector_panel.py",
            "status": "modified",
            "insertions": 45,
            "deletions": 2,
        },
    ])
    assert panel.files_count() == 2

    panel.update_background_tasks([
        {"id": "bg1", "name": "Build daemon", "state": "running"},
        {"id": "bg2", "name": "File watcher", "state": "done"},
    ])
    assert panel.tasks_count() == 2


def test_inspector_panel_dimensions(qtbot):
    panel = InspectorPanel()
    qtbot.addWidget(panel)

    assert panel.minimumWidth() == 240
    assert panel.maximumWidth() == 480
    assert panel.sizeHint().width() == 300


def test_accordion_header_interactions(qtbot):
    section = AccordionSection(title="Terminals", count=0)
    qtbot.addWidget(section)
    assert section.is_expanded()

    # Right-click should not toggle
    qtbot.mouseClick(section.header, Qt.MouseButton.RightButton)
    assert section.is_expanded()

    # Clicking on the title label directly should toggle
    qtbot.mouseClick(section.header_title, Qt.MouseButton.LeftButton)
    assert not section.is_expanded()

    # Clicking on chevron should toggle
    qtbot.mouseClick(section.chevron, Qt.MouseButton.LeftButton)
    assert section.is_expanded()


def test_inspector_panel_tab_filtering_and_telemetry(qtbot):
    panel = InspectorPanel()
    qtbot.addWidget(panel)
    panel.show()

    # Add items to various sections
    panel.update_subagent("sub1", "Reviewer", "running", "Active")
    panel.update_subagent("sub2", "Planner", "failed", "Error")
    panel.update_subagent("sub3", "Worker", "done", "Done")
    assert panel.subagent_count() == 3

    panel.update_artifacts([{"title": "Diff Report", "path": "/path/to/diff"}])
    assert panel.artifacts_count() == 1

    panel.update_uploads([{"name": "screenshot.png"}])
    assert panel.uploads_count() == 1

    panel.update_terminals([{"id": "term1", "name": "zsh"}])
    assert panel.terminals_count() == 1

    # In Context tab (0), all sections should be visible
    assert panel.section_subagents.isVisible()
    assert panel.section_files.isVisible()
    assert panel.section_artifacts.isVisible()

    # Switch to Files tab (1)
    panel.header.set_current_tab(1)
    assert not panel.section_subagents.isVisible()
    assert panel.section_files.isVisible()
    assert not panel.section_artifacts.isVisible()

    # Switch to Artifacts tab (2)
    panel.header.set_current_tab(2)
    assert not panel.section_subagents.isVisible()
    assert not panel.section_files.isVisible()
    assert panel.section_artifacts.isVisible()

    # Switch back to Context tab (0)
    panel.header.set_current_tab(0)
    assert panel.section_subagents.isVisible()
    assert panel.section_files.isVisible()
    assert panel.section_artifacts.isVisible()

