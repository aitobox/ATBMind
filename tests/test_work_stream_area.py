"""
Unit tests for WorkStreamArea and timeline items (Task 5).
Tests BreadcrumbHeaderBar, StepElapsedPill, CodeChangeBadgeItem,
SubagentNoticeItem, and WorkStreamArea integration.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from apps.atbmind_desktop.widgets.work_stream import (
    BreadcrumbHeaderBar,
    CodeChangeBadgeItem,
    StepElapsedPill,
    SubagentNoticeItem,
    WorkStreamArea,
)


def test_breadcrumb_header_bar(qtbot):
    header = BreadcrumbHeaderBar()
    qtbot.addWidget(header)
    header.set_breadcrumb("ATBMind", "Codex Project Implementation Planning")
    assert "ATBMind" in header.label_path.text()
    assert "Codex Project" in header.label_path.text()
    assert header.get_project_name() == "ATBMind"
    assert "Codex Project Implementation Planning" in header.get_session_title()

    assert not header.btn_open_ide.isVisible()
    with qtbot.waitSignal(header.open_ide_requested, timeout=1000):
        header.btn_open_ide.click()

    with qtbot.waitSignal(header.menu_requested, timeout=1000):
        header.btn_menu.click()

    with qtbot.waitSignal(header.sidebar_toggle_requested, timeout=1000):
        header.btn_toggle_sidebar.click()

    with qtbot.waitSignal(header.inspector_toggle_requested, timeout=1000):
        header.btn_toggle_inspector.click()

    header.set_sidebar_visible(False)
    assert not header.btn_toggle_sidebar.isChecked()
    header.set_sidebar_visible(True)
    assert header.btn_toggle_sidebar.isChecked()

    header.set_inspector_visible(False)
    assert not header.btn_toggle_inspector.isChecked()
    header.set_inspector_visible(True)
    assert header.btn_toggle_inspector.isChecked()


def test_step_elapsed_pill(qtbot):
    pill = StepElapsedPill(text="Worked for 1m", details="Execution log line 1")
    qtbot.addWidget(pill)
    assert "Worked for 1m" in pill.title_label.text()
    assert not pill.details_widget.isVisible()
    assert not pill.is_expanded()

    pill.toggle_expand()
    assert pill.details_widget.isVisible()
    assert pill.is_expanded()

    pill.toggle_expand()
    assert not pill.details_widget.isVisible()
    assert not pill.is_expanded()


def test_code_change_badge(qtbot):
    badge = CodeChangeBadgeItem(summary="1 file changed +23 -0")
    qtbot.addWidget(badge)
    assert "+23 -0" in badge.label.text()

    with qtbot.waitSignal(badge.review_requested, timeout=1000):
        badge.btn_review.click()


def test_subagent_notice_item(qtbot):
    notice = SubagentNoticeItem(
        message="Waiting for Task 1 implementer subagent to complete work and report.",
        badge="Subagent",
    )
    qtbot.addWidget(notice)
    assert "Subagent" in notice.badge_label.text()
    assert "Waiting for Task 1" in notice.message_label.text()

    notice.set_notice("Subagent finished", badge="Done")
    assert "Done" in notice.badge_label.text()
    assert "Subagent finished" in notice.message_label.text()


def test_work_stream_area_integration(qtbot):
    area = WorkStreamArea()
    qtbot.addWidget(area)

    assert area.header is not None
    assert area.chat_stream is not None
    assert area.prompt_dock is not None
    assert area.minimumWidth() == 460

    area.set_breadcrumb("ATBMind", "Session 42")
    assert area.header.get_project_name() == "ATBMind"
    assert area.header.get_session_title() == "Session 42"

    area.prompt_dock.set_prompt_text("Hello from WorkStreamArea")
    assert area.prompt_dock.get_prompt_text() == "Hello from WorkStreamArea"


def test_step_elapsed_pill_interaction(qtbot):
    pill = StepElapsedPill(text="Worked for 30s", details="Compiling modules")
    qtbot.addWidget(pill)

    # Right-click should be ignored and not raise AttributeError or toggle expand
    right_click_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        QPointF(5, 5),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pill.header_widget.mousePressEvent(right_click_event)
    assert not pill.is_expanded()

    # Also test via qtbot mouseClick with RightButton
    qtbot.mouseClick(pill.header_widget, Qt.MouseButton.RightButton)
    assert not pill.is_expanded()

    # Click header widget to toggle expand
    with qtbot.waitSignal(pill.toggled, timeout=1000) as sig:
        qtbot.mouseClick(pill.header_widget, Qt.MouseButton.LeftButton)
    assert sig.args == [True]
    assert pill.is_expanded()

    # Click header widget again to collapse
    with qtbot.waitSignal(pill.toggled, timeout=1000) as sig:
        qtbot.mouseClick(pill.header_widget, Qt.MouseButton.LeftButton)
    assert sig.args == [False]
    assert not pill.is_expanded()

    # Update text and details
    pill.set_text("Worked for 2m")
    assert pill.title_label.text() == "Worked for 2m"
    pill.set_details("All tests passed")
    assert pill.details_label.text() == "All tests passed"


def test_work_stream_area_timeline_items_and_signals(qtbot):
    area = WorkStreamArea()
    qtbot.addWidget(area)

    initial_count = area.chat_stream.message_count()

    # Append timeline items
    pill = area.add_step_elapsed_pill("Worked for 10s", "Step details")
    assert area.chat_stream.message_count() == initial_count + 1
    assert pill.title_label.text() == "Worked for 10s"

    badge = area.add_code_change_badge("2 files changed +45 -3")
    assert area.chat_stream.message_count() == initial_count + 2
    assert "+45 -3" in badge.label.text()

    notice = area.add_subagent_notice("Subagent done", "Done")
    assert area.chat_stream.message_count() == initial_count + 3
    assert "Done" in notice.badge_label.text()

    # Signal forwardings
    with qtbot.waitSignal(area.open_ide_requested, timeout=1000):
        area.header.btn_open_ide.click()

    with qtbot.waitSignal(area.menu_requested, timeout=1000):
        area.header.btn_menu.click()

    with qtbot.waitSignal(area.submit_requested, timeout=1000) as submit_sig:
        area.prompt_dock.input_card.set_prompt_text("Refactor layout")
        area.prompt_dock.input_card.btn_send.click()
    assert submit_sig.args[0] == "Refactor layout"

    with qtbot.waitSignal(area.clear_history_requested, timeout=1000):
        area.chat_stream.clear_history_requested.emit()
