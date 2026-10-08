"""
ATBMind ChatStreamView
Central scrollable conversation stream supporting user bubbles with thumbnails,
assistant text bubbles, plugin result cards, inline error cards, inspiring empty canvas,
and smooth auto-scrolling with Apple HIG aesthetics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.storage.schemas import MessageRecord
from apps.atbmind_desktop.icons import get_apple_icon
from apps.atbmind_desktop.theme import (
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog
from apps.atbmind_desktop.widgets.message_bubble import (
    AssistantTextMessageItem,
    ErrorResultCard,
    LoadingIndicatorItem,
    UserMessageItem,
)
from apps.atbmind_desktop.widgets.draw_card import DrawResultCard
from apps.atbmind_desktop.widgets.question_card import QuestionCardItem

# Alias for backwards compatibility
DrawResultCardItem = DrawResultCard

__all__ = [
    "UserMessageItem",
    "AssistantTextMessageItem",
    "ErrorResultCard",
    "LoadingIndicatorItem",
    "DrawResultCardItem",
    "QuestionCardItem",
    "ChatHeaderBar",
    "ChatStreamView",
    "EmptyStateWidget",
]


class EditableTitleLabel(QLabel):
    """QLabel that triggers editing on double click."""

    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class ChatHeaderBar(QWidget):
    """Header bar of ChatStreamView showing session title and plugin badge."""

    clear_requested = Signal()
    title_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            ChatHeaderBar {{
                background-color: {ThemeColors.BG_CHAT};
                border-bottom: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
            QLabel#titleLabel {{
                font-size: 15px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel#titleLabel:hover {{
                color: {ThemeColors.PRIMARY};
            }}
            QLineEdit#titleEdit {{
                font-size: 14px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1.5px solid {ThemeColors.BORDER_FOCUS};
                border-radius: 6px;
                padding: 3px 8px;
                background: #FFFFFF;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel#badgeLabel {{
                font-size: 11px;
                font-weight: 600;
                border-radius: {ThemeRadii.PILL};
                padding: 3px 10px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#clearBtn {{
                background-color: transparent;
                border: 1px solid transparent;
                color: {ThemeColors.TEXT_MUTED};
                font-size: 12px;
                font-weight: 500;
                padding: 4px 10px;
                border-radius: 6px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#clearBtn:hover {{
                background-color: {ThemeColors.ERROR_BG};
                color: {ThemeColors.ERROR};
                border-color: {ThemeColors.ERROR_BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        # Display Label
        self.title_label = EditableTitleLabel("新对话")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_label.setToolTip("双击以重命名会话")
        self.title_label.double_clicked.connect(self.start_title_edit)
        layout.addWidget(self.title_label)

        # Inline Editor
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("titleEdit")
        self.title_edit.setVisible(False)
        self.title_edit.returnPressed.connect(self.commit_title_edit)
        layout.addWidget(self.title_edit)

        # Plugin Indicator Badge
        self.badge_label = QLabel("[💬 通用对话]")
        self.badge_label.setObjectName("badgeLabel")
        self.badge_label.setStyleSheet(f"background-color: {ThemeColors.BG_INPUT}; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(self.badge_label)

        layout.addStretch(1)

        self.clear_btn = QPushButton("清空历史", self)
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setIcon(get_apple_icon("trash", size=13, color=ThemeColors.TEXT_MUTED, active_color=ThemeColors.ERROR))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.clear_btn)

    def set_session_info(self, title: str, active_plugin_id: Optional[str]) -> None:
        self.title_label.setText(title or "新对话")
        if active_plugin_id == "draw":
            self.badge_label.setText("[🎨 ATBDraw 图像精修]")
            self.badge_label.setStyleSheet(f"""
                background-color: {ThemeColors.PRIMARY_LIGHT};
                color: {ThemeColors.PRIMARY};
                border: 1px solid {ThemeColors.PRIMARY_BORDER};
            """)
        else:
            self.badge_label.setText("[💬 通用对话]")
            self.badge_label.setStyleSheet(f"""
                background-color: {ThemeColors.BG_INPUT};
                color: {ThemeColors.TEXT_MUTED};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
            """)

    def start_title_edit(self) -> None:
        self.title_label.setVisible(False)
        self.title_edit.setText(self.title_label.text())
        self.title_edit.setVisible(True)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def commit_title_edit(self) -> None:
        new_title = self.title_edit.text().strip()
        if new_title:
            self.title_label.setText(new_title)
            self.title_changed.emit(new_title)
        self.title_edit.setVisible(False)
        self.title_label.setVisible(True)


class QuickStartCard(QFrame):
    """Interactive card for empty state inspiring quick workflows."""

    clicked = Signal(str)

    def __init__(self, icon: str, title: str, subtitle: str, prompt: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.prompt = prompt
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QuickStartCard {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 12px;
                padding: 12px;
            }}
            QuickStartCard:hover {{
                border-color: {ThemeColors.PRIMARY};
                background-color: {ThemeColors.PRIMARY_LIGHT};
            }}
            QLabel#cardTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel#cardSub {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        t_lbl = QLabel(f"{icon}  {title}")
        t_lbl.setObjectName("cardTitle")
        layout.addWidget(t_lbl)

        s_lbl = QLabel(subtitle)
        s_lbl.setObjectName("cardSub")
        s_lbl.setWordWrap(True)
        layout.addWidget(s_lbl)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.prompt)
        super().mousePressEvent(event)


class EmptyStateWidget(QWidget):
    """Inspiring empty state canvas shown when a conversation has no messages."""

    quick_action_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Hero Icon & Heading
        hero_icon = QLabel("🧠")
        hero_icon.setStyleSheet("font-size: 38px; background: transparent;")
        hero_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hero_icon)

        title = QLabel("探索灵感，与智能体协同创作")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {ThemeColors.TEXT_PRIMARY};
            font-family: {ThemeFonts.FONT_STACK};
        """)
        layout.addWidget(title)

        subtitle = QLabel("输入您的自然语言想法，或从下方快捷工作流快速开始")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            font-size: 13px;
            color: {ThemeColors.TEXT_MUTED};
            font-family: {ThemeFonts.FONT_STACK};
        """)
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # 2x2 Grid of Quick Actions
        grid = QGridLayout()
        grid.setSpacing(12)

        cards = [
            ("✨", "自然双频磨皮", "保持真实原生肌理，抚平微瑕暗沉", "请帮我对照片进行双频原生磨皮，保持肌肤质感"),
            ("👗", "全身显瘦塑形", "黄金比例身材微调，衣物背景防畸变", "请将人像进行自然全身显瘦塑形，注意保持背景衣服不变形"),
            ("📷", "电影写真打光", "强化面部立体光影，营造电影级写实质感", "请为人物面部增添电影质感光影，提升立体感"),
            ("💡", "通用创作助手", "向全能 AI 提问或探讨任何灵感构想", "你好，请问你可以帮我完成哪些修图或创作工作？"),
        ]

        for i, (icon, c_title, c_sub, prompt) in enumerate(cards):
            card = QuickStartCard(icon, c_title, c_sub, prompt, self)
            card.clicked.connect(self.quick_action_clicked.emit)
            grid.addWidget(card, i // 2, i % 2)

        layout.addLayout(grid)


class ChatStreamView(QWidget):
    """
    Central scrollable conversation stream supporting user bubbles with thumbnails,
    assistant text bubbles, plugin result cards, inline error cards, inspiring empty canvas,
    and smooth auto-scrolling with Apple HIG aesthetics.
    """

    clear_history_requested = Signal()
    refine_requested = Signal(str, str)
    zoom_requested = Signal(str)
    retry_requested = Signal()
    starter_prompt_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loading_indicator: Optional[LoadingIndicatorItem] = None
        self._current_speaker_bubble: Optional[AssistantTextMessageItem] = None
        self._current_speaker_id: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"ChatStreamView {{ background-color: {ThemeColors.BG_CHAT}; }}")
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
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {ThemeColors.BG_CHAT};
            }}
            {SLIM_SCROLLBAR_QSS}
        """)

        self.messages_container = QWidget()
        self.messages_container.setStyleSheet(f"background-color: {ThemeColors.BG_CHAT};")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 16, 0, 16)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch(1)

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, 1)

        # Inspiring Empty State Overlay
        self.empty_state = EmptyStateWidget(self.scroll_area.viewport())
        self.empty_state.quick_action_clicked.connect(self.starter_prompt_selected.emit)
        self.empty_state.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "empty_state") and hasattr(self, "scroll_area"):
            vp_rect = self.scroll_area.viewport().rect()
            self.empty_state.setGeometry(vp_rect)

    def _update_empty_state_visibility(self) -> None:
        if hasattr(self, "empty_state"):
            if self.message_count() == 0:
                self.empty_state.show()
                self.empty_state.raise_()
            else:
                self.empty_state.hide()

    def set_session_info(self, title: str, active_plugin_id: Optional[str]) -> None:
        self.header_bar.set_session_info(title, active_plugin_id)

    def add_user_message(self, content: str, attachment_path: Optional[str] = None) -> None:
        self._current_speaker_bubble = None
        self._current_speaker_id = None
        item = UserMessageItem(content, attachment_path=attachment_path)
        item.zoom_requested.connect(self.zoom_requested.emit)
        self._insert_message_item(item)

    def add_assistant_message(
        self,
        content: str,
        speaker_role_id: Optional[str] = None,
        speaker_name: Optional[str] = None,
        speaker_avatar: Optional[str] = None,
    ) -> AssistantTextMessageItem:
        self.remove_loading_indicator()
        self._current_speaker_bubble = None
        self._current_speaker_id = None
        item = AssistantTextMessageItem(
            content,
            speaker_role_id=speaker_role_id,
            speaker_name=speaker_name,
            speaker_avatar=speaker_avatar,
        )
        self._insert_message_item(item)
        return item

    def append_speaker_delta(
        self,
        speaker_role_id: str,
        speaker_name: str = "",
        delta: str = "",
        speaker_avatar: str = "",
        is_start: bool = False,
        is_end: bool = False,
    ) -> AssistantTextMessageItem:
        self.remove_loading_indicator()

        need_new = (
            self._current_speaker_bubble is None
            or self._current_speaker_id != speaker_role_id
            or (is_start and self._current_speaker_bubble is not None and self._current_speaker_id != speaker_role_id)
        )

        if need_new:
            bubble = AssistantTextMessageItem(
                content=delta,
                speaker_role_id=speaker_role_id,
                speaker_name=speaker_name,
                speaker_avatar=speaker_avatar,
            )
            self._current_speaker_bubble = bubble
            self._current_speaker_id = speaker_role_id
            self._insert_message_item(bubble)
        else:
            assert self._current_speaker_bubble is not None
            self._current_speaker_bubble.append_text(delta)
            self.scroll_to_bottom()

        target_bubble = bubble if need_new else self._current_speaker_bubble

        if is_end:
            self._current_speaker_bubble = None
            self._current_speaker_id = None

        return target_bubble

    def add_plugin_result(self, payload: Dict[str, Any]) -> None:
        self.remove_loading_indicator()
        item = DrawResultCardItem(payload)
        item.zoom_requested.connect(self.zoom_requested.emit)
        item.refine_requested.connect(self.refine_requested.emit)
        self._insert_message_item(item)

    def add_error_card(self, error_message: str) -> None:
        self.remove_loading_indicator()
        item = ErrorResultCard(error_message)
        item.retry_requested.connect(self.retry_requested.emit)
        self._insert_message_item(item)

    def add_question_card(
        self,
        question_data: Dict[str, Any],
        response_future: Optional[Any] = None,
    ) -> QuestionCardItem:
        self.remove_loading_indicator()
        item = QuestionCardItem(question_data=question_data, response_future=response_future)
        self._insert_message_item(item)
        return item

    def add_loading_indicator(self, text: str = "正在思考中...") -> LoadingIndicatorItem:
        if self._loading_indicator is not None:
            self._loading_indicator.set_text(text)
            return self._loading_indicator

        self._loading_indicator = LoadingIndicatorItem(text)
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, self._loading_indicator)
        self._update_empty_state_visibility()
        self.scroll_to_bottom()
        return self._loading_indicator

    def remove_loading_indicator(self) -> None:
        if self._loading_indicator is not None:
            self.messages_layout.removeWidget(self._loading_indicator)
            self._loading_indicator.deleteLater()
            self._loading_indicator = None
            self._update_empty_state_visibility()

    def has_loading_indicator(self) -> bool:
        return self._loading_indicator is not None

    def _insert_message_item(self, item: QWidget) -> None:
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, item)
        self._update_empty_state_visibility()
        self.scroll_to_bottom()

    def message_count(self) -> int:
        """Count of message and card items in the stream."""
        count = 0
        for i in range(self.messages_layout.count()):
            widget = self.messages_layout.itemAt(i).widget()
            if widget and widget is not self._loading_indicator:
                count += 1
        return count

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
        self._update_empty_state_visibility()

    def clear_messages(self) -> None:
        self.remove_loading_indicator()
        self._current_speaker_bubble = None
        self._current_speaker_id = None
        while self.messages_layout.count() > 1:
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._update_empty_state_visibility()

    def scroll_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
