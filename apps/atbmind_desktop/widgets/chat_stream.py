"""
ATBMind ChatStreamView
Central scrollable conversation stream supporting user bubbles with thumbnails,
assistant text bubbles, plugin result cards, inline error cards, and smooth auto-scrolling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.plugins.schemas import MessageRecord
from apps.atbmind_desktop.widgets.message_bubble import (
    AssistantTextMessageItem,
    ErrorResultCard,
    LoadingIndicatorItem,
    UserMessageItem,
)

__all__ = [
    "UserMessageItem",
    "AssistantTextMessageItem",
    "ErrorResultCard",
    "LoadingIndicatorItem",
    "DrawResultCardItem",
    "ChatHeaderBar",
    "ChatStreamView",
]


class DrawResultCardItem(QFrame):
    """
    Dedicated Before/After image comparison result card for ATBDraw results.
    """

    zoom_requested = Signal(str)
    refine_requested = Signal(str, str)  # after_img_path, prompt_prefix

    def __init__(
        self,
        payload: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.payload = payload
        self.before_path = str(payload.get("before_img") or "")
        self.after_path = str(payload.get("after_img") or "")
        self.elapsed = float(payload.get("elapsed_seconds") or 0.0)
        self.plan_summary = str(payload.get("template_name") or "人像精修")
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            DrawResultCardItem {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 12px;
                margin: 6px 16px;
            }
            QLabel {
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton {
                background-color: #f5f5f7;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
                border-color: #0071e3;
            }
            QPushButton#refineBtn {
                background-color: #0071e3;
                color: #ffffff;
                border: none;
                font-weight: 500;
            }
            QPushButton#refineBtn:hover {
                background-color: #0077ed;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Meta Header
        header = QHBoxLayout()
        badge = QLabel(f"🎨 ATBDraw: {self.plan_summary}")
        badge.setStyleSheet("font-weight: bold; color: #0071e3; font-size: 13px;")
        header.addWidget(badge)

        header.addStretch(1)

        time_label = QLabel(f"耗时: {self.elapsed:.1f}s")
        time_label.setStyleSheet("color: #86868b;")
        header.addWidget(time_label)
        layout.addLayout(header)

        # Images Row (Before / After)
        img_row = QHBoxLayout()
        img_row.setSpacing(14)

        # Before Image
        img_row.addWidget(self._create_image_box("原图 (Before)", self.before_path))
        # After Image
        img_row.addWidget(self._create_image_box("精修效果 (After)", self.after_path))

        layout.addLayout(img_row)

        # Action Buttons
        actions_row = QHBoxLayout()
        actions_row.addStretch(1)

        if self.after_path:
            zoom_btn = QPushButton("🔍 放大查看")
            zoom_btn.clicked.connect(lambda: self.zoom_requested.emit(self.after_path))
            actions_row.addWidget(zoom_btn)

            save_btn = QPushButton("💾 另存为")
            save_btn.clicked.connect(self._on_save_as)
            actions_row.addWidget(save_btn)

            refine_btn = QPushButton("↺ 以此结果微调")
            refine_btn.setObjectName("refineBtn")
            refine_btn.clicked.connect(
                lambda: self.refine_requested.emit(self.after_path, "在此基础上：")
            )
            actions_row.addWidget(refine_btn)

        layout.addLayout(actions_row)

    def _create_image_box(self, label_text: str, img_path: str) -> QWidget:
        container = QWidget()
        box_layout = QVBoxLayout(container)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(4)

        cap = QLabel(label_text)
        cap.setStyleSheet("color: #86868b; font-size: 11px;")
        box_layout.addWidget(cap)

        img_label = QLabel()
        img_label.setFixedSize(200, 200)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet("border: 1px solid #e5e5ea; border-radius: 8px; background: #fbfbfd;")

        if img_path and Path(img_path).exists():
            pix = QPixmap(img_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    196, 196,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("图片解析失败")
        else:
            img_label.setText("无对应图像")

        box_layout.addWidget(img_label)
        return container

    def _on_save_as(self) -> None:
        if not self.after_path or not Path(self.after_path).exists():
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "保存图片",
            Path(self.after_path).name,
            "Images (*.png *.jpg *.jpeg)",
        )
        if dest:
            import shutil
            shutil.copy2(self.after_path, dest)


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
            QLineEdit#titleEdit {
                font-size: 14px;
                font-weight: 600;
                color: #1d1d1f;
                border: 1px solid #0071e3;
                border-radius: 4px;
                padding: 2px 6px;
                background: #ffffff;
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

        # Display Label
        self.title_label = EditableTitleLabel("新对话")
        self.title_label.setObjectName("titleLabel")
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
        self.badge_label.setStyleSheet("background-color: #f2f2f7; color: #86868b;")
        layout.addWidget(self.badge_label)

        layout.addStretch(1)

        self.clear_btn = QPushButton("🗑️ 清空历史")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.clear_btn)

    def start_title_edit(self) -> None:
        self.title_edit.setText(self.title_label.text())
        self.title_label.setVisible(False)
        self.title_edit.setVisible(True)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def commit_title_edit(self) -> None:
        if not self.title_edit.isVisible():
            return
        new_title = self.title_edit.text().strip()
        if new_title and new_title != self.title_label.text():
            self.title_label.setText(new_title)
            self.title_changed.emit(new_title)
        self.title_edit.setVisible(False)
        self.title_label.setVisible(True)

    def set_session_info(self, title: str, active_plugin_id: Optional[str]) -> None:
        self.title_label.setText(title or "新对话")
        if self.title_edit.isVisible():
            self.title_edit.setVisible(False)
            self.title_label.setVisible(True)

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
    title_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loading_indicator: Optional[LoadingIndicatorItem] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar
        self.header_bar = ChatHeaderBar()
        self.header_bar.clear_requested.connect(self.clear_history_requested.emit)
        self.header_bar.title_changed.connect(self.title_changed.emit)
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
        self._insert_message_item(item)

    def add_assistant_message(self, content: str) -> None:
        self.remove_loading_indicator()
        item = AssistantTextMessageItem(content)
        self._insert_message_item(item)

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

    def add_loading_indicator(self, text: str = "正在思考中...") -> LoadingIndicatorItem:
        if self._loading_indicator is not None:
            self._loading_indicator.set_text(text)
            return self._loading_indicator

        self._loading_indicator = LoadingIndicatorItem(text)
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, self._loading_indicator)
        self.scroll_to_bottom()
        return self._loading_indicator

    def remove_loading_indicator(self) -> None:
        if self._loading_indicator is not None:
            self.messages_layout.removeWidget(self._loading_indicator)
            self._loading_indicator.deleteLater()
            self._loading_indicator = None

    def has_loading_indicator(self) -> bool:
        return self._loading_indicator is not None

    def _insert_message_item(self, item: QWidget) -> None:
        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, item)
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

    def clear_messages(self) -> None:
        self.remove_loading_indicator()
        while self.messages_layout.count() > 1:
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def scroll_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
