"""
NavigationSidebar - Antigravity Modern Navigation Sidebar.
Left navigation sidebar adhering to Apple HIG and Google Antigravity layout paradigms.
Features macOS traffic light margin, collapse toggle button ([|]), history back/forward navigation,
primary "+ New Conversation" card button, system navigation links (Conversation History, Scheduled Tasks),
PINNED CONVERSATIONS 2-line cards, PROJECTS tree grouped by workspace/repository,
hover context actions (Pin/Unpin, Rename, Delete), in-flight loading spinners, and pinned Settings footer.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.storage.schemas import SessionRecord
from apps.atbmind_desktop.theme import (
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)
from apps.atbmind_desktop.widgets.sidebar import LoadingSpinner


def format_relative_timestamp(timestamp: float, now: Optional[float] = None) -> str:
    """Formats a Unix epoch timestamp into an abbreviated relative time string."""
    if not timestamp or timestamp <= 0:
        return ""
    if now is None:
        now = time.time()
    diff = max(0.0, now - timestamp)
    if diff < 60:
        return "now"
    elif diff < 3600:
        return f"{int(diff // 60)}m"
    elif diff < 86400:
        return f"{int(diff // 3600)}h"
    elif diff < 86400 * 30:
        return f"{int(diff // 86400)}d"
    elif diff < 86400 * 365:
        return f"{int(diff // (86400 * 30))}mo"
    else:
        return f"{int(diff // (86400 * 365))}y"


class PinnedSessionCard(QFrame):
    """
    2-line card for a pinned conversation.
    Line 1: Title (left) + relative timestamp (right) + spinner + [...]
    Line 2: 📁 workspace_name
    """

    clicked = Signal(str)
    more_clicked = Signal(str, QPoint)

    def __init__(
        self,
        session: SessionRecord,
        is_active: bool = False,
        in_flight: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.is_active = is_active
        self.in_flight = in_flight
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("pinnedCard")
        self._update_card_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Line 1: Title + relative time + spinner + [...]
        line1 = QHBoxLayout()
        line1.setContentsMargins(0, 0, 0, 0)
        line1.setSpacing(6)

        self.title_label = QLabel(self.session.title or "新对话")
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        line1.addWidget(self.title_label, 1)

        time_str = format_relative_timestamp(self.session.updated_at)
        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        line1.addWidget(self.time_label)

        self.spinner = LoadingSpinner(self, size=14)
        line1.addWidget(self.spinner)
        if self.in_flight:
            self.spinner.start()
        else:
            self.spinner.stop()

        self.btn_more = QPushButton("···")
        self.btn_more.setFixedSize(20, 18)
        self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_more.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {ThemeColors.TEXT_MUTED};
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        self.btn_more.clicked.connect(self._on_more_clicked)
        line1.addWidget(self.btn_more)

        layout.addLayout(line1)

        # Line 2: 📁 workspace_name
        line2 = QHBoxLayout()
        line2.setContentsMargins(0, 0, 0, 0)
        line2.setSpacing(4)

        ws_name = self.session.workspace_name or "ATBMind"
        self.ws_label = QLabel(f"📁 {ws_name}")
        self.ws_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        line2.addWidget(self.ws_label)
        line2.addStretch(1)

        layout.addLayout(line2)

    def _update_card_style(self) -> None:
        bg_col = ThemeColors.BG_SIDEBAR_SELECTED if self.is_active else "#FFFFFF"
        border_col = ThemeColors.PRIMARY if self.is_active else ThemeColors.BORDER_SUBTLE
        border_w = "1.5px" if self.is_active else "1px"
        self.setStyleSheet(f"""
            QFrame#pinnedCard {{
                background-color: {bg_col};
                border: {border_w} solid {border_col};
                border-radius: 8px;
            }}
            QFrame#pinnedCard:hover {{
                border-color: {ThemeColors.PRIMARY if self.is_active else ThemeColors.BORDER_STRONG};
            }}
        """)

    def set_active(self, active: bool) -> None:
        if self.is_active != active:
            self.is_active = active
            self._update_card_style()

    def set_in_flight(self, in_flight: bool) -> None:
        self.in_flight = in_flight
        if in_flight:
            self.spinner.start()
        else:
            self.spinner.stop()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session.session_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.more_clicked.emit(self.session.session_id, event.globalPos())

    def _on_more_clicked(self) -> None:
        pt = self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height()))
        self.more_clicked.emit(self.session.session_id, pt)


class PinnedListWidget(QWidget):
    """
    Renders PINNED CONVERSATIONS section with 2-line cards.
    """

    session_selected = Signal(str)
    more_clicked = Signal(str, QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cards: Dict[str, PinnedSessionCard] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)

        # Section Header
        self.header_label = QLabel("PINNED CONVERSATIONS")
        self.header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 700;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
                padding-left: 4px;
            }}
        """)
        self.layout.addWidget(self.header_label)

        # Cards container
        self.cards_container = QVBoxLayout()
        self.cards_container.setContentsMargins(0, 0, 0, 0)
        self.cards_container.setSpacing(6)
        self.layout.addLayout(self.cards_container)

    def set_sessions(
        self,
        sessions: List[SessionRecord],
        active_session_id: Optional[str] = None,
        in_flight_states: Optional[Dict[str, bool]] = None,
    ) -> None:
        # Clear existing cards
        while self.cards_container.count():
            item = self.cards_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()

        in_flights = in_flight_states or {}

        for s in sessions:
            card = PinnedSessionCard(
                session=s,
                is_active=(s.session_id == active_session_id),
                in_flight=in_flights.get(s.session_id, False),
            )
            card.clicked.connect(self.session_selected.emit)
            card.more_clicked.connect(self.more_clicked.emit)
            self.cards_container.addWidget(card)
            self._cards[s.session_id] = card

        # Show or hide section based on card count
        self.setVisible(len(self._cards) > 0)

    def set_active_session(self, active_session_id: Optional[str]) -> None:
        for sid, card in self._cards.items():
            card.set_active(sid == active_session_id)

    def set_in_flight(self, session_id: str, in_flight: bool) -> None:
        card = self._cards.get(session_id)
        if card:
            card.set_in_flight(in_flight)

    def count(self) -> int:
        return len(self._cards)


class ProjectSessionRowWidget(QWidget):
    """
    Row widget for a session under a Project folder in the Projects Tree.
    Renders title (left) + relative timestamp + spinner + [...]
    """

    clicked = Signal(str)
    more_clicked = Signal(str, QPoint)

    def __init__(
        self,
        session: SessionRecord,
        is_active: bool = False,
        in_flight: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.is_active = is_active
        self.in_flight = in_flight
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("projectSessionRow")
        self._update_row_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.title_label = QLabel(self.session.title or "新对话")
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        layout.addWidget(self.title_label, 1)

        time_str = format_relative_timestamp(self.session.updated_at)
        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        layout.addWidget(self.time_label)

        self.spinner = LoadingSpinner(self, size=14)
        layout.addWidget(self.spinner)
        if self.in_flight:
            self.spinner.start()
        else:
            self.spinner.stop()

        self.btn_more = QPushButton("···")
        self.btn_more.setFixedSize(20, 18)
        self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_more.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {ThemeColors.TEXT_MUTED};
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        self.btn_more.clicked.connect(self._on_more_clicked)
        layout.addWidget(self.btn_more)

    def _update_row_style(self) -> None:
        bg_col = ThemeColors.BG_SIDEBAR_SELECTED if self.is_active else "transparent"
        self.setStyleSheet(f"""
            QWidget#projectSessionRow {{
                background-color: {bg_col};
                border-radius: 6px;
            }}
            QWidget#projectSessionRow:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_SELECTED if self.is_active else ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)

    def set_active(self, active: bool) -> None:
        if self.is_active != active:
            self.is_active = active
            self._update_row_style()

    def set_in_flight(self, in_flight: bool) -> None:
        self.in_flight = in_flight
        if in_flight:
            self.spinner.start()
        else:
            self.spinner.stop()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session.session_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.more_clicked.emit(self.session.session_id, event.globalPos())

    def _on_more_clicked(self) -> None:
        pt = self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height()))
        self.more_clicked.emit(self.session.session_id, pt)


class ProjectFolderSection(QWidget):
    """
    Project folder node: 📁 {workspace_name} with collapsible list of session rows.
    """

    session_selected = Signal(str)
    more_clicked = Signal(str, QPoint)

    def __init__(
        self,
        workspace_name: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.workspace_name = workspace_name
        self._is_expanded = True
        self._rows: Dict[str, ProjectSessionRowWidget] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)

        # Folder Header Bar
        self.header_btn = QPushButton()
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px 6px;
                text-align: left;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)
        self.header_btn.clicked.connect(self.toggle_expand)

        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(6)

        self.chevron_label = QLabel("▾")
        self.chevron_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px;")
        header_layout.addWidget(self.chevron_label)

        self.title_label = QLabel(f"📁 {self.workspace_name}")
        self.title_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {ThemeColors.TEXT_PRIMARY};
            font-family: {ThemeFonts.FONT_STACK};
        """)
        header_layout.addWidget(self.title_label, 1)

        self.count_badge = QLabel("0")
        self.count_badge.setStyleSheet(f"""
            font-size: 10px;
            color: {ThemeColors.TEXT_MUTED};
            font-family: {ThemeFonts.FONT_STACK};
        """)
        header_layout.addWidget(self.count_badge)

        self.main_layout.addWidget(self.header_btn)

        # Rows Container
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(12, 0, 0, 0)
        self.rows_layout.setSpacing(2)
        self.main_layout.addWidget(self.rows_container)

    def toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded
        self.chevron_label.setText("▾" if self._is_expanded else "▸")
        self.rows_container.setVisible(self._is_expanded)

    def set_sessions(
        self,
        sessions: List[SessionRecord],
        active_session_id: Optional[str] = None,
        in_flight_states: Optional[Dict[str, bool]] = None,
    ) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._rows.clear()

        in_flights = in_flight_states or {}

        for s in sessions:
            row = ProjectSessionRowWidget(
                session=s,
                is_active=(s.session_id == active_session_id),
                in_flight=in_flights.get(s.session_id, False),
            )
            row.clicked.connect(self.session_selected.emit)
            row.more_clicked.connect(self.more_clicked.emit)
            self.rows_layout.addWidget(row)
            self._rows[s.session_id] = row

        self.count_badge.setText(str(len(self._rows)))
        self.setVisible(len(self._rows) > 0)

    def set_active_session(self, active_session_id: Optional[str]) -> None:
        for sid, row in self._rows.items():
            row.set_active(sid == active_session_id)

    def set_in_flight(self, session_id: str, in_flight: bool) -> None:
        row = self._rows.get(session_id)
        if row:
            row.set_in_flight(in_flight)

    def count(self) -> int:
        return len(self._rows)


class ProjectsTreeWidget(QWidget):
    """
    Renders PROJECTS tree with workspace folder sections.
    """

    session_selected = Signal(str)
    more_clicked = Signal(str, QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._folder_sections: Dict[str, ProjectFolderSection] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)

        # Section Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 0, 4, 0)
        header_row.setSpacing(6)

        self.header_label = QLabel("PROJECTS")
        self.header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 700;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_row.addWidget(self.header_label)
        header_row.addStretch(1)

        self.layout.addLayout(header_row)

        # Folders container
        self.folders_container = QVBoxLayout()
        self.folders_container.setContentsMargins(0, 0, 0, 0)
        self.folders_container.setSpacing(6)
        self.layout.addLayout(self.folders_container)

    def set_sessions(
        self,
        sessions: List[SessionRecord],
        active_session_id: Optional[str] = None,
        in_flight_states: Optional[Dict[str, bool]] = None,
    ) -> None:
        # Group by workspace_name
        grouped: Dict[str, List[SessionRecord]] = {}
        for s in sessions:
            ws = s.workspace_name or "ATBMind"
            grouped.setdefault(ws, []).append(s)

        # Clear existing folders
        while self.folders_container.count():
            item = self.folders_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._folder_sections.clear()

        # Build folder sections
        for ws, ws_sessions in grouped.items():
            folder = ProjectFolderSection(workspace_name=ws)
            folder.session_selected.connect(self.session_selected.emit)
            folder.more_clicked.connect(self.more_clicked.emit)
            folder.set_sessions(ws_sessions, active_session_id, in_flight_states)
            self.folders_container.addWidget(folder)
            self._folder_sections[ws] = folder

    def set_active_session(self, active_session_id: Optional[str]) -> None:
        for folder in self._folder_sections.values():
            folder.set_active_session(active_session_id)

    def set_in_flight(self, session_id: str, in_flight: bool) -> None:
        for folder in self._folder_sections.values():
            folder.set_in_flight(session_id, in_flight)

    def project_session_count(self, workspace_name: str) -> int:
        folder = self._folder_sections.get(workspace_name)
        return folder.count() if folder else 0


class NavigationSidebar(QWidget):
    """
    Antigravity Modern Navigation Sidebar.
    Maintains left panel navigation, project tree, pinned cards, and actions.
    """

    new_session_requested = Signal()
    session_selected = Signal(str)
    session_pin_toggled = Signal(str)
    session_rename_requested = Signal(str, str)
    session_delete_requested = Signal(str)
    open_settings_requested = Signal()
    sidebar_collapse_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(360)
        self.setFixedWidth(260)

        self._sessions: Dict[str, SessionRecord] = {}
        self._in_flight_states: Dict[str, bool] = {}
        self._active_session_id: Optional[str] = None

        self._init_ui()
        self._init_shortcuts()

    def _init_ui(self) -> None:
        self.setObjectName("navigationSidebar")
        self.setStyleSheet(f"""
            QWidget#navigationSidebar {{
                background-color: {ThemeColors.BG_SIDEBAR};
                border-right: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
            QPushButton#btnToggle, QPushButton#btnNavBack, QPushButton#btnNavForward {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 600;
                padding: 4px 6px;
            }}
            QPushButton#btnToggle:hover, QPushButton#btnNavBack:hover, QPushButton#btnNavForward:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QPushButton#btnNew {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: {ThemeRadii.BUTTON};
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 600;
                font-family: {ThemeFonts.FONT_STACK};
                text-align: center;
            }}
            QPushButton#btnNew:hover {{
                background-color: {ThemeColors.PRIMARY_LIGHT};
                border-color: {ThemeColors.PRIMARY};
                color: {ThemeColors.PRIMARY};
            }}
            QPushButton#btnNew:pressed {{
                background-color: #E0EFFF;
            }}
            QPushButton#navLinkBtn {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
                text-align: left;
            }}
            QPushButton#navLinkBtn:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
            QPushButton#btnSettings {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
                text-align: left;
            }}
            QPushButton#btnSettings:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QLabel#versionLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
                padding-right: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Top Controls Bar (macOS traffic lights margin, collapse toggle [|], history back/forward)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(4)

        self.btn_toggle = QPushButton("[|]")
        self.btn_toggle.setObjectName("btnToggle")
        self.btn_toggle.setFixedSize(30, 26)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setToolTip("Toggle Sidebar (⌘B / Ctrl+B)")
        self.btn_toggle.clicked.connect(self.sidebar_collapse_requested.emit)
        top_bar.addWidget(self.btn_toggle)

        top_bar.addSpacing(4)

        self.btn_back = QPushButton("‹")
        self.btn_back.setObjectName("btnNavBack")
        self.btn_back.setFixedSize(26, 26)
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setToolTip("Back")
        top_bar.addWidget(self.btn_back)

        self.btn_forward = QPushButton("›")
        self.btn_forward.setObjectName("btnNavForward")
        self.btn_forward.setFixedSize(26, 26)
        self.btn_forward.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_forward.setToolTip("Forward")
        top_bar.addWidget(self.btn_forward)

        top_bar.addStretch(1)
        layout.addLayout(top_bar)

        # 2. + New Conversation Button (Cmd+N)
        self.btn_new = QPushButton("+ New Conversation")
        self.btn_new.setObjectName("btnNew")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setToolTip("Create New Conversation (⌘N / Ctrl+N)")
        self.btn_new.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(self.btn_new)

        # 3. System Navigation Links
        nav_links_layout = QVBoxLayout()
        nav_links_layout.setContentsMargins(0, 0, 0, 0)
        nav_links_layout.setSpacing(2)

        self.btn_history = QPushButton("🕒 Conversation History")
        self.btn_history.setObjectName("navLinkBtn")
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_links_layout.addWidget(self.btn_history)

        self.btn_scheduled = QPushButton("⏰ Scheduled Tasks")
        self.btn_scheduled.setObjectName("navLinkBtn")
        self.btn_scheduled.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_links_layout.addWidget(self.btn_scheduled)

        layout.addLayout(nav_links_layout)

        # 4. Scrollable Container for Pinned & Projects sections
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            {SLIM_SCROLLBAR_QSS}
        """)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.scroll_layout.setContentsMargins(0, 4, 0, 4)
        self.scroll_layout.setSpacing(14)

        # 4a. Pinned Conversations
        self.pinned_list = PinnedListWidget()
        self.pinned_list.session_selected.connect(self.click_session)
        self.pinned_list.more_clicked.connect(self._show_context_menu)
        self.scroll_layout.addWidget(self.pinned_list)

        # 4b. Projects Tree
        self.projects_tree = ProjectsTreeWidget()
        self.projects_tree.session_selected.connect(self.click_session)
        self.projects_tree.more_clicked.connect(self._show_context_menu)
        self.scroll_layout.addWidget(self.projects_tree)

        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(scroll_widget)
        layout.addWidget(self.scroll_area, 1)

        # 5. Bottom Pinned Settings Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)

        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.setObjectName("btnSettings")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings_requested.emit)
        bottom_bar.addWidget(self.btn_settings)

        bottom_bar.addStretch(1)

        self.version_label = QLabel("v0.2.0")
        self.version_label.setObjectName("versionLabel")
        bottom_bar.addWidget(self.version_label)

        layout.addLayout(bottom_bar)

    def _init_shortcuts(self) -> None:
        self.new_shortcut_std = QShortcut(QKeySequence.StandardKey.New, self)
        self.new_shortcut_std.activated.connect(self.new_session_requested.emit)
        self.new_shortcut_ctrl = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut_ctrl.activated.connect(self.new_session_requested.emit)

        self.toggle_shortcut_cmd = QShortcut(QKeySequence("Ctrl+B"), self)
        self.toggle_shortcut_cmd.activated.connect(self.sidebar_collapse_requested.emit)

    def _show_context_menu(self, session_id: str, pos: QPoint) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

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

        pin_text = "📌 取消置顶 (Unpin)" if session.is_pinned else "📌 置顶会话 (Pin)"
        pin_act = QAction(pin_text, self)
        rename_act = QAction("✏️ 重命名 (Rename)", self)
        delete_act = QAction("🗑️ 删除会话 (Delete)", self)

        pin_act.triggered.connect(lambda: self.trigger_pin_toggle(session_id))
        rename_act.triggered.connect(lambda: self.prompt_rename(session_id))
        delete_act.triggered.connect(lambda: self.prompt_delete(session_id))

        menu.addAction(pin_act)
        menu.addAction(rename_act)
        menu.addAction(delete_act)
        menu.exec(pos)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_sessions(
        self,
        sessions: List[SessionRecord],
        active_session_id: Optional[str] = None,
    ) -> None:
        """Populates the navigation sidebar with pinned cards and projects tree."""
        self._sessions = {s.session_id: s for s in sessions}
        self._active_session_id = active_session_id

        pinned = [s for s in sessions if s.is_pinned]
        unpinned = [s for s in sessions if not s.is_pinned]

        self.pinned_list.set_sessions(
            pinned,
            active_session_id=active_session_id,
            in_flight_states=self._in_flight_states,
        )
        self.projects_tree.set_sessions(
            unpinned,
            active_session_id=active_session_id,
            in_flight_states=self._in_flight_states,
        )

    def add_session(self, session: SessionRecord, select: bool = True) -> None:
        """Appends or updates a session record and refreshes the tree."""
        self._sessions[session.session_id] = session
        if select:
            self._active_session_id = session.session_id
        self.set_sessions(list(self._sessions.values()), active_session_id=self._active_session_id)
        if select:
            self.session_selected.emit(session.session_id)

    def update_session(self, session: SessionRecord) -> None:
        """Updates session data and refreshes view."""
        self._sessions[session.session_id] = session
        self.set_sessions(list(self._sessions.values()), active_session_id=self._active_session_id)

    def remove_session(self, session_id: str) -> None:
        """Removes a session and purges its in-flight state."""
        self._sessions.pop(session_id, None)
        self._in_flight_states.pop(session_id, None)
        self.set_sessions(list(self._sessions.values()), active_session_id=self._active_session_id)

    def select_session(self, session_id: str, emit_signal: bool = False) -> None:
        """Highlights session visually and optionally emits session_selected."""
        if self._active_session_id == session_id and not emit_signal:
            return
        self._active_session_id = session_id
        self.pinned_list.set_active_session(session_id)
        self.projects_tree.set_active_session(session_id)
        if emit_signal:
            self.session_selected.emit(session_id)

    def click_session(self, session_id: str) -> None:
        """Handles item click by updating visual selection and emitting session_selected."""
        self.select_session(session_id, emit_signal=False)
        self.session_selected.emit(session_id)

    def set_in_flight(self, session_id: str, is_in_flight: bool) -> None:
        """Sets loading spinner indicator for an in-flight background task."""
        self._in_flight_states[session_id] = is_in_flight
        self.pinned_list.set_in_flight(session_id, is_in_flight)
        self.projects_tree.set_in_flight(session_id, is_in_flight)

    def is_in_flight(self, session_id: str) -> bool:
        """Returns True if the given session is currently in flight."""
        return bool(self._in_flight_states.get(session_id, False))

    def pinned_count(self) -> int:
        """Returns the count of pinned conversation cards."""
        return self.pinned_list.count()

    def project_session_count(self, workspace_name: str) -> int:
        """Returns the count of conversations under the specified project/workspace."""
        return self.projects_tree.project_session_count(workspace_name)

    def trigger_pin_toggle(self, session_id: str) -> None:
        """Emits session_pin_toggled signal."""
        self.session_pin_toggled.emit(session_id)

    def trigger_rename(self, session_id: str, new_title: str) -> None:
        """Emits session_rename_requested signal."""
        self.session_rename_requested.emit(session_id, new_title)

    def trigger_delete(self, session_id: str) -> None:
        """Emits session_delete_requested signal."""
        self.session_delete_requested.emit(session_id)

    def prompt_rename(self, session_id: str, current_title: str = "") -> None:
        """Shows modal dialog to rename session and triggers signal if confirmed."""
        if not current_title:
            sess = self._sessions.get(session_id)
            if sess:
                current_title = sess.title or ""
        new_title, ok = QInputDialog.getText(
            self,
            "重命名会话",
            "请输入新的会话标题:",
            text=current_title,
        )
        if ok and new_title.strip():
            self.trigger_rename(session_id, new_title.strip())

    def prompt_delete(self, session_id: str) -> None:
        """Shows modal confirmation to delete session and triggers signal if confirmed."""
        reply = QMessageBox.question(
            self,
            "删除会话",
            "确定要删除此会话吗？该操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.trigger_delete(session_id)
