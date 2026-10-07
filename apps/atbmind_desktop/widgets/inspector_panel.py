"""
ATBMind InspectorPanel & Accordion Framework
Implements right Antigravity inspector pane conforming to Apple HIG and Google Antigravity layout:
- AccordionHeader: Clickable section header with chevron (⮞ / ⮟), title, count badge, and optional action widget
- AccordionSection: Collapsible section container supporting dynamic items
- InspectorHeaderBar: Top navigation header with view tabs (Context, Files, Artifacts) and action buttons (+, ⛶, [|])
- InspectorPanel: Responsive right pane (min 240px, max 480px, sizeHint 300px) with slim scrollable accordions:
  Subagents, Files Changed, Artifacts, Uploads, Background Tasks, Terminals, and Skills Used.
"""

from __future__ import annotations

from typing import Any, Optional, cast

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apps.atbmind_desktop.theme import (
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
)
from apps.atbmind_desktop.widgets.sidebar import LoadingSpinner


class AccordionHeader(QFrame):
    """
    Clickable header bar for an AccordionSection.
    Contains: chevron (⮞ / ⮟), title text, count badge, and optional action widget (e.g. dropdown).
    """

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("accordionHeader")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setStyleSheet(f"""
            QFrame#accordionHeader {{
                background-color: transparent;
                border-radius: 6px;
                padding: 0px 4px;
            }}
            QFrame#accordionHeader:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)

        self.header_layout = QHBoxLayout(self)
        self.header_layout.setContentsMargins(6, 0, 6, 0)
        self.header_layout.setSpacing(6)

        # Chevron indicator (⮞ / ⮟)
        self.chevron_label = QLabel("⮟", self)
        self.chevron_label.setObjectName("accordionChevron")
        self.chevron_label.setStyleSheet(f"""
            QLabel#accordionChevron {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                min-width: 14px;
            }}
        """)
        self.header_layout.addWidget(self.chevron_label)

        # Title text
        self.title_label = QLabel(self)
        self.title_label.setObjectName("accordionTitle")
        self.title_label.setStyleSheet(f"""
            QLabel#accordionTitle {{
                font-size: 12px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        self.header_layout.addWidget(self.title_label)

        # Count badge (pill badge)
        self.count_badge = QLabel(self)
        self.count_badge.setObjectName("countBadge")
        self.count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_badge.setStyleSheet(f"""
            QLabel#countBadge {{
                background-color: rgba(0, 0, 0, 0.06);
                color: {ThemeColors.TEXT_SECONDARY};
                border-radius: 8px;
                padding: 1px 6px;
                font-size: 11px;
                font-weight: 600;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        self.count_badge.setVisible(False)
        self.header_layout.addWidget(self.count_badge)

        self.header_layout.addStretch(1)

        self._action_widget: Optional[QWidget] = None

        # Filter mouse events on label children to propagate clicks to header
        self.chevron_label.installEventFilter(self)
        self.title_label.installEventFilter(self)
        self.count_badge.installEventFilter(self)

    def set_action_widget(self, widget: QWidget) -> None:
        """Sets an optional trailing action widget (e.g. dropdown or button)."""
        if self._action_widget:
            self.header_layout.removeWidget(self._action_widget)
            self._action_widget.deleteLater()
        self._action_widget = widget
        self.header_layout.addWidget(widget)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = cast(QMouseEvent, event)
            if mouse_event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            event.ignore()


class AccordionSection(QWidget):
    """
    Collapsible section conforming to Antigravity accordion framework.
    Consists of an AccordionHeader and a content container.
    """

    expanded_changed = Signal(bool)

    def __init__(
        self,
        title: str = "",
        count: Optional[int] = None,
        expanded: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._count = count
        self._expanded = expanded
        self._items: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        self.header = AccordionHeader(self)
        self.header_title = self.header.title_label
        self.count_badge = self.header.count_badge
        self.chevron = self.header.chevron_label
        self.header.clicked.connect(self.toggle_expanded)
        layout.addWidget(self.header)

        self.content_container = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(14, 2, 4, 4)
        self.content_layout.setSpacing(4)
        layout.addWidget(self.content_container)

        self.set_title(title, count)
        self.set_expanded(expanded)

    def set_title(self, title: str, count: Optional[int] = None) -> None:
        """Updates section title and optional count badge."""
        self._title = title
        self._count = count
        self.header_title.setText(title)
        if count is not None:
            self.count_badge.setText(str(count))
            self.count_badge.setVisible(True)
        else:
            self.count_badge.setText("")
            self.count_badge.setVisible(False)

    def set_header_widget(self, widget: QWidget) -> None:
        """Sets an optional trailing widget in the header bar."""
        self.header.set_action_widget(widget)

    def is_expanded(self) -> bool:
        """Returns True if the section is currently expanded."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Expands or collapses the section content container."""
        self._expanded = expanded
        self.content_container.setVisible(expanded)
        self.chevron.setText("⮟" if expanded else "⮞")
        self.expanded_changed.emit(expanded)

    def toggle_expanded(self) -> None:
        """Toggles expansion state."""
        self.set_expanded(not self._expanded)

    def add_item(self, widget: QWidget) -> None:
        """Appends a child item widget to the section content container."""
        self._items.append(widget)
        self.content_layout.addWidget(widget)

    def clear_items(self) -> None:
        """Removes and cleans up all child item widgets."""
        for widget in list(self._items):
            try:
                if hasattr(widget, "stop"):
                    widget.stop()
            except Exception:
                pass
            self.content_layout.removeWidget(widget)
            widget.deleteLater()
        self._items.clear()

    def item_count(self) -> int:
        """Returns current number of item widgets inside this section."""
        return len(self._items)


class InspectorHeaderBar(QWidget):
    """
    Top header bar for InspectorPanel.
    Contains:
    - View mode tabs (Context, Files, Artifacts)
    - Action buttons: [+] (`btn_add`), [⛶] (`btn_fullscreen`), [|] (`btn_collapse`)
    """

    tab_changed = Signal(int)
    add_requested = Signal()
    fullscreen_requested = Signal()
    collapse_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_tab: int = 0
        self._tabs = ["Context", "Files", "Artifacts"]
        self._tab_buttons: list[QPushButton] = []

        self.setFixedHeight(40)
        self.setStyleSheet(f"""
            InspectorHeaderBar {{
                background-color: {ThemeColors.BG_SIDEBAR};
                border-bottom: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        # Tabs container (segmented control)
        tabs_container = QWidget(self)
        tabs_layout = QHBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(2)

        for idx, tab_name in enumerate(self._tabs):
            btn = QPushButton(tab_name, tabs_container)
            btn.setObjectName(f"tab_{tab_name.lower()}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self.set_current_tab(i))
            self._tab_buttons.append(btn)
            tabs_layout.addWidget(btn)

        layout.addWidget(tabs_container)
        layout.addStretch(1)

        # Action buttons
        actions_container = QWidget(self)
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(4)

        btn_action_qss = f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 5px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                border-color: {ThemeColors.BORDER_LIGHT};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.BG_SIDEBAR_SELECTED};
            }}
        """

        self.btn_add = QPushButton("+", actions_container)
        self.btn_add.setObjectName("btnAdd")
        self.btn_add.setToolTip("Add item")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setFixedSize(26, 26)
        self.btn_add.setStyleSheet(btn_action_qss)
        self.btn_add.clicked.connect(self.add_requested.emit)
        actions_layout.addWidget(self.btn_add)

        self.btn_fullscreen = QPushButton("⛶", actions_container)
        self.btn_fullscreen.setObjectName("btnFullscreen")
        self.btn_fullscreen.setToolTip("Toggle Fullscreen")
        self.btn_fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fullscreen.setFixedSize(26, 26)
        self.btn_fullscreen.setStyleSheet(btn_action_qss)
        self.btn_fullscreen.clicked.connect(self.fullscreen_requested.emit)
        actions_layout.addWidget(self.btn_fullscreen)

        self.btn_collapse = QPushButton("[|]", actions_container)
        self.btn_collapse.setObjectName("btnCollapse")
        self.btn_collapse.setToolTip("Collapse Inspector")
        self.btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse.setFixedSize(26, 26)
        self.btn_collapse.setStyleSheet(btn_action_qss)
        self.btn_collapse.clicked.connect(self.collapse_requested.emit)
        actions_layout.addWidget(self.btn_collapse)

        layout.addWidget(actions_container)

        self._update_tab_styles()

    def current_tab(self) -> int:
        return self._current_tab

    def set_current_tab(self, index: int) -> None:
        """Sets the active tab and emits tab_changed signal."""
        if 0 <= index < len(self._tabs):
            self._current_tab = index
            self._update_tab_styles()
            self.tab_changed.emit(index)

    def _update_tab_styles(self) -> None:
        for idx, btn in enumerate(self._tab_buttons):
            if idx == self._current_tab:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #FFFFFF;
                        border: 1px solid {ThemeColors.BORDER_SUBTLE};
                        border-radius: 6px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: 600;
                        color: {ThemeColors.TEXT_PRIMARY};
                        font-family: {ThemeFonts.FONT_STACK};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: 1px solid transparent;
                        border-radius: 6px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: 500;
                        color: {ThemeColors.TEXT_SECONDARY};
                        font-family: {ThemeFonts.FONT_STACK};
                    }}
                    QPushButton:hover {{
                        background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                        color: {ThemeColors.TEXT_PRIMARY};
                    }}
                """)


class InspectorPanel(QWidget):
    """
    Antigravity Right Inspector Panel.
    Layout constraints:
    - minimum width: 240px
    - maximum width: 480px
    - sizeHint width: 300px
    Housing vertical accordions for Subagents, Files Changed, Artifacts,
    Uploads, Background Tasks, Terminals, and Skills Used.
    """

    artifact_clicked = Signal(dict)
    artifact_proceed = Signal(str)
    artifact_revise = Signal(str, str)
    task_clicked = Signal(dict)
    task_kill_requested = Signal(str)
    task_input_requested = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("inspectorPanel")
        self.setMinimumWidth(240)
        self.setMaximumWidth(480)
        # Note: Do NOT call setFixedWidth!

        self._subagents: dict[str, dict[str, Any]] = {}
        self._files: list[dict[str, Any]] = []
        self._skills: list[tuple[str, str]] = []
        self._tasks: list[dict[str, Any]] = []
        self._artifacts: list[dict[str, Any]] = []
        self._uploads: list[dict[str, Any]] = []
        self._terminals: list[dict[str, Any]] = []
        self._active_task_dialogs: dict[str, Any] = {}

        self.setStyleSheet(f"""
            QWidget#inspectorPanel {{
                background-color: {ThemeColors.BG_SIDEBAR};
                border-left: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        self.header = InspectorHeaderBar(self)
        self.header.tab_changed.connect(self._on_tab_changed)
        main_layout.addWidget(self.header)

        # Connect internal click to viewers
        self.artifact_clicked.connect(self.open_artifact_viewer)
        self.task_clicked.connect(self.open_task_terminal)

        # Scroll Area with Slim Scrollbar
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            {SLIM_SCROLLBAR_QSS}
        """)

        # Container inside Scroll Area
        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setObjectName("inspectorContentWidget")
        self.content_widget.setStyleSheet(f"""
            QWidget#inspectorContentWidget {{
                background-color: transparent;
            }}
        """)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 16)
        self.content_layout.setSpacing(6)

        # Accordion Sections
        # 1. Subagents
        self.section_subagents = AccordionSection("Subagents", count=0, parent=self.content_widget)
        self.content_layout.addWidget(self.section_subagents)

        # 2. Files Changed (with Uncommitted filter dropdown)
        self.section_files = AccordionSection("Files Changed", count=0, parent=self.content_widget)
        self.files_filter_combo = QComboBox(self.section_files)
        self.files_filter_combo.addItems(["Uncommitted", "All Changes", "Staged Changes"])
        self.files_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 5px;
                padding: 1px 18px 1px 6px;
                font-size: 11px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QComboBox:hover {{
                border-color: {ThemeColors.BORDER_STRONG};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left-width: 0px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid {ThemeColors.TEXT_MUTED};
                width: 0px;
                height: 0px;
                margin-right: 4px;
            }}
        """)
        self.section_files.set_header_widget(self.files_filter_combo)
        self.content_layout.addWidget(self.section_files)

        # 3. Artifacts
        self.section_artifacts = AccordionSection("Artifacts", count=0, parent=self.content_widget)
        self.content_layout.addWidget(self.section_artifacts)

        # 4. Uploads
        self.section_uploads = AccordionSection("Uploads", count=0, parent=self.content_widget)
        self.content_layout.addWidget(self.section_uploads)

        # 5. Background Tasks
        self.section_tasks = AccordionSection("Background Tasks", count=0, parent=self.content_widget)
        self.content_layout.addWidget(self.section_tasks)

        # 6. Terminals
        self.section_terminals = AccordionSection("Terminals", count=0, parent=self.content_widget)
        self.content_layout.addWidget(self.section_terminals)

        # 7. Skills Used
        self.section_skills = AccordionSection("Skills Used", count=0, parent=self.content_widget)
        self.content_layout.addWidget(self.section_skills)

        # Stretch at bottom
        self.content_layout.addStretch(1)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

    def sizeHint(self) -> QSize:
        """Recommended width for the inspector pane is 300px."""
        return QSize(300, 600)

    # ----------------------------------------------------------------------
    # Tab Switching
    # ----------------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        """Filters section visibility based on selected tab view mode."""
        if index == 0:  # Context: show all sections
            for section in (
                self.section_subagents,
                self.section_files,
                self.section_artifacts,
                self.section_uploads,
                self.section_tasks,
                self.section_terminals,
                self.section_skills,
            ):
                section.setVisible(True)
        elif index == 1:  # Files: focus on Files Changed
            self.section_subagents.setVisible(False)
            self.section_files.setVisible(True)
            self.section_files.set_expanded(True)
            self.section_artifacts.setVisible(False)
            self.section_uploads.setVisible(False)
            self.section_tasks.setVisible(False)
            self.section_terminals.setVisible(False)
            self.section_skills.setVisible(False)
        elif index == 2:  # Artifacts: focus on Artifacts
            self.section_subagents.setVisible(False)
            self.section_files.setVisible(False)
            self.section_artifacts.setVisible(True)
            self.section_artifacts.set_expanded(True)
            self.section_uploads.setVisible(False)
            self.section_tasks.setVisible(False)
            self.section_terminals.setVisible(False)
            self.section_skills.setVisible(False)

    # ----------------------------------------------------------------------
    # Telemetry Updates
    # ----------------------------------------------------------------------

    def update_subagent(self, id: str, name: str, state: str, elapsed: str) -> None:
        """
        Updates or adds subagent telemetry record.
        State: 'running' (spinner), 'done' (checkmark), 'failed'/'error' (error icon).
        """
        self._subagents[id] = {
            "id": id,
            "name": name,
            "state": state,
            "elapsed": elapsed,
        }
        self._rebuild_subagents()

    def _rebuild_subagents(self) -> None:
        self.section_subagents.clear_items()
        count = len(self._subagents)
        self.section_subagents.set_title("Subagents", count=count)
        for sub in self._subagents.values():
            row = self._create_subagent_row(
                sub["id"], sub["name"], sub["state"], sub["elapsed"]
            )
            self.section_subagents.add_item(row)

    def _create_subagent_row(self, sub_id: str, name: str, state: str, elapsed: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 3, 6, 3)
        row_layout.setSpacing(6)

        st = state.lower()
        if st in ("running", "active", "in_progress", "working"):
            spinner = LoadingSpinner(row, size=14)
            spinner.start()
            row_layout.addWidget(spinner)
            row.spinner = spinner  # type: ignore[attr-defined]
            row.stop = spinner.stop  # type: ignore[attr-defined]
        elif st in ("done", "completed", "success", "finished"):
            icon = QLabel("✓", row)
            icon.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.SUCCESS};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            row_layout.addWidget(icon)
        elif st in ("failed", "error"):
            icon = QLabel("✕", row)
            icon.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.ERROR};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            row_layout.addWidget(icon)
        else:
            icon = QLabel("●", row)
            icon.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.TEXT_MUTED};
                    font-size: 10px;
                }}
            """)
            row_layout.addWidget(icon)

        name_label = QLabel(name, row)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(name_label)
        row_layout.addStretch(1)

        elapsed_label = QLabel(elapsed, row)
        elapsed_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(elapsed_label)

        return row

    def update_files_changed(self, files: list[dict[str, Any]]) -> None:
        """
        Updates changed files list.
        Each file dict may contain: path, status ('added', 'modified', 'deleted'),
        insertions, deletions.
        """
        self._files = list(files)
        self.section_files.clear_items()
        count = len(self._files)
        self.section_files.set_title("Files Changed", count=count)
        for f in self._files:
            row = self._create_file_row(f)
            self.section_files.add_item(row)

    def _create_file_row(self, file_info: dict[str, Any]) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 3, 6, 3)
        row_layout.setSpacing(6)

        status = str(file_info.get("status", "modified")).lower()
        if status in ("added", "new"):
            badge_text = "A"
            badge_color = ThemeColors.SUCCESS
            badge_bg = ThemeColors.SUCCESS_LIGHT
        elif status in ("deleted", "removed"):
            badge_text = "D"
            badge_color = ThemeColors.ERROR
            badge_bg = ThemeColors.ERROR_BG
        else:
            badge_text = "M"
            badge_color = ThemeColors.PRIMARY
            badge_bg = ThemeColors.PRIMARY_LIGHT

        status_badge = QLabel(badge_text, row)
        status_badge.setFixedSize(16, 16)
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {badge_bg};
                color: {badge_color};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(status_badge)

        path = str(file_info.get("path", ""))
        name_label = QLabel(path, row)
        name_label.setToolTip(path)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_MONO};
            }}
        """)
        row_layout.addWidget(name_label)
        row_layout.addStretch(1)

        ins = file_info.get("insertions", 0)
        dels = file_info.get("deletions", 0)
        if ins or dels:
            diff_label = QLabel(f"+{ins} -{dels}", row)
            diff_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 11px;
                    color: {ThemeColors.TEXT_MUTED};
                    font-family: {ThemeFonts.FONT_MONO};
                }}
            """)
            row_layout.addWidget(diff_label)

        return row

    def update_skills_used(self, skills: list[tuple[str, str]]) -> None:
        """Updates list of skills used in current session: (name, path)."""
        self._skills = list(skills)
        self.section_skills.clear_items()
        count = len(self._skills)
        self.section_skills.set_title("Skills Used", count=count)
        for skill_name, skill_path in self._skills:
            row = self._create_skill_row(skill_name, skill_path)
            self.section_skills.add_item(row)

    def _create_skill_row(self, name: str, path: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 3, 6, 3)
        row_layout.setSpacing(6)

        icon_label = QLabel("📄", row)
        icon_label.setStyleSheet("font-size: 12px;")
        row_layout.addWidget(icon_label)

        name_label = QLabel(name, row)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(name_label)
        row_layout.addStretch(1)

        path_label = QLabel(path, row)
        path_label.setToolTip(path)
        path_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_MONO};
            }}
        """)
        row_layout.addWidget(path_label)

        return row

    def update_background_tasks(self, tasks: list[dict[str, Any]]) -> None:
        """Updates list of running or completed background tasks."""
        self._tasks = list(tasks)
        self.section_tasks.clear_items()
        count = len(self._tasks)
        self.section_tasks.set_title("Background Tasks", count=count)
        for t in self._tasks:
            row = self._create_task_row(t)
            self.section_tasks.add_item(row)
            t_id = str(t.get("id", t.get("task_id", "")))
            if t_id in self._active_task_dialogs:
                self._active_task_dialogs[t_id].set_status(t.get("status", "running"), t.get("elapsed", ""))

    def _create_task_row(self, task_info: dict[str, Any]) -> QWidget:
        row = QWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(f"""
            QWidget:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                border-radius: 6px;
            }}
        """)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(6)

        st = str(task_info.get("state", task_info.get("status", "running"))).lower()
        if st in ("running", "active"):
            spinner = LoadingSpinner(row, size=14)
            spinner.start()
            row_layout.addWidget(spinner)
            row.spinner = spinner  # type: ignore[attr-defined]
            row.stop = spinner.stop  # type: ignore[attr-defined]
        elif st in ("done", "completed", "success"):
            icon = QLabel("✓", row)
            icon.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.SUCCESS};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            row_layout.addWidget(icon)
        elif st in ("failed", "error", "killed"):
            icon = QLabel("✕", row)
            icon.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.ERROR};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            row_layout.addWidget(icon)
        else:
            icon = QLabel("●", row)
            icon.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.TEXT_MUTED};
                    font-size: 10px;
                }}
            """)
            row_layout.addWidget(icon)

        name = str(task_info.get("name", task_info.get("id", "Task")))
        name_label = QLabel(name, row)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(name_label)
        row_layout.addStretch(1)

        status_text = str(task_info.get("elapsed", st.capitalize()))
        status_label = QLabel(status_text, row)
        status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(status_label)

        def _on_mouse_release(event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.task_clicked.emit(task_info)

        row.mouseReleaseEvent = _on_mouse_release  # type: ignore[assignment]
        return row

    def open_task_terminal(self, task_info: dict[str, Any]) -> Any:
        """Opens interactive TaskTerminalDialog to inspect output, send stdin, or terminate task."""
        from apps.atbmind_desktop.widgets.task_terminal import TaskTerminalDialog
        dialog = TaskTerminalDialog(task_info, self)
        task_id = str(task_info.get("id", task_info.get("task_id", "")))
        self._active_task_dialogs[task_id] = dialog

        dialog.kill_requested.connect(self.task_kill_requested.emit)
        dialog.input_submitted.connect(self.task_input_requested.emit)

        def _cleanup(*args: Any) -> None:
            self._active_task_dialogs.pop(task_id, None)

        dialog.finished.connect(_cleanup)
        dialog.show()
        return dialog

    def append_task_output(self, task_id: str, chunk: str) -> None:
        """Forwards streaming output chunk to any active task terminal dialog."""
        if task_id in self._active_task_dialogs:
            self._active_task_dialogs[task_id].append_output(chunk)

    def update_artifacts(self, artifacts: list[dict[str, Any]]) -> None:
        """Updates artifacts list."""
        self._artifacts = list(artifacts)
        self.section_artifacts.clear_items()
        self.section_artifacts.set_title("Artifacts", count=len(self._artifacts))
        for art in self._artifacts:
            row = self._create_artifact_row(art)
            self.section_artifacts.add_item(row)

    def _create_artifact_row(self, art: dict[str, Any]) -> QWidget:
        row = QWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(f"""
            QWidget:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                border-radius: 6px;
            }}
        """)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(6)

        icon = QLabel("📦", row)
        row_layout.addWidget(icon)

        title = str(art.get("title", art.get("name", "Artifact")))
        title_label = QLabel(title, row)
        summary = str(art.get("summary", ""))
        if summary:
            title_label.setToolTip(summary)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        row_layout.addWidget(title_label)
        row_layout.addStretch(1)

        ver = art.get("version", 1)
        ver_label = QLabel(f"v{ver}", row)
        ver_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                font-weight: 600;
                color: {ThemeColors.PRIMARY};
                background: rgba(0, 122, 255, 0.08);
                border-radius: 4px;
                padding: 1px 4px;
            }}
        """)
        row_layout.addWidget(ver_label)

        def _on_mouse_release(event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.artifact_clicked.emit(art)

        row.mouseReleaseEvent = _on_mouse_release  # type: ignore[assignment]
        return row

    def open_artifact_viewer(self, artifact: dict[str, Any]) -> Any:
        """Opens modal ArtifactViewerDialog to inspect markdown, diff, and submit feedback."""
        from apps.atbmind_desktop.widgets.artifact_viewer import ArtifactViewerDialog
        dialog = ArtifactViewerDialog(artifact, self)
        dialog.proceed_requested.connect(self.artifact_proceed.emit)
        dialog.revise_requested.connect(self.artifact_revise.emit)
        dialog.exec()
        return dialog

    def update_uploads(self, uploads: list[dict[str, Any]]) -> None:
        """Updates uploads list."""
        self._uploads = list(uploads)
        self.section_uploads.clear_items()
        self.section_uploads.set_title("Uploads", count=len(self._uploads))
        for up in self._uploads:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 3, 6, 3)
            row_layout.setSpacing(6)
            icon = QLabel("📎", row)
            row_layout.addWidget(icon)
            name = str(up.get("name", "Upload"))
            name_label = QLabel(name, row)
            name_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_PRIMARY};")
            row_layout.addWidget(name_label)
            row_layout.addStretch(1)
            self.section_uploads.add_item(row)

    def update_terminals(self, terminals: list[dict[str, Any]]) -> None:
        """Updates terminals list."""
        self._terminals = list(terminals)
        self.section_terminals.clear_items()
        self.section_terminals.set_title("Terminals", count=len(self._terminals))
        for term in self._terminals:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 3, 6, 3)
            row_layout.setSpacing(6)
            icon = QLabel("💻", row)
            row_layout.addWidget(icon)
            name = str(term.get("name", term.get("id", "Terminal")))
            name_label = QLabel(name, row)
            name_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_PRIMARY};")
            row_layout.addWidget(name_label)
            row_layout.addStretch(1)
            self.section_terminals.add_item(row)

    # ----------------------------------------------------------------------
    # Count Accessors
    # ----------------------------------------------------------------------

    def subagent_count(self) -> int:
        return len(self._subagents)

    def skills_count(self) -> int:
        return len(self._skills)

    def files_count(self) -> int:
        return len(self._files)

    def tasks_count(self) -> int:
        return len(self._tasks)

    def task_count(self) -> int:
        return len(self._tasks)

    def artifacts_count(self) -> int:
        return len(self._artifacts)

    def uploads_count(self) -> int:
        return len(self._uploads)

    def terminals_count(self) -> int:
        return len(self._terminals)
