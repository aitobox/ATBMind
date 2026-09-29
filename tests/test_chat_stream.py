"""
Unit tests for ChatStreamView, MessageBubbles, and ErrorResultCard (Issue #34).
"""

from __future__ import annotations

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLineEdit, QPushButton

from atbmind_core.plugins.schemas import MessageRecord
from apps.atbmind_desktop.widgets.message_bubble import (
    AssistantTextMessageItem,
    ErrorResultCard,
    LoadingIndicatorItem,
    UserMessageItem,
)
from apps.atbmind_desktop.widgets.chat_stream import (
    ChatHeaderBar,
    ChatStreamView,
)


@pytest.fixture
def sample_image_path(tmp_path: Path) -> str:
    img_path = tmp_path / "test_thumb.png"
    img = QImage(64, 64, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.blue)
    img.save(str(img_path))
    return str(img_path)


def test_user_message_item_rendering_and_zoom(qtbot, sample_image_path: str):
    item = UserMessageItem("你好，请帮我修图", attachment_path=sample_image_path)
    qtbot.addWidget(item)
    item.show()

    assert item.content == "你好，请帮我修图"
    assert item.attachment_path == sample_image_path

    # Verify thumbnail preview button is present and emits zoom_requested
    thumb_btn = item.findChild(QPushButton)
    assert thumb_btn is not None

    with qtbot.waitSignal(item.zoom_requested, timeout=1000) as blocker:
        qtbot.mouseClick(thumb_btn, Qt.MouseButton.LeftButton)

    assert blocker.args == [sample_image_path]


def test_assistant_text_message_item(qtbot):
    item = AssistantTextMessageItem("这里是 AI 助手的回答，支持换行与解析。")
    qtbot.addWidget(item)
    item.show()

    assert item.content == "这里是 AI 助手的回答，支持换行与解析。"
    # Message label should allow text selection
    msg_label = item.findChild(AssistantTextMessageItem)


def test_error_result_card(qtbot):
    card = ErrorResultCard("连接超时，请检查网络配置")
    qtbot.addWidget(card)
    card.show()

    assert "连接超时" in card.error_message
    retry_btn = card.findChild(QPushButton)
    assert retry_btn is not None
    assert "重试" in retry_btn.text()

    with qtbot.waitSignal(card.retry_requested, timeout=1000) as blocker:
        qtbot.mouseClick(retry_btn, Qt.MouseButton.LeftButton)

    assert blocker.signal_triggered


def test_loading_indicator_item(qtbot):
    loading = LoadingIndicatorItem("正在分析图像结构...")
    qtbot.addWidget(loading)
    loading.show()

    assert "正在分析图像结构..." in loading.text()


def test_chat_header_bar_inline_edit(qtbot):
    header = ChatHeaderBar()
    qtbot.addWidget(header)
    header.show()

    header.set_session_info("默认会话", active_plugin_id="draw")
    assert header.title_label.text() == "默认会话"
    assert "ATBDraw" in header.badge_label.text()

    # Trigger title editing
    with qtbot.waitSignal(header.title_changed, timeout=1000) as blocker:
        header.start_title_edit()
        line_edit = header.findChild(QLineEdit)
        assert line_edit is not None
        assert line_edit.isVisible()
        line_edit.setText("重命名后的会话")
        qtbot.keyClick(line_edit, Qt.Key.Key_Return)

    assert blocker.args == ["重命名后的会话"]
    assert header.title_label.text() == "重命名后的会话"


def test_chat_stream_view_operations(qtbot, sample_image_path: str):
    stream = ChatStreamView()
    qtbot.addWidget(stream)
    stream.show()

    # Add user message
    stream.add_user_message("请帮我处理照片", attachment_path=sample_image_path)
    assert stream.message_count() == 1

    # Add loading indicator
    stream.add_loading_indicator("正在生成人像...")
    assert stream.has_loading_indicator() is True

    # Remove loading indicator
    stream.remove_loading_indicator()
    assert stream.has_loading_indicator() is False

    # Add assistant message
    stream.add_assistant_message("人像处理已完成。")
    assert stream.message_count() == 2

    # Add error card
    with qtbot.waitSignal(stream.retry_requested, timeout=1000) as blocker:
        stream.add_error_card("生成失败：显存不足")
        error_card = stream.findChild(ErrorResultCard)
        assert error_card is not None
        retry_btn = error_card.findChild(QPushButton)
        qtbot.mouseClick(retry_btn, Qt.MouseButton.LeftButton)

    assert blocker.signal_triggered

    # Clear messages
    stream.clear_messages()
    assert stream.message_count() == 0


def test_chat_stream_load_messages(qtbot):
    stream = ChatStreamView()
    qtbot.addWidget(stream)
    stream.show()

    import time
    now = time.time()
    messages = [
        MessageRecord(message_id="m1", session_id="s1", role="user", content="用户问题 1", created_at=now),
        MessageRecord(message_id="m2", session_id="s1", role="assistant", content="助手回答 1", created_at=now + 1),
        MessageRecord(message_id="m3", session_id="s1", role="user", content="用户问题 2", created_at=now + 2),
        MessageRecord(message_id="m4", session_id="s1", role="assistant", content="助手回答 2", created_at=now + 3),
    ]

    stream.load_messages(messages)
    assert stream.message_count() == 4
