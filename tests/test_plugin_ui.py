"""
Unit & GUI tests for ATBDraw UI components (DrawResultCard & ImageViewerDialog).
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QPushButton
import pytest

from plugins.draw.ui.draw_card import DrawResultCard
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog


@pytest.fixture
def sample_images(tmp_path: Path):
    """Generates two test images for Before and After comparison."""
    before_file = tmp_path / "before.png"
    after_file = tmp_path / "after.png"

    img1 = QImage(120, 120, QImage.Format.Format_RGB32)
    img1.fill(QColor("blue"))
    img1.save(str(before_file))

    img2 = QImage(120, 120, QImage.Format.Format_RGB32)
    img2.fill(QColor("green"))
    img2.save(str(after_file))

    return str(before_file), str(after_file)


def test_draw_result_card_render_and_metadata(qtbot, sample_images):
    before_path, after_path = sample_images
    payload = {
        "before_img": before_path,
        "after_img": after_path,
        "elapsed_seconds": 2.45,
        "template_name": "双频原生磨皮",
    }

    card = DrawResultCard(payload)
    qtbot.addWidget(card)
    card.show()

    # Verify metadata labels
    assert "双频原生磨皮" in card.badge.text()
    assert "2.5s" in card.time_label.text()

    # Verify buttons exist
    assert card.zoom_btn is not None
    assert card.save_btn is not None
    assert card.refine_btn is not None


def test_draw_result_card_signals(qtbot, sample_images):
    before_path, after_path = sample_images
    payload = {
        "before_img": before_path,
        "after_img": after_path,
        "elapsed_seconds": 1.2,
        "template_name": "全身塑形",
    }

    card = DrawResultCard(payload)
    qtbot.addWidget(card)
    card.show()

    # 1. Test zoom_requested signal
    with qtbot.waitSignal(card.zoom_requested, timeout=1000) as blocker:
        qtbot.mouseClick(card.zoom_btn, Qt.MouseButton.LeftButton)
    assert blocker.args == [after_path]

    # 2. Test refine_requested signal
    with qtbot.waitSignal(card.refine_requested, timeout=1000) as blocker:
        qtbot.mouseClick(card.refine_btn, Qt.MouseButton.LeftButton)
    assert blocker.args == [after_path, "在此基础上："]

    # 3. Test save_requested signal
    with qtbot.waitSignal(card.save_requested, timeout=1000) as blocker:
        card.save_requested.emit(after_path)
    assert blocker.args == [after_path]


def test_draw_result_card_empty_or_missing_images(qtbot):
    card = DrawResultCard({})
    qtbot.addWidget(card)
    card.show()

    assert card.zoom_btn is None
    assert card.save_btn is None
    assert card.refine_btn is None
    assert "人像精修" in card.badge.text()
    assert "0.0s" in card.time_label.text()


def test_image_viewer_dialog_open_and_close_esc(qtbot, sample_images):
    _, after_path = sample_images
    dialog = ImageViewerDialog(after_path)
    qtbot.addWidget(dialog)
    dialog.show()

    assert Path(after_path).name in dialog.title_label.text()
    assert not dialog.image_label.pixmap().isNull()

    # Press Escape key to close dialog
    with qtbot.waitSignal(dialog.finished, timeout=1000):
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)


def test_image_viewer_dialog_close_button(qtbot, sample_images):
    _, after_path = sample_images
    dialog = ImageViewerDialog(after_path)
    qtbot.addWidget(dialog)
    dialog.show()

    # Click close button
    with qtbot.waitSignal(dialog.finished, timeout=1000):
        qtbot.mouseClick(dialog.close_btn, Qt.MouseButton.LeftButton)


def test_image_viewer_dialog_missing_image(qtbot):
    dialog = ImageViewerDialog("/nonexistent/dummy_path.png")
    qtbot.addWidget(dialog)
    dialog.show()

    assert "无法加载图像" in dialog.image_label.text()
