"""
Message bubble items for ATBMind conversation stream.
Includes UserMessageItem, AssistantTextMessageItem, ErrorResultCard, and LoadingIndicatorItem.
Adheres to Apple HIG aesthetics and modern AI conversational UI patterns.
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

from apps.atbmind_desktop.theme import (
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
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
        outer_layout.setContentsMargins(20, 6, 20, 6)
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
            thumb_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    border: 1px solid {ThemeColors.BORDER_STRONG};
                    border-radius: 8px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 500;
                    color: {ThemeColors.TEXT_PRIMARY};
                    font-family: {ThemeFonts.FONT_STACK};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {ThemeColors.PRIMARY_LIGHT};
                    border-color: {ThemeColors.PRIMARY};
                    color: {ThemeColors.PRIMARY};
                }}
            """)
            file_name = Path(self.attachment_path).name
            if len(file_name) > 28:
                file_name = file_name[:14] + "..." + file_name[-10:]
            thumb_btn.setText(f"📎 {file_name} (🔍 预览)")
            thumb_btn.clicked.connect(lambda: self.zoom_requested.emit(self.attachment_path))
            bubble_layout.addWidget(thumb_btn, 0, Qt.AlignmentFlag.AlignRight)

        # Message Bubble
        bubble = QFrame()
        bubble.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.PRIMARY};
                border-radius: {ThemeRadii.BUBBLE};
                padding: 10px 16px;
            }}
            QLabel {{
                color: #FFFFFF;
                font-size: 14px;
                line-height: 1.45;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        inner_layout = QVBoxLayout(bubble)
        inner_layout.setContentsMargins(12, 10, 12, 10)
        msg_label = QLabel(self.content)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        outer_layout.setContentsMargins(20, 6, 20, 6)

        bubble = QFrame()
        bubble.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_BUBBLE_ASSISTANT};
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-radius: {ThemeRadii.BUBBLE};
                padding: 10px 16px;
            }}
            QLabel#badge {{
                font-size: 11px;
                font-weight: 600;
                color: {ThemeColors.PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
                padding-bottom: 2px;
            }}
            QLabel#msgText {{
                color: {ThemeColors.TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.5;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        inner_layout = QVBoxLayout(bubble)
        inner_layout.setContentsMargins(14, 10, 14, 10)
        inner_layout.setSpacing(4)

        header_label = QLabel("✦ ATBMind 助手")
        header_label.setObjectName("badge")
        inner_layout.addWidget(header_label)

        self.msg_label = QLabel(self.content)
        self.msg_label.setObjectName("msgText")
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
        self.setStyleSheet(f"""
            ErrorResultCard {{
                background-color: {ThemeColors.ERROR_BG};
                border: 1px solid {ThemeColors.ERROR_BORDER};
                border-radius: 10px;
                margin: 6px 20px;
            }}
            QLabel {{
                color: {ThemeColors.ERROR};
                font-size: 13px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.ERROR_BORDER};
                color: {ThemeColors.ERROR};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.ERROR};
                color: #FFFFFF;
                border-color: {ThemeColors.ERROR};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        err_label = QLabel(f"⚠️ {self.error_message}")
        err_label.setWordWrap(True)
        layout.addWidget(err_label, 1)

        retry_btn = QPushButton("↺ 重试")
        retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        outer_layout.setContentsMargins(20, 6, 20, 6)

        bubble = QFrame()
        bubble.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_BUBBLE_ASSISTANT};
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-radius: {ThemeRadii.BUBBLE};
                padding: 8px 14px;
            }}
            QLabel {{
                color: {ThemeColors.TEXT_MUTED};
                font-size: 13px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        inner_layout = QHBoxLayout(bubble)
        inner_layout.setContentsMargins(12, 6, 12, 6)
        inner_layout.setSpacing(8)

        self.label = QLabel(f"✦ {self._message}")
        inner_layout.addWidget(self.label)

        outer_layout.addWidget(bubble)
        outer_layout.addStretch(1)

    def text(self) -> str:
        return self._message

    def set_text(self, text: str) -> None:
        self._message = text
        self.label.setText(f"✦ {text}")
