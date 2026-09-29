"""
ATBMind SidebarWidget
Left navigation sidebar adhering to Apple Human Interface Guidelines.
Features modern branding, quick session creation (Cmd+N), real-time session search filtering,
in-flight loading spinners, custom context menu, and settings launcher.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional
from PySide6.QtCore import QPoint, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.plugins.schemas import SessionRecord
from apps.atbmind_desktop.theme import (
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)


class LoadingSpinner(QWidget):
    """
    Apple HIG styled indeterminate loading spinner.
    Renders rotating radial tick marks using QPainter.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        size: int = 16,
        color: QColor = QColor(ThemeColors.PRIMARY),
    ) -> None:
        super().__init__(parent)
        self._size = size
        self._color = color
        self._step = 0
        self._ticks = 8
        self._is_spinning = False

        self.setFixedSize(size, size)
        self.setVisible(False)

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._on_timer)

    def start(self) -> None:
        """Starts spinner animation and displays widget."""
        self._is_spinning = True
        self.setVisible(True)
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self) -> None:
        """Stops spinner animation and hides widget."""
        self._is_spinning = False
        self._timer.stop()
        self.setVisible(False)
        self.update()

    def is_spinning(self) -> bool:
        """Returns True if the spinner animation is currently active."""
        return self._is_spinning

    def _on_timer(self) -> None:
        self._step = (self._step + 1) % self._ticks
        self.update()

    def paintEvent(self, event) -> None:
        if not self._is_spinning:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        radius_outer = min(center_x, center_y) - 1.0
        radius_inner = radius_outer * 0.55

        painter.translate(center_x, center_y)

        for i in range(self._ticks):
            angle = (360.0 / self._ticks) * i
            alpha_idx = (i - self._step) % self._ticks
            alpha = int(40 + (215 * (alpha_idx / (self._ticks - 1))))

            pen_color = QColor(self._color)
            pen_color.setAlpha(alpha)

            pen = QPen(pen_color)
            pen.setWidthF(1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            painter.save()
            painter.rotate(angle)
            painter.drawLine(0, int(-radius_inner), 0, int(-radius_outer))
            painter.restore()

        painter.end()


class SessionItemWidget(QWidget):
    """Custom row widget for session list item with icon, title, date, and spinner."""

    def __init__(
        self,
        session: SessionRecord,
        in_flight: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.in_flight = in_flight
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # Plugin Icon / Indicator badge
        is_draw = self.session.active_plugin_id == "draw"
        icon_str = "🎨" if is_draw else "💬"
        self.icon_label = QLabel(icon_str)
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {ThemeColors.PRIMARY_LIGHT if is_draw else 'rgba(0,0,0,0.04)'};
                border-radius: 6px;
                font-size: 13px;
            }}
        """)
        layout.addWidget(self.icon_label)

        # Text column (Title + Date)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(self.session.title or "新对话")
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        text_layout.addWidget(self.title_label)

        # Formatted time
        dt = datetime.datetime.fromtimestamp(self.session.updated_at)
        time_str = dt.strftime("%m-%d %H:%M")
        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        text_layout.addWidget(self.time_label)

        layout.addLayout(text_layout, 1)

        # Loading Spinner / in-flight indicator
        self.spinner = LoadingSpinner(self, size=16)
        layout.addWidget(self.spinner)

        if self.in_flight:
            self.spinner.start()
        else:
            self.spinner.stop()

    def update_data(self, session: SessionRecord, in_flight: bool) -> None:
        self.session = session
        self.in_flight = in_flight
        is_draw = session.active_plugin_id == "draw"
        self.icon_label.setText("🎨" if is_draw else "💬")
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {ThemeColors.PRIMARY_LIGHT if is_draw else 'rgba(0,0,0,0.04)'};
                border-radius: 6px;
                font-size: 13px;
            }}
        """)
        self.title_label.setText(session.title or "新对话")
        dt = datetime.datetime.fromtimestamp(session.updated_at)
        self.time_label.setText(dt.strftime("%m-%d %H:%M"))
        if in_flight:
            self.spinner.start()
        else:
            self.spinner.stop()


class SidebarWidget(QWidget):
    """
    Apple HIG styled left navigation sidebar for ATBMind.
    Supports session management, real-time search filtering, shortcuts, and settings.
    """

    new_session_requested = Signal()
    session_selected = Signal(str)                          # session_id
    session_rename_requested = Signal(str, str)             # session_id, new_title
    session_delete_requested = Signal(str)                  # session_id
    open_settings_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(250)
        self._session_items: Dict[str, QListWidgetItem] = {}
        self._in_flight_states: Dict[str, bool] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            SidebarWidget {{
                background-color: {ThemeColors.BG_SIDEBAR};
                border-right: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
            QLabel#brandingLabel {{
                font-size: 15px;
                font-weight: 700;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel#brandingBadge {{
                font-size: 10px;
                font-weight: 600;
                color: {ThemeColors.PRIMARY};
                background-color: {ThemeColors.PRIMARY_LIGHT};
                border-radius: 4px;
                padding: 1px 5px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#newBtn {{
                background-color: #FFFFFF;
                color: {ThemeColors.PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: {ThemeRadii.BUTTON};
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 600;
                font-family: {ThemeFonts.FONT_STACK};
                text-align: center;
            }}
            QPushButton#newBtn:hover {{
                background-color: {ThemeColors.PRIMARY_LIGHT};
                border-color: {ThemeColors.PRIMARY};
            }}
            QPushButton#newBtn:pressed {{
                background-color: #E0EFFF;
            }}
            QLineEdit#searchEdit {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit#searchEdit:focus {{
                border: 1.5px solid {ThemeColors.BORDER_FOCUS};
            }}
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            {SLIM_SCROLLBAR_QSS}
            QListWidget::item {{
                border-radius: {ThemeRadii.BUTTON};
                margin: 2px 2px;
                border: 1px solid transparent;
            }}
            QListWidget::item:selected {{
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.08);
            }}
            QListWidget::item:hover:!selected {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
            QPushButton#settingsBtn {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: none;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
                text-align: left;
            }}
            QPushButton#settingsBtn:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QLabel#versionLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
                padding-right: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        # 1. Branding Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        branding = QLabel("🧠 ATBMind")
        branding.setObjectName("brandingLabel")
        header_layout.addWidget(branding)

        badge = QLabel("PRO")
        badge.setObjectName("brandingBadge")
        header_layout.addWidget(badge)

        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        # 2. New Session Button (+ Cmd+N)
        self.new_btn = QPushButton("+ 新对话")
        self.new_btn.setObjectName("newBtn")
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.setToolTip("创建新对话 (⌘N / Ctrl+N)")
        self.new_btn.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(self.new_btn)

        # 3. Search Filter Bar
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("🔍 搜索会话历史...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_sessions)
        layout.addWidget(self.search_edit)

        # Global Shortcuts
        self.new_shortcut_std = QShortcut(QKeySequence.StandardKey.New, self)
        self.new_shortcut_std.activated.connect(self.new_session_requested.emit)
        self.new_shortcut_ctrl = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut_ctrl.activated.connect(self.new_session_requested.emit)

        # 4. Session List Widget
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, 1)

        # 5. Bottom Settings Bar
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_btn = QPushButton("⚙️ 设置 (Settings)")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings_requested.emit)
        bottom_layout.addWidget(self.settings_btn)
        bottom_layout.addStretch(1)

        version_label = QLabel("v0.1.0")
        version_label.setObjectName("versionLabel")
        bottom_layout.addWidget(version_label)

        layout.addLayout(bottom_layout)

    def _filter_sessions(self, query: str) -> None:
        """Dynamically filters session items based on search query."""
        q = query.strip().lower()
        for session_id, item in self._session_items.items():
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, SessionItemWidget):
                title = (widget.session.title or "").lower()
                matched = not q or q in title
                item.setHidden(not matched)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.session_selected.emit(session_id)

    def create_context_menu(
        self,
        session_id: str,
        item: Optional[QListWidgetItem] = None,
    ) -> QMenu:
        """Constructs and returns the context menu for a session row."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 4px;
                font-family: {ThemeFonts.FONT_STACK};
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background-color: {ThemeColors.PRIMARY_LIGHT};
                color: {ThemeColors.PRIMARY};
            }}
        """)
        rename_act = QAction("✏️ 重命名 (Rename)", self)
        delete_act = QAction("🗑️ 删除会话 (Delete)", self)

        rename_act.triggered.connect(lambda: self._prompt_rename(session_id, item))
        delete_act.triggered.connect(lambda: self._prompt_delete(session_id))

        menu.addAction(rename_act)
        menu.addAction(delete_act)
        return menu

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        session_id = item.data(Qt.ItemDataRole.UserRole)
        if not session_id:
            return

        menu = self.create_context_menu(session_id, item)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _prompt_rename(self, session_id: str, item: Optional[QListWidgetItem] = None) -> None:
        current_title = ""
        if item is not None:
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, SessionItemWidget):
                current_title = widget.session.title

        new_title, ok = QInputDialog.getText(
            self,
            "重命名会话",
            "请输入新的会话标题:",
            text=current_title,
        )
        if ok and new_title.strip():
            self.session_rename_requested.emit(session_id, new_title.strip())

    def _prompt_delete(self, session_id: str) -> None:
        reply = QMessageBox.question(
            self,
            "删除会话",
            "确定要删除此会话及其关联的所有生成图片吗？该操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.session_delete_requested.emit(session_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_sessions(self, sessions: List[SessionRecord], active_session_id: Optional[str] = None) -> None:
        """Populates the session list."""
        self.list_widget.clear()
        self._session_items.clear()

        for session in sessions:
            self.add_session(session, select=(session.session_id == active_session_id))

        if self.search_edit.text():
            self._filter_sessions(self.search_edit.text())

    def add_session(self, session: SessionRecord, select: bool = True) -> None:
        """Appends or prepends a session record into the list."""
        if session.session_id in self._session_items:
            self.update_session(session)
            return

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, session.session_id)

        in_flight = self._in_flight_states.get(session.session_id, False)
        widget = SessionItemWidget(session, in_flight=in_flight)
        item.setSizeHint(widget.sizeHint())

        self.list_widget.insertItem(0, item)
        self.list_widget.setItemWidget(item, widget)
        self._session_items[session.session_id] = item

        if select:
            self.list_widget.setCurrentItem(item)

    def update_session(self, session: SessionRecord) -> None:
        """Updates the visual representation of an existing session."""
        item = self._session_items.get(session.session_id)
        if not item:
            return
        widget = self.list_widget.itemWidget(item)
        if isinstance(widget, SessionItemWidget):
            in_flight = self._in_flight_states.get(session.session_id, False)
            widget.update_data(session, in_flight=in_flight)

    def remove_session(self, session_id: str) -> None:
        """Removes a session from the list."""
        item = self._session_items.pop(session_id, None)
        self._in_flight_states.pop(session_id, None)
        if item:
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def select_session(self, session_id: str) -> None:
        """Selects the item matching session_id without re-emitting signals."""
        item = self._session_items.get(session_id)
        if item:
            self.list_widget.blockSignals(True)
            self.list_widget.setCurrentItem(item)
            self.list_widget.blockSignals(False)

    def set_in_flight(self, session_id: str, in_flight: bool) -> None:
        """Updates spinner indicator for in-flight task."""
        self._in_flight_states[session_id] = in_flight
        item = self._session_items.get(session_id)
        if item:
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, SessionItemWidget):
                widget.update_data(widget.session, in_flight=in_flight)

    def is_in_flight(self, session_id: str) -> bool:
        """Returns True if the specified session has an in-flight background task."""
        return bool(self._in_flight_states.get(session_id, False))
