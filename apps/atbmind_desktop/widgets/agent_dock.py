"""
ATBMind AgentPromptDock
Composite Agent Prompt Dock adhering to Apple Human Interface Guidelines
and Google Antigravity desktop layout paradigms.

Comprises:
- Layer 1: QueuedMessagesWidget (pending messages queue with actions [➔], [✎], [🗑])
- Layer 2: SubagentRunningBanner (active subagents telemetry with animated spinners)
- Layer 3: AgentInputCard (16px border-radius container with auto-resizing text edit,
            model selection combobox, voice button, attachment button, and circular send button)
- AgentPromptDock: vertical composite container integrating all three layers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QFocusEvent,
    QKeyEvent,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from apps.atbmind_desktop.theme import (
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)
from apps.atbmind_desktop.widgets.sidebar import LoadingSpinner


class PromptCompleterPopup(QFrame):
    """
    Floating completion popup for slash commands (/) and role mentions (@).
    Apple HIG styled card with clean border, rounded corners, and subtle highlight.
    """

    completion_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("promptCompleterPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self.list_widget = QListWidget(self)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 5px 8px;
                border-radius: 6px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
                font-size: 12px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(0, 122, 255, 0.12);
                color: {ThemeColors.PRIMARY};
                font-weight: 600;
            }}
            QListWidget::item:hover:!selected {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self.setStyleSheet(f"""
            QFrame#promptCompleterPopup {{
                background: transparent;
                border: none;
            }}
        """)
        self._items: list[tuple[str, str, str]] = []

    def set_items(self, items: list[tuple[str, str, str]]) -> None:
        self._items = list(items)
        self.list_widget.clear()
        for token, desc, icon in self._items:
            display_text = f"{icon}  {token}   —   {desc}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, token)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        row_height = 28
        total_h = min(220, max(40, self.list_widget.count() * row_height + 12))
        self.resize(340, total_h)

    def select_next(self) -> None:
        cnt = self.list_widget.count()
        if cnt == 0:
            return
        curr = self.list_widget.currentRow()
        next_row = (curr + 1) % cnt
        self.list_widget.setCurrentRow(next_row)

    def select_prev(self) -> None:
        cnt = self.list_widget.count()
        if cnt == 0:
            return
        curr = self.list_widget.currentRow()
        prev_row = (curr - 1 + cnt) % cnt
        self.list_widget.setCurrentRow(prev_row)

    def get_selected_token(self) -> Optional[str]:
        curr_item = self.list_widget.currentItem()
        if curr_item:
            return curr_item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        token = item.data(Qt.ItemDataRole.UserRole)
        if token:
            self.completion_selected.emit(token)


class AutoResizingAgentTextEdit(QTextEdit):
    """
    Auto-resizing text input for AgentPromptDock.
    Auto-adjusts height between min_height and max_height based on document size.
    Enter sends; Shift+Enter creates a new line.
    Supports '/' slash commands and '@' role mentions auto-completion.
    Emits submit_pressed, file_dropped, and focus_changed signals.
    """

    submit_pressed = Signal()
    file_dropped = Signal(str)
    focus_changed = Signal(bool)

    SLASH_COMMANDS = [
        ("/plan", "详细任务规划与步骤拆解", "📋"),
        ("/goal", "深度长周期自治执行", "🎯"),
        ("/schedule", "定时与后台周期性调度", "⏰"),
        ("/browser", "网页浏览与多模态检索", "🌐"),
        ("/grill-me", "严格方案对齐与推演", "🔥"),
        ("/teamwork-preview", "多智能体团队协作编排", "👥"),
        ("/learn", "沉淀经验到规则库", "💡"),
        ("/boost", "增强多视角深度思考", "🚀"),
    ]

    MENTION_ROLES = [
        ("@coordinator", "任务拆解与编排专家", "🧭"),
        ("@draw_expert", "AI 图像生成与图像处理专家", "🎨"),
        ("@research", "只读文件与代码库调研助手", "🔍"),
        ("@self", "克隆当前智能体上下文与工具", "🤖"),
    ]

    def __init__(
        self,
        min_height: int = 40,
        max_height: int = 140,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.min_height = min_height
        self.max_height = max_height
        self.setAcceptDrops(True)
        self.setPlaceholderText("Ask anything, @ to mention, / for actions")
        self.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                font-size: 14px;
                line-height: 1.4;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
                padding: 4px 6px;
                selection-background-color: rgba(0, 122, 255, 0.25);
            }}
        """)
        self.setFixedHeight(self.min_height)
        self.textChanged.connect(self._adjust_height)

        self.completer_popup = PromptCompleterPopup(self)
        self.completer_popup.completion_selected.connect(self._apply_completion)
        self.textChanged.connect(self._check_completion)

    def _adjust_height(self) -> None:
        doc: QTextDocument = self.document()
        doc_height = int(doc.size().height()) + 14
        new_height = max(self.min_height, min(doc_height, self.max_height))
        if self.height() != new_height:
            self.setFixedHeight(new_height)

    def _get_current_prefix(self) -> tuple[Optional[str], int, int]:
        cursor = self.textCursor()
        pos = cursor.position()
        full_text = self.toPlainText()
        text_before = full_text[:pos]
        if not text_before or text_before[-1].isspace():
            return (None, 0, 0)
        start_idx = max(text_before.rfind(" "), text_before.rfind("\n"), text_before.rfind("\t")) + 1
        word = text_before[start_idx:pos]
        if word.startswith("/") or word.startswith("@"):
            return (word, start_idx, pos)
        return (None, 0, 0)

    def _check_completion(self) -> None:
        prefix, start, end = self._get_current_prefix()
        if not prefix:
            self.completer_popup.hide()
            return

        matches = []
        if prefix.startswith("/"):
            q = prefix.lower()
            matches = [c for c in self.SLASH_COMMANDS if c[0].lower().startswith(q)]
        elif prefix.startswith("@"):
            q = prefix.lower()
            matches = [c for c in self.MENTION_ROLES if c[0].lower().startswith(q)]

        if matches:
            self.completer_popup.set_items(matches)
            cursor_rect = self.cursorRect()
            global_pos = self.mapToGlobal(cursor_rect.bottomLeft())
            pop_h = self.completer_popup.height()
            pop_y = global_pos.y() - pop_h - cursor_rect.height() - 4
            if pop_y < 10:
                pop_y = global_pos.y() + cursor_rect.height() + 4
            self.completer_popup.move(global_pos.x(), pop_y)
            self.completer_popup.show()
        else:
            self.completer_popup.hide()

    def _apply_completion(self, token: str) -> None:
        prefix, start, end = self._get_current_prefix()
        if prefix is not None:
            cursor = self.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(token + " ")
            self.setTextCursor(cursor)
        self.completer_popup.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.completer_popup.isVisible():
            if event.key() == Qt.Key.Key_Up:
                self.completer_popup.select_prev()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Down:
                self.completer_popup.select_next()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                tok = self.completer_popup.get_selected_token()
                if tok:
                    self._apply_completion(tok)
                    event.accept()
                    return
            elif event.key() == Qt.Key.Key_Escape:
                self.completer_popup.hide()
                event.accept()
                return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.submit_pressed.emit()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.completer_popup.hide()
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    self.file_dropped.emit(url.toLocalFile())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class QueuedMessagesWidget(QWidget):
    """
    Layer 1 of AgentPromptDock: Queued Messages List.
    Only visible when 1 or more messages are queued.
    Displays:
    - Header: 'Queued Messages N · Sends after agent finishes working'
    - Rows: pending prompts with actions [➔] (send now), [✎] (edit), [🗑] (delete).
    """

    send_now_requested = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._prompts: list[str] = []

        self.setVisible(False)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.frame = QFrame(self)
        self.frame.setObjectName("queuedMessagesFrame")
        self.frame.setStyleSheet(f"""
            QFrame#queuedMessagesFrame {{
                background-color: #F8F9FA;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 12px;
            }}
        """)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(10, 8, 10, 8)
        self.frame_layout.setSpacing(6)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)

        self.header_label = QLabel(self.frame)
        self.header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_row.addWidget(self.header_label)
        header_row.addStretch(1)

        self.frame_layout.addLayout(header_row)

        # Items container
        self.items_container = QWidget(self.frame)
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(4)

        self.frame_layout.addWidget(self.items_container)
        outer_layout.addWidget(self.frame)

    def count(self) -> int:
        return len(self._prompts)

    def set_queued_messages(self, prompts: list[str]) -> None:
        self._prompts = list(prompts)
        if not self._prompts:
            self._clear_items()
            self.setVisible(False)
            return

        self._rebuild_items()
        self.setVisible(True)

    def trigger_send_now(self, idx: int) -> None:
        if 0 <= idx < len(self._prompts):
            self.send_now_requested.emit(idx)

    def trigger_edit(self, idx: int) -> None:
        if 0 <= idx < len(self._prompts):
            self.edit_requested.emit(idx)

    def trigger_delete(self, idx: int) -> None:
        if 0 <= idx < len(self._prompts):
            self.delete_requested.emit(idx)

    def _clear_items(self) -> None:
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _rebuild_items(self) -> None:
        self._clear_items()
        count = len(self._prompts)
        self.header_label.setText(
            f"⮟ Queued Messages {count} · Sends after agent finishes working"
        )

        for idx, prompt in enumerate(self._prompts):
            row = self._create_item_row(idx, prompt)
            self.items_layout.addWidget(row)

    def _create_item_row(self, idx: int, prompt: str) -> QWidget:
        row_widget = QFrame(self.items_container)
        row_widget.setObjectName(f"queuedItemRow_{idx}")
        row_widget.setStyleSheet(f"""
            QFrame#queuedItemRow_{idx} {{
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.06);
                border-radius: 8px;
            }}
            QFrame#queuedItemRow_{idx}:hover {{
                border-color: rgba(0, 0, 0, 0.12);
                background-color: #FAFAFC;
            }}
        """)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 5, 8, 5)
        row_layout.setSpacing(6)

        # Index badge
        idx_label = QLabel(f"#{idx + 1}")
        idx_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_MONO};
            }}
        """)
        row_layout.addWidget(idx_label)

        # Text label (truncated if long, full text in tooltip)
        clean_text = prompt.replace("\n", " ")
        display_text = clean_text[:80] + "..." if len(clean_text) > 80 else clean_text
        text_label = QLabel(display_text)
        text_label.setToolTip(prompt)
        text_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(text_label, 1)

        # Action Buttons
        btn_send_now = QPushButton("➔")
        btn_send_now.setObjectName(f"btnSendNow_{idx}")
        btn_send_now.setToolTip("Send now (force dispatch)")
        btn_send_now.setFixedSize(22, 22)
        btn_send_now.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send_now.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                color: {ThemeColors.PRIMARY};
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 122, 255, 0.10);
            }}
        """)
        btn_send_now.clicked.connect(lambda _, i=idx: self.trigger_send_now(i))
        row_layout.addWidget(btn_send_now)

        btn_edit = QPushButton("✎")
        btn_edit.setObjectName(f"btnEdit_{idx}")
        btn_edit.setToolTip("Edit queued message")
        btn_edit.setFixedSize(22, 22)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 0, 0, 0.06);
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        btn_edit.clicked.connect(lambda _, i=idx: self.trigger_edit(i))
        row_layout.addWidget(btn_edit)

        btn_del = QPushButton("🗑")
        btn_del.setObjectName(f"btnDelete_{idx}")
        btn_del.setToolTip("Remove from queue")
        btn_del.setFixedSize(22, 22)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.ERROR_BG};
                color: {ThemeColors.ERROR};
            }}
        """)
        btn_del.clicked.connect(lambda _, i=idx: self.trigger_delete(i))
        row_layout.addWidget(btn_del)

        return row_widget


class SubagentRunningBanner(QWidget):
    """
    Layer 2 of AgentPromptDock: Subagents Running Banner.
    Displays active subagents telemetry when 1 or more subagents are running.
    Header: 'N subagent(s) running'
    Items: Animated loading spinners with subagent names.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._subagents: list[tuple[str, str]] = []
        self._spinners: list[LoadingSpinner] = []

        self.setVisible(False)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.frame = QFrame(self)
        self.frame.setObjectName("subagentBannerFrame")
        self.frame.setStyleSheet(f"""
            QFrame#subagentBannerFrame {{
                background-color: #F0F7FF;
                border: 1px solid rgba(0, 122, 255, 0.16);
                border-radius: 10px;
            }}
        """)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(10, 7, 10, 7)
        self.frame_layout.setSpacing(5)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)

        self.header_label = QLabel(self.frame)
        self.header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {ThemeColors.PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_row.addWidget(self.header_label)
        header_row.addStretch(1)

        self.frame_layout.addLayout(header_row)

        # Items container
        self.items_container = QWidget(self.frame)
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(4)

        self.frame_layout.addWidget(self.items_container)
        outer_layout.addWidget(self.frame)

    def count(self) -> int:
        return len(self._subagents)

    def text(self) -> str:
        if not self._subagents:
            return ""
        names = ", ".join(name for _, name in self._subagents)
        return f"{len(self._subagents)} subagent(s) running: {names}"

    def set_running_subagents(self, subagents: list[tuple[str, str]]) -> None:
        self._subagents = list(subagents)
        if not self._subagents:
            self._stop_spinners()
            self._clear_items()
            self.setVisible(False)
            return

        self._rebuild_items()
        self.setVisible(True)

    def _stop_spinners(self) -> None:
        for sp in self._spinners:
            try:
                sp.stop()
            except Exception:
                pass
        self._spinners.clear()

    def _clear_items(self) -> None:
        self._stop_spinners()
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _rebuild_items(self) -> None:
        self._clear_items()
        count = len(self._subagents)
        self.header_label.setText(f"⮟ {count} subagent(s) running")

        for sub_id, sub_name in self._subagents:
            row = self._create_subagent_row(sub_id, sub_name)
            self.items_layout.addWidget(row)

    def _create_subagent_row(self, sub_id: str, sub_name: str) -> QWidget:
        row_widget = QWidget(self.items_container)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(6)

        spinner = LoadingSpinner(row_widget, size=14)
        spinner.start()
        self._spinners.append(spinner)
        row_layout.addWidget(spinner)

        name_label = QLabel(sub_name, row_widget)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(name_label)

        status_label = QLabel("Working...", row_widget)
        status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(status_label)
        row_layout.addStretch(1)

        return row_widget


class AgentInputCard(QWidget):
    """
    Layer 3 of AgentPromptDock: Agent Input Card.
    Features:
    - 16px border-radius container with dynamic focus styling.
    - Auto-resizing text edit with placeholder 'Ask anything, @ to mention, / for actions'.
    - Integrated toolbar:
      - Left: [+] attach button and model combobox dropdown.
      - Right: [🎙] voice dictation button and circular [➔] send button.
    """

    submit_requested = Signal(str, dict)
    attach_requested = Signal()
    voice_requested = Signal()
    file_dropped = Signal(str)

    DEFAULT_MODELS = [
        "Gemini 3.8 Flash High",
        "Gemini 3.8 Pro",
        "Claude 3.7 Sonnet",
        "GPT-4o",
        "DeepSeek V3",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 16px border-radius card frame
        self.card_frame = QFrame(self)
        self.card_frame.setObjectName("agentInputCardFrame")
        self.card_frame.setProperty("focused", False)
        self.card_frame.setStyleSheet(f"""
            QFrame#agentInputCardFrame {{
                background-color: {ThemeColors.BG_CARD};
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: {ThemeRadii.DOCK};
            }}
            QFrame#agentInputCardFrame[focused="true"] {{
                border-color: {ThemeColors.BORDER_FOCUS};
                background-color: #FFFFFF;
            }}
        """)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        # Text Edit
        self.text_edit = AutoResizingAgentTextEdit(min_height=40, max_height=140, parent=self.card_frame)
        self.text_edit.submit_pressed.connect(self._on_submit)
        self.text_edit.focus_changed.connect(self._on_focus_changed)
        self.text_edit.file_dropped.connect(self.file_dropped.emit)
        self.text_edit.textChanged.connect(self._update_send_state)
        card_layout.addWidget(self.text_edit)

        # Toolbar Row
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(2, 0, 2, 2)
        toolbar_row.setSpacing(6)

        # Left: [+] Attach button
        self.btn_attach = QPushButton("+", self.card_frame)
        self.btn_attach.setObjectName("btnAttach")
        self.btn_attach.setFixedSize(26, 26)
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setToolTip("Attach files or images (@)")
        self.btn_attach.setStyleSheet(f"""
            QPushButton#btnAttach {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 13px;
                font-size: 15px;
                font-weight: 500;
                padding-bottom: 2px;
            }}
            QPushButton#btnAttach:hover {{
                background-color: rgba(0, 0, 0, 0.05);
                color: {ThemeColors.TEXT_PRIMARY};
                border-color: rgba(0, 0, 0, 0.20);
            }}
            QPushButton#btnAttach:pressed {{
                background-color: rgba(0, 0, 0, 0.08);
            }}
        """)
        self.btn_attach.clicked.connect(self.attach_requested.emit)
        toolbar_row.addWidget(self.btn_attach)

        # Model Selector Combobox
        self.model_combo = QComboBox(self.card_frame)
        self.model_combo.setObjectName("modelCombo")
        self.model_combo.addItems(self.DEFAULT_MODELS)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.setStyleSheet(f"""
            QComboBox#modelCombo {{
                background-color: rgba(0, 0, 0, 0.04);
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 13px;
                padding: 3px 12px 3px 10px;
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
                min-height: 20px;
            }}
            QComboBox#modelCombo:hover {{
                background-color: rgba(0, 0, 0, 0.07);
                border-color: rgba(0, 0, 0, 0.14);
            }}
            QComboBox#modelCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left-width: 0px;
            }}
            QComboBox#modelCombo QAbstractItemView {{
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.10);
                border-radius: 8px;
                selection-background-color: rgba(0, 122, 255, 0.10);
                selection-color: {ThemeColors.PRIMARY};
                color: {ThemeColors.TEXT_PRIMARY};
                padding: 4px;
            }}
        """)
        toolbar_row.addWidget(self.model_combo)

        toolbar_row.addStretch(1)

        # Right: [🎙] Voice dictation
        self.btn_voice = QPushButton("🎙", self.card_frame)
        self.btn_voice.setObjectName("btnVoice")
        self.btn_voice.setFixedSize(26, 26)
        self.btn_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_voice.setToolTip("Voice dictation")
        self.btn_voice.setStyleSheet(f"""
            QPushButton#btnVoice {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: none;
                border-radius: 13px;
                font-size: 13px;
            }}
            QPushButton#btnVoice:hover {{
                background-color: rgba(0, 0, 0, 0.05);
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        self.btn_voice.clicked.connect(self.voice_requested.emit)
        toolbar_row.addWidget(self.btn_voice)

        # Right: [➔] Circular Send Button
        self.btn_send = QPushButton("➔", self.card_frame)
        self.btn_send.setObjectName("btnSend")
        self.btn_send.setFixedSize(30, 30)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setToolTip("Send message (Return)")
        self.btn_send.setStyleSheet(f"""
            QPushButton#btnSend {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 15px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#btnSend:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton#btnSend:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
            QPushButton#btnSend:disabled {{
                background-color: rgba(0, 0, 0, 0.08);
                color: rgba(0, 0, 0, 0.25);
            }}
        """)
        self.btn_send.clicked.connect(self._on_submit)
        toolbar_row.addWidget(self.btn_send)

        card_layout.addLayout(toolbar_row)
        outer_layout.addWidget(self.card_frame)

        self._update_send_state()

    def _update_send_state(self) -> None:
        has_text = bool(self.get_prompt_text())
        self.btn_send.setEnabled(has_text)

    def set_prompt_text(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self._update_send_state()

    def get_prompt_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def clear(self) -> None:
        self.text_edit.clear()
        self._update_send_state()

    def _on_focus_changed(self, focused: bool) -> None:
        self.card_frame.setProperty("focused", focused)
        self.card_frame.style().unpolish(self.card_frame)
        self.card_frame.style().polish(self.card_frame)

    def _on_submit(self, *args) -> None:
        prompt = self.get_prompt_text()
        if not prompt:
            return
        payload = {
            "model": self.model_combo.currentText(),
        }
        self.clear()
        self.submit_requested.emit(prompt, payload)


class AgentPromptDock(QWidget):
    """
    Composite Agent Prompt Dock vertically assembling:
    - Layer 1: QueuedMessagesWidget (pending messages queue)
    - Layer 2: SubagentRunningBanner (active subagents telemetry)
    - Layer 3: AgentInputCard (modern auto-resizing input card)
    """

    submit_requested = Signal(str, dict)
    queue_action = Signal(str, int)
    plugin_changed = Signal(str, dict)
    attachment_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.active_plugin_id: Optional[str] = None
        self.attachment_path: Optional[str] = None
        self.plugin_state: dict[str, Any] = {}
        self.chip_container = QWidget(self)
        self.chip_container.setVisible(False)

        dock_layout = QVBoxLayout(self)
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.setSpacing(6)

        # Layer 1: Queued messages
        self.queued_widget = QueuedMessagesWidget(self)
        dock_layout.addWidget(self.queued_widget)

        # Layer 2: Subagent running banner
        self.running_banner = SubagentRunningBanner(self)
        dock_layout.addWidget(self.running_banner)

        # Layer 3: Agent input card
        self.input_card = AgentInputCard(self)
        dock_layout.addWidget(self.input_card)

        # Signal forwardings
        self.input_card.submit_requested.connect(self._on_input_card_submit)
        self.queued_widget.send_now_requested.connect(
            lambda idx: self.queue_action.emit("send_now", idx)
        )
        self.queued_widget.edit_requested.connect(
            lambda idx: self.queue_action.emit("edit", idx)
        )
        self.queued_widget.delete_requested.connect(
            lambda idx: self.queue_action.emit("delete", idx)
        )

    def _on_input_card_submit(self, prompt: str, payload: dict) -> None:
        if self.attachment_path and "attachment_path" not in payload:
            payload["attachment_path"] = self.attachment_path
        if self.active_plugin_id and "active_plugin_id" not in payload:
            payload["active_plugin_id"] = self.active_plugin_id
        if self.plugin_state and "plugin_state" not in payload:
            payload["plugin_state"] = self.plugin_state
        self.submit_requested.emit(prompt, payload)

    @property
    def text_edit(self) -> AutoResizingAgentTextEdit:
        return self.input_card.text_edit

    @property
    def send_btn(self) -> QPushButton:
        return self.input_card.btn_send

    def load_plugin(self, plugin_id: str, state: Optional[dict] = None) -> None:
        self.active_plugin_id = plugin_id
        self.plugin_state = dict(state or {})
        self.plugin_changed.emit(plugin_id, self.plugin_state)

    def unload_plugin(self) -> None:
        self.active_plugin_id = None
        self.plugin_state = {}
        self.plugin_changed.emit("", {})

    def set_attachment(self, file_path: Optional[str]) -> None:
        self.attachment_path = file_path
        self.chip_container.setVisible(bool(file_path))
        self.attachment_changed.emit(file_path or "")

    def clear_attachment(self) -> None:
        self.set_attachment(None)

    def get_attachment(self) -> Optional[str]:
        return self.attachment_path

    def set_queued_messages(self, prompts: list[str]) -> None:
        self.queued_widget.set_queued_messages(prompts)

    def set_running_subagents(self, subagents: list[tuple[str, str]]) -> None:
        self.running_banner.set_running_subagents(subagents)

    def set_prompt_text(self, text: str) -> None:
        self.input_card.set_prompt_text(text)

    def get_prompt_text(self) -> str:
        return self.input_card.get_prompt_text()

    def clear(self) -> None:
        self.input_card.clear()
