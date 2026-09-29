"""
Tests for Pluggable FooterDock & StylePopover (Issue #35).
Validates dynamic plugin control bar, Doubao-style art styles popover menu,
image attachment chip with thumbnail, auto-resizing text edit, and send/stop states.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPoint, QSize, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QPixmap, QColor
from PySide6.QtWidgets import QApplication

from apps.atbmind_desktop.widgets.style_popover import StylePopover
from apps.atbmind_desktop.widgets.footer_dock import (
    AttachmentChip,
    AutoResizingTextEdit,
    FooterDock,
)
from plugins.draw.plugin import DRAW_UI_STYLES


def test_style_popover_init_and_selection(qtbot):
    popover = StylePopover()
    qtbot.addWidget(popover)

    emitted = []
    popover.style_selected.connect(lambda s_id, s_name: emitted.append((s_id, s_name)))

    assert len(popover.style_buttons) == len(DRAW_UI_STYLES)
    assert popover.get_selected_style() == "portrait"

    # Click cinematic style
    cinematic_btn = popover.style_buttons.get("cinematic")
    assert cinematic_btn is not None
    qtbot.mouseClick(cinematic_btn, Qt.MouseButton.LeftButton)

    assert len(emitted) == 1
    assert emitted[0] == ("cinematic", "电影写真")
    assert popover.get_selected_style() == "cinematic"


def test_style_popover_set_selected_style(qtbot):
    popover = StylePopover()
    qtbot.addWidget(popover)

    popover.set_selected_style("anime")
    assert popover.get_selected_style() == "anime"


def test_attachment_chip_render_and_remove(qtbot, tmp_path):
    img_file = tmp_path / "test_avatar.png"
    pix = QPixmap(100, 100)
    pix.fill(QColor("blue"))
    pix.save(str(img_file))

    chip = AttachmentChip(str(img_file))
    qtbot.addWidget(chip)
    chip.show()

    assert chip.file_path == str(img_file)
    assert chip.thumbnail_label is not None
    assert not chip.thumbnail_label.pixmap().isNull()

    remove_emitted = []
    chip.remove_requested.connect(lambda: remove_emitted.append(True))

    qtbot.mouseClick(chip.del_btn, Qt.MouseButton.LeftButton)
    assert remove_emitted == [True]


def test_attachment_chip_fallback_and_truncation(qtbot):
    long_filename = "/path/to/very_long_file_name_portrait_retouch_enhanced_version.png"
    chip = AttachmentChip(long_filename)
    qtbot.addWidget(chip)
    chip.show()

    assert chip.thumbnail_label.text() == "🖼️"
    assert "..." in chip.name_label.text()


def test_auto_resizing_text_edit(qtbot):
    edit = AutoResizingTextEdit(min_height=40, max_height=120)
    qtbot.addWidget(edit)
    edit.show()

    assert edit.height() == 40

    # Expand text
    edit.setPlainText("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8")
    assert edit.height() > 40
    assert edit.height() <= 120

    # Enter emits submit_pressed
    submit_emitted = []
    edit.submit_pressed.connect(lambda: submit_emitted.append(True))

    event_enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    edit.keyPressEvent(event_enter)
    assert submit_emitted == [True]

    # Shift+Enter does not emit submit_pressed
    event_shift_enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    edit.keyPressEvent(event_shift_enter)
    assert submit_emitted == [True]


def test_footer_dock_plain_and_loaded_modes(qtbot):
    dock = FooterDock()
    qtbot.addWidget(dock)
    dock.show()

    # Plain text mode by default
    assert dock.active_plugin_id is None
    assert dock.load_plugin_btn.isVisible()
    assert not dock.capsule_btn.isVisible()
    assert not dock.model_combo.isVisible()
    assert not dock.ratio_combo.isVisible()
    assert not dock.style_btn.isVisible()
    assert not dock.template_combo.isVisible()

    # Load draw plugin
    plugin_emitted = []
    dock.plugin_changed.connect(lambda p_id, state: plugin_emitted.append((p_id, state)))

    dock.load_plugin("draw", {"model": "Flux.1", "style_id": "guofeng"})
    assert dock.active_plugin_id == "draw"
    assert not dock.load_plugin_btn.isVisible()
    assert dock.capsule_btn.isVisible()
    assert dock.model_combo.isVisible()
    assert dock.ratio_combo.isVisible()
    assert dock.style_btn.isVisible()
    assert dock.template_combo.isVisible()

    state = dock.get_plugin_state()
    assert state["model"] == "Flux.1"
    assert state["style_id"] == "guofeng"
    assert "中国风" in dock.style_btn.text()

    # Unload plugin
    dock.unload_plugin()
    assert dock.active_plugin_id is None
    assert dock.load_plugin_btn.isVisible()
    assert not dock.capsule_btn.isVisible()


def test_footer_dock_attachment_and_submit(qtbot, tmp_path):
    dock = FooterDock()
    qtbot.addWidget(dock)
    dock.show()

    img_file = tmp_path / "portrait.jpg"
    pix = QPixmap(50, 50)
    pix.fill(QColor("red"))
    pix.save(str(img_file))

    # Empty submit ignored
    submit_events = []
    dock.submit_requested.connect(lambda p, a, s: submit_events.append((p, a, s)))
    qtbot.mouseClick(dock.send_btn, Qt.MouseButton.LeftButton)
    assert len(submit_events) == 0

    # Set attachment only (no prompt)
    dock.set_attachment(str(img_file))
    assert dock.get_attachment() == str(img_file)
    assert dock.chip_container.isVisible()

    qtbot.mouseClick(dock.send_btn, Qt.MouseButton.LeftButton)
    assert len(submit_events) == 1
    prompt, att, p_state = submit_events[0]
    assert prompt == ""
    assert att == str(img_file)

    # Submit with prompt
    submit_events.clear()
    dock.set_prompt_text("自然显瘦")
    assert dock.get_prompt_text() == "自然显瘦"

    qtbot.mouseClick(dock.send_btn, Qt.MouseButton.LeftButton)
    assert len(submit_events) == 1
    prompt, att, p_state = submit_events[0]
    assert prompt == "自然显瘦"
    assert dock.get_prompt_text() == ""  # text edit cleared after submit

    # Clear attachment
    dock.clear_attachment()
    assert dock.get_attachment() is None
    assert not dock.chip_container.isVisible()


def test_footer_dock_busy_toggle(qtbot):
    dock = FooterDock()
    qtbot.addWidget(dock)
    dock.show()

    stop_events = []
    dock.stop_requested.connect(lambda: stop_events.append(True))

    assert not dock.is_busy()
    assert dock.send_btn.text() == "↑"

    # Set busy
    dock.set_busy(True)
    assert dock.is_busy()
    assert dock.send_btn.text() == "⏹"

    # Clicking send_btn when busy emits stop_requested
    qtbot.mouseClick(dock.send_btn, Qt.MouseButton.LeftButton)
    assert stop_events == [True]

    # Clear busy
    dock.set_busy(False)
    assert not dock.is_busy()
    assert dock.send_btn.text() == "↑"


def test_footer_dock_style_popover_interaction(qtbot):
    dock = FooterDock()
    qtbot.addWidget(dock)
    dock.show()

    dock.load_plugin("draw")
    assert dock.style_popover is not None

    # Trigger style popover
    qtbot.mouseClick(dock.style_btn, Qt.MouseButton.LeftButton)
    assert dock.style_popover.isVisible()

    # Select style from popover
    oil_btn = dock.style_popover.style_buttons.get("oil_painting")
    assert oil_btn is not None
    qtbot.mouseClick(oil_btn, Qt.MouseButton.LeftButton)

    assert dock.get_plugin_state()["style_id"] == "oil_painting"
    assert "油画" in dock.style_btn.text()
    assert not dock.style_popover.isVisible()


def test_footer_dock_drag_and_drop(qtbot, tmp_path):
    dock = FooterDock()
    qtbot.addWidget(dock)
    dock.show()

    img_file = tmp_path / "drop_test.png"
    img_file.touch()

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(img_file))])

    drop_event = QDropEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    dock.dropEvent(drop_event)
    assert dock.get_attachment() == str(img_file)
    assert dock.chip_container.isVisible()
