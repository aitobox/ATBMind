"""
ATBMind WorkStreamArea & Timeline Items
Implements central Antigravity workspace stream:
- BreadcrumbHeaderBar: Displays [Project / Session Title], Open IDE button, and session menu.
- StepElapsedPill: Collapsible timeline card displaying 'Worked for Xm >' with execution logs.
- CodeChangeBadgeItem: Diff summary badge displaying '1 file changed +23 -0' with [Review] pill button.
- SubagentNoticeItem: Subagent telemetry notice item with status badge and message.
- WorkStreamArea: Composite widget integrating BreadcrumbHeaderBar, ChatStreamView, and AgentPromptDock.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
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
from apps.atbmind_desktop.widgets.agent_dock import AgentPromptDock
from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView


class BreadcrumbHeaderBar(QWidget):
    """
    Antigravity breadcrumb header bar displaying:
    - Left: '[Project Name] / [Session Title]' breadcrumb path
    - Right: 'Open IDE' launcher button and '...' session actions menu button
    """

    open_ide_requested = Signal()
    menu_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._project: str = "ATBMind"
        self._session_title: str = "新对话"

        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            BreadcrumbHeaderBar {{
                background-color: {ThemeColors.BG_CHAT};
                border-bottom: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Left: Breadcrumb path
        self.label_path = QLabel(self)
        self.label_path.setObjectName("breadcrumbLabel")
        self.label_path.setStyleSheet(f"""
            QLabel#breadcrumbLabel {{
                font-size: 13px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        layout.addWidget(self.label_path)

        layout.addStretch(1)

        # Right: [Open IDE] button
        self.btn_open_ide = QPushButton("💻 Open IDE", self)
        self.btn_open_ide.setObjectName("btnOpenIde")
        self.btn_open_ide.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_ide.setToolTip("Open current project in IDE")
        self.btn_open_ide.setStyleSheet(f"""
            QPushButton#btnOpenIde {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#btnOpenIde:hover {{
                background-color: {ThemeColors.BG_INPUT};
                border-color: {ThemeColors.BORDER_STRONG};
            }}
            QPushButton#btnOpenIde:pressed {{
                background-color: {ThemeColors.BG_INPUT_HOVER};
            }}
        """)
        self.btn_open_ide.clicked.connect(self.open_ide_requested.emit)
        layout.addWidget(self.btn_open_ide)

        # Right: [...] Session actions menu button
        self.btn_menu = QPushButton("···", self)
        self.btn_menu.setObjectName("btnMenu")
        self.btn_menu.setFixedSize(28, 28)
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.setToolTip("Session settings & actions")
        self.btn_menu.setStyleSheet(f"""
            QPushButton#btnMenu {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                color: {ThemeColors.TEXT_SECONDARY};
            }}
            QPushButton#btnMenu:hover {{
                background-color: {ThemeColors.BG_INPUT};
                border-color: {ThemeColors.BORDER_SUBTLE};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QPushButton#btnMenu:pressed {{
                background-color: {ThemeColors.BG_INPUT_HOVER};
            }}
        """)
        self.btn_menu.clicked.connect(self.menu_requested.emit)
        layout.addWidget(self.btn_menu)

        self.set_breadcrumb(self._project, self._session_title)

    def set_breadcrumb(self, project: str, session_title: str) -> None:
        self._project = project or "ATBMind"
        self._session_title = session_title or "新对话"
        self.label_path.setText(f"{self._project}  /  {self._session_title}")
        self.label_path.setToolTip(f"{self._project} / {self._session_title}")

    def get_project_name(self) -> str:
        return self._project

    def get_session_title(self) -> str:
        return self._session_title


class StepElapsedPill(QWidget):
    """
    Collapsible timeline pill displaying 'Worked for Xm >' or similar status.
    Clicking the header card toggles expanded details container.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        text: str = "Worked for 1m",
        details: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._details = details

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 4, 16, 4)
        outer_layout.setSpacing(0)

        # Main Card Frame
        self.card_frame = QFrame(self)
        self.card_frame.setObjectName("stepElapsedCardFrame")
        self.card_frame.setStyleSheet(f"""
            QFrame#stepElapsedCardFrame {{
                background-color: #F8F9FA;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 10px;
            }}
        """)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(4)

        # Header Row (Clickable)
        self.header_widget = QWidget(self.card_frame)
        self.header_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(8)

        # Icon
        self.icon_label = QLabel("⏱", self.header_widget)
        self.icon_label.setStyleSheet("font-size: 12px; background: transparent;")
        header_layout.addWidget(self.icon_label)

        # Title Label
        self.title_label = QLabel(self._text, self.header_widget)
        self.title_label.setObjectName("stepTitleLabel")
        self.title_label.setStyleSheet(f"""
            QLabel#stepTitleLabel {{
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        # Chevron Arrow
        self.chevron_label = QLabel("⮞", self.header_widget)
        self.chevron_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                color: {ThemeColors.TEXT_MUTED};
            }}
        """)
        header_layout.addWidget(self.chevron_label)

        card_layout.addWidget(self.header_widget)

        # Details Container (Initially Hidden)
        self.details_widget = QFrame(self.card_frame)
        self.details_widget.setObjectName("stepDetailsWidget")
        self.details_widget.setStyleSheet(f"""
            QFrame#stepDetailsWidget {{
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.06);
                border-radius: 6px;
                padding: 6px 8px;
            }}
        """)
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(6, 6, 6, 6)
        details_layout.setSpacing(2)

        self.details_label = QLabel(self._details, self.details_widget)
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-family: {ThemeFonts.FONT_MONO};
                color: {ThemeColors.TEXT_SECONDARY};
            }}
        """)
        details_layout.addWidget(self.details_label)

        card_layout.addWidget(self.details_widget)
        self.details_widget.setVisible(False)

        outer_layout.addWidget(self.card_frame)

        # Connect click event
        self.header_widget.mousePressEvent = self._on_header_mouse_press

        self.show()

    def _on_header_mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_expand()
            event.accept()
        else:
            event.ignore()

    def toggle_expand(self) -> None:
        expanded = not self.details_widget.isVisible()
        self.details_widget.setVisible(expanded)
        self.chevron_label.setText("⮟" if expanded else "⮞")
        self.toggled.emit(expanded)

    def is_expanded(self) -> bool:
        return self.details_widget.isVisible()

    def set_text(self, text: str) -> None:
        self._text = text
        self.title_label.setText(text)

    def set_details(self, details: str) -> None:
        self._details = details
        self.details_label.setText(details)


class CodeChangeBadgeItem(QWidget):
    """
    Timeline item displaying file changes summary (e.g. '1 file changed +23 -0')
    and a [Review] pill button emitting review_requested.
    """

    review_requested = Signal()

    def __init__(
        self,
        summary: str = "1 file changed +0 -0",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._summary = summary

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 4, 16, 4)
        outer_layout.setSpacing(0)

        # Badge Frame
        self.frame = QFrame(self)
        self.frame.setObjectName("codeChangeFrame")
        self.frame.setStyleSheet(f"""
            QFrame#codeChangeFrame {{
                background-color: #F8F9FA;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 8px;
            }}
            QFrame#codeChangeFrame:hover {{
                border-color: rgba(0, 0, 0, 0.14);
            }}
        """)

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # File Diff Icon
        icon_label = QLabel("📄", self.frame)
        icon_label.setStyleSheet("font-size: 13px; background: transparent;")
        layout.addWidget(icon_label)

        # Summary Label
        self.label = QLabel(self._summary, self.frame)
        self.label.setObjectName("codeChangeSummary")
        self.label.setStyleSheet(f"""
            QLabel#codeChangeSummary {{
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_MONO};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(self.label, 1)

        # [Review] Pill Action Button
        self.btn_review = QPushButton("Review", self.frame)
        self.btn_review.setObjectName("btnReview")
        self.btn_review.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_review.setStyleSheet(f"""
            QPushButton#btnReview {{
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 122, 255, 0.3);
                border-radius: 11px;
                padding: 2px 12px;
                font-size: 11px;
                font-weight: 600;
                color: {ThemeColors.PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#btnReview:hover {{
                background-color: {ThemeColors.PRIMARY_LIGHT};
                border-color: {ThemeColors.PRIMARY};
            }}
            QPushButton#btnReview:pressed {{
                background-color: {ThemeColors.PRIMARY_SUBTLE};
            }}
        """)
        self.btn_review.clicked.connect(self.review_requested.emit)
        layout.addWidget(self.btn_review)

        outer_layout.addWidget(self.frame)

    def set_summary(self, summary: str) -> None:
        self._summary = summary
        self.label.setText(summary)


class SubagentNoticeItem(QWidget):
    """
    Informational callout banner indicating subagent status, delegation, or messages.
    """

    def __init__(
        self,
        message: str = "",
        badge: str = "Subagent",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._badge = badge

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 4, 16, 4)
        outer_layout.setSpacing(0)

        # Frame
        self.frame = QFrame(self)
        self.frame.setObjectName("subagentNoticeFrame")
        self.frame.setStyleSheet(f"""
            QFrame#subagentNoticeFrame {{
                background-color: #F0F7FF;
                border: 1px solid rgba(0, 122, 255, 0.16);
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Badge Label
        self.badge_label = QLabel(self._badge, self.frame)
        self.badge_label.setObjectName("subagentBadge")
        self.badge_label.setStyleSheet(f"""
            QLabel#subagentBadge {{
                background-color: rgba(0, 122, 255, 0.12);
                color: {ThemeColors.PRIMARY};
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 2px 6px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        layout.addWidget(self.badge_label)

        # Message Label
        self.message_label = QLabel(self._message, self.frame)
        self.message_label.setObjectName("subagentMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"""
            QLabel#subagentMessage {{
                font-size: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        layout.addWidget(self.message_label, 1)

        outer_layout.addWidget(self.frame)

    def set_notice(self, message: str, badge: Optional[str] = None) -> None:
        self._message = message
        self.message_label.setText(message)
        if badge is not None:
            self._badge = badge
            self.badge_label.setText(badge)


class WorkStreamArea(QWidget):
    """
    Central Antigravity Work Area integrating:
    - Top: BreadcrumbHeaderBar (project / session breadcrumb, Open IDE, actions menu)
    - Center: ChatStreamView (scrollable conversation message stream & cards)
    - Bottom: AgentPromptDock (3-layer composite dock for queued messages, running subagents, and modern input card)
    """

    open_ide_requested = Signal()
    menu_requested = Signal()
    submit_requested = Signal(str, dict)
    clear_history_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("workStreamArea")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QWidget#workStreamArea {{ background-color: {ThemeColors.BG_CHAT}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top: Breadcrumb Header Bar
        self.header = BreadcrumbHeaderBar(self)
        self.header.open_ide_requested.connect(self.open_ide_requested.emit)
        self.header.menu_requested.connect(self.menu_requested.emit)
        layout.addWidget(self.header)

        # Center: Chat Stream View
        self.chat_stream = ChatStreamView(self)
        # Hide internal duplicate header bar so BreadcrumbHeaderBar acts as primary header
        if hasattr(self.chat_stream, "header_bar"):
            self.chat_stream.header_bar.setVisible(False)
        self.chat_stream.clear_history_requested.connect(self.clear_history_requested.emit)
        layout.addWidget(self.chat_stream, 1)

        # Bottom Dock Container with comfortable Antigravity padding
        dock_container = QWidget(self)
        dock_layout = QVBoxLayout(dock_container)
        dock_layout.setContentsMargins(16, 8, 16, 16)
        dock_layout.setSpacing(0)

        self.prompt_dock = AgentPromptDock(dock_container)
        self.prompt_dock.submit_requested.connect(self.submit_requested.emit)
        dock_layout.addWidget(self.prompt_dock)

        layout.addWidget(dock_container)

    def set_breadcrumb(self, project: str, session_title: str) -> None:
        """Sets project and session title in breadcrumb header and synchronizes with chat stream."""
        self.header.set_breadcrumb(project, session_title)
        if hasattr(self.chat_stream, "set_session_info"):
            self.chat_stream.set_session_info(session_title, None)

    def add_step_elapsed_pill(self, text: str = "Worked for 1m", details: str = "") -> StepElapsedPill:
        """Helper to append a StepElapsedPill timeline item to the stream."""
        pill = StepElapsedPill(text=text, details=details)
        self.chat_stream._insert_message_item(pill)
        return pill

    def add_code_change_badge(self, summary: str = "1 file changed +0 -0") -> CodeChangeBadgeItem:
        """Helper to append a CodeChangeBadgeItem timeline item to the stream."""
        badge = CodeChangeBadgeItem(summary=summary)
        self.chat_stream._insert_message_item(badge)
        return badge

    def add_subagent_notice(self, message: str, badge: str = "Subagent") -> SubagentNoticeItem:
        """Helper to append a SubagentNoticeItem banner to the stream."""
        notice = SubagentNoticeItem(message=message, badge=badge)
        self.chat_stream._insert_message_item(notice)
        return notice
