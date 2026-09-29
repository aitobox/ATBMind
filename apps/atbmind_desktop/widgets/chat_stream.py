"""
ATBMind ChatStreamView
Central scrollable conversation stream supporting user bubbles with thumbnails,
assistant text bubbles, plugin result cards, and inline error cards with auto-scrolling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.plugins.schemas import MessageRecord
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog
from plugins.draw.ui.draw_card import DrawResultCard

# Alias for backwards compatibility
DrawResultCardItem = DrawResultCard


class UserMessageItem(QFrame):
    """Right-aligned user message bubble with optional top thumbnail chip."""

    zoom_requested = Signal(str)

    def __init__(
        self,
        content: str,
        attachment_path: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.content = content
        self.attachment_path = attachment_path
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("background: transparent; border: none;")
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(16, 6, 16, 6)
        outer_layout.addStretch(1)

        bubble_container = QWidget()
        bubble_layout = QVBoxLayout(bubble_container)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        bubble_layout.setSpacing(6)
        bubble_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Optional thumbnail chip
        if self.attachment_path and Path(self.attachment_path).exists():
            thumb_btn = QPushButton()
            thumb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #d2d2d7;
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-size: 11px;
                    color: #1d1d1f;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #f5f5f7;
                    border-color: #0071e3;
                }
            """)
            thumb_btn.setText(f"📎 {Path(self.attachment_path).name} (🔍 预览)")
            thumb_btn.clicked.connect(lambda: self.zoom_requested.emit(self.attachment_path))
            bubble_layout.addWidget(thumb_btn, 0, Qt.AlignmentFlag.AlignRight)

        # Bubble
        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #0071e3;
                color: #ffffff;
                border-radius: 14px;
                padding: 10px 14px;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
                line-height: 1.4;
            }
        """)
        inner_layout = QVBoxLayout(bubble)
        inner_layout.setContentsMargins(10, 8, 10, 8)
        msg_label = QLabel(self.content)
        msg_label.setWordWrap(True)
        inner_layout.addWidget(msg_label)

        bubble_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        outer_layout.addWidget(bubble_container)


class AssistantTextMessageItem(QFrame):
    """Left-aligned assistant text bubble with thoughts and markdown responses."""

    def __init__(self, content: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.content = content
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("background: transparent; border: none;")
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(16, 6, 16, 6)

        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #f2f2f7;
                color: #1d1d1f;
                border-radius: 14px;
                padding: 10px 14px;
            }
            QLabel {
                color: #1d1d1f;
                font-size: 14px;
                line-height: 1.45;
            }
        """)
        inner_layout = QVBoxLayout(bubble)
        inner_layout.setContentsMargins(12, 10, 12, 10)
        msg_label = QLabel(self.content)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner_layout.addWidget(msg_label)

        outer_layout.addWidget(bubble)
        outer_layout.addStretch(1)




class ErrorResultCard(QFrame):
    """Inline soft red failure card with retry trigger."""

    retry_requested = Signal()

    def __init__(self, error_message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.error_message = error_message
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            ErrorResultCard {
                background-color: #fff2f2;
                border: 1px solid #ffcdd2;
                border-radius: 10px;
                margin: 6px 16px;
            }
            QLabel {
                color: #d32f2f;
                font-size: 13px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #ffcdd2;
                color: #d32f2f;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ffebee;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        err_label = QLabel(f"⚠️ {self.error_message}")
        err_label.setWordWrap(True)
        layout.addWidget(err_label, 1)

        retry_btn = QPushButton("↺ 重试")
        retry_btn.clicked.connect(self.retry_requested.emit)
        layout.addWidget(retry_btn)


class ChatHeaderBar(QWidget):
    """Header bar of ChatStreamView showing session title and plugin badge."""

    clear_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setStyleSheet("""
            ChatHeaderBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e5ea;
            }
            QLabel#titleLabel {
                font-size: 15px;
                font-weight: 600;
                color: #1d1d1f;
            }
            QLabel#badgeLabel {
                font-size: 12px;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton#clearBtn {
                background-color: transparent;
                border: none;
                color: #86868b;
                font-size: 13px;
                padding: 4px 8px;
                border-radius: 6px;
            }
            QPushButton#clearBtn:hover {
                background-color: #f2f2f7;
                color: #ff3b30;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self.title_label = QLabel("新对话")
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)

        self.badge_label = QLabel("[💬 通用对话]")
        self.badge_label.setObjectName("badgeLabel")
        self.badge_label.setStyleSheet("background-color: #f2f2f7; color: #86868b;")
        layout.addWidget(self.badge_label)

        layout.addStretch(1)

        self.clear_btn = QPushButton("🗑️ 清空历史")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.clear_btn)

    def set_session_info(self, title: str, active_plugin_id: Optional[str]) -> None:
        self.title_label.setText(title or "新对话")
        if active_plugin_id == "draw":
            self.badge_label.setText("[🎨 ATBDraw: 图像生成]")
            self.badge_label.setStyleSheet("background-color: #e3f2fd; color: #0071e3;")
        else:
            self.badge_label.setText("[💬 通用对话]")
            self.badge_label.setStyleSheet("background-color: #f2f2f7; color: #86868b;")


class ChatStreamView(QWidget):
    """
    Central conversation stream widget.
    """

    clear_history_requested = Signal()
    refine_requested = Signal(str, str)
    zoom_requested = Signal(str)
    retry_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar
        self.header_bar = ChatHeaderBar()
        self.header_bar.clear_requested.connect(self.clear_history_requested.emit)
        layout.addWidget(self.header_bar)

        # Scroll Area for Messages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 12, 0, 12)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch(1)

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, 1)

    def set_session_info(self, title: str, active_plugin_id: Optional[str]) -> None:
        self.header_bar.set_session_info(title, active_plugin_id)

    def add_user_message(self, content: str, attachment_path: Optional[str] = None) -> None:
        item = UserMessageItem(content, attachment_path=attachment_path)
        item.zoom_requested.connect(self.zoom_requested.emit)
        # Insert before bottom stretch
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, item)
        self.scroll_to_bottom()

    def add_assistant_message(self, content: str) -> None:
        item = AssistantTextMessageItem(content)
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, item)
        self.scroll_to_bottom()

    def add_plugin_result(self, payload: Dict[str, Any]) -> None:
        item = DrawResultCardItem(payload)
        item.zoom_requested.connect(self.zoom_requested.emit)
        item.refine_requested.connect(self.refine_requested.emit)
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, item)
        self.scroll_to_bottom()

    def add_error_card(self, error_message: str) -> None:
        item = ErrorResultCard(error_message)
        item.retry_requested.connect(self.retry_requested.emit)
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, item)
        self.scroll_to_bottom()

    def load_messages(self, messages: list[MessageRecord]) -> None:
        self.clear_messages()
        for msg in messages:
            if msg.role == "user":
                self.add_user_message(msg.content, attachment_path=msg.attachment_path)
            elif msg.role == "assistant":
                if msg.plugin_payload:
                    self.add_plugin_result(msg.plugin_payload)
                else:
                    self.add_assistant_message(msg.content)

    def clear_messages(self) -> None:
        while self.messages_layout.count() > 1:
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def scroll_to_bottom(self) -> None:
        # Give Qt event loop a cycle to calculate new layout height
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
