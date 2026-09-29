"""
Message bubble items for ATBMind conversation stream.
Includes UserMessageItem, AssistantTextMessageItem, ErrorResultCard, and LoadingIndicatorItem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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

        # Message Bubble
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
        self.msg_label = QLabel(self.content)
        self.msg_label.setWordWrap(True)
        self.msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner_layout.addWidget(self.msg_label)

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


class LoadingIndicatorItem(QFrame):
    """Typing/thinking indicator bubble shown while assistant generates responses."""

    def __init__(self, message: str = "正在思考中...", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._message = message
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("background: transparent; border: none;")
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(16, 6, 16, 6)

        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #f2f2f7;
                color: #86868b;
                border-radius: 14px;
                padding: 8px 14px;
            }
            QLabel {
                color: #86868b;
                font-size: 13px;
            }
        """)
        inner_layout = QHBoxLayout(bubble)
        inner_layout.setContentsMargins(10, 6, 10, 6)
        inner_layout.setSpacing(6)

        self.label = QLabel(f"💬 {self._message}")
        inner_layout.addWidget(self.label)

        outer_layout.addWidget(bubble)
        outer_layout.addStretch(1)

    def text(self) -> str:
        return self._message

    def set_text(self, text: str) -> None:
        self._message = text
        self.label.setText(f"💬 {text}")
