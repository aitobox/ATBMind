"""
ATBMind Desktop Native SkillHubView & SkillCard Grid
Apple HIG styled desktop workbench for browsing, filtering, enabling/disabling,
and managing ATBMind skills.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QKeyEvent, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.runtime.event_bus import (
    get_global_event_bus,
    SkillBoundRoleEvent,
    SkillInstalledEvent,
    SkillUpdatedEvent,
)
from atbmind_core.skills.manager import SkillManager
from atbmind_core.skills.schema import Skill, SkillMetadata, SkillSourceInfo
from apps.atbmind_desktop.icons import get_apple_icon
from apps.atbmind_desktop.theme import (
    APPLE_ICON_BUTTON_QSS,
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)
from apps.atbmind_desktop.widgets.skill_dialogs import (
    GitHubImportDialog,
    LocalImportDialog,
    NewSkillDialog,
)
from apps.atbmind_desktop.widgets.skill_drawer import SkillDetailDrawer
from apps.atbmind_desktop.workers import (
    SkillCheckUpdatesWorker,
    SkillImportWorker,
    SkillUpdateWorker,
)

logger = logging.getLogger(__name__)


class SkillCard(QFrame):
    """
    Apple HIG light card representing a single skill item.
    Displays:
    - Title, version badge, source badge ([GitHub: repo], [Project], [Global], [Local])
    - Enable / Disable switch toggle
    - 2-line description with word-wrap
    - Tags pills
    - Bound roles tags
    - Update button (highlighted when has_update is True)
    """

    card_clicked = Signal(str)
    skill_toggled = Signal(str, bool)
    update_requested = Signal(str)

    def __init__(self, skill: Skill, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.skill = skill
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("skillCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(150)
        self._update_style()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # -------------------------------------------------------------
        # Row 1: Header (Title, Version, Source Badge, Spacer, Switch)
        # -------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        # Title
        self.title_label = QLabel(self.skill.metadata.name)
        self.title_label.setObjectName("skillCardTitle")
        self.title_label.setStyleSheet(f"""
            QLabel#skillCardTitle {{
                font-size: 14px;
                font-weight: 700;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_layout.addWidget(self.title_label)

        # Version Pill
        ver_text = f"v{self.skill.metadata.version}" if self.skill.metadata.version else "v1.0.0"
        self.version_badge = QLabel(ver_text)
        self.version_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #F2F2F7;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 600;
                border-radius: 4px;
                padding: 2px 6px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_layout.addWidget(self.version_badge)

        # Source Badge
        self.source_badge = QLabel(self._get_source_badge_text())
        bg_col, text_col, border_col = self._get_source_badge_colors()
        self.source_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_col};
                color: {text_col};
                border: 1px solid {border_col};
                font-size: 10px;
                font-weight: 600;
                border-radius: 4px;
                padding: 1px 6px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        header_layout.addWidget(self.source_badge)

        header_layout.addStretch(1)

        # Enable / Disable Switch Checkbox
        self.enable_switch = QCheckBox(self)
        self.enable_switch.setObjectName("skillCardSwitch")
        self.enable_switch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enable_switch.setChecked(bool(getattr(self.skill.metadata, "enabled", True)))
        self.enable_switch.setToolTip("启用 / 禁用该技能 (Enable / Disable)")
        self.enable_switch.setStyleSheet(f"""
            QCheckBox#skillCardSwitch {{
                spacing: 6px;
                font-size: 11px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QCheckBox#skillCardSwitch::indicator {{
                width: 32px;
                height: 18px;
                border-radius: 9px;
                border: 1px solid {ThemeColors.BORDER_STRONG};
                background-color: #E5E5EA;
            }}
            QCheckBox#skillCardSwitch::indicator:checked {{
                background-color: {ThemeColors.PRIMARY};
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.enable_switch.toggled.connect(self._on_switch_toggled)
        header_layout.addWidget(self.enable_switch)

        main_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # Row 2: Description (2-line ellipsis)
        # -------------------------------------------------------------
        desc_text = self.skill.metadata.description or "暂无详细描述"
        self.desc_label = QLabel(desc_text)
        self.desc_label.setObjectName("skillCardDesc")
        self.desc_label.setWordWrap(True)
        self.desc_label.setMaximumHeight(36)
        self.desc_label.setStyleSheet(f"""
            QLabel#skillCardDesc {{
                font-size: 12px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
                line-height: 1.3;
            }}
        """)
        main_layout.addWidget(self.desc_label)

        # -------------------------------------------------------------
        # Row 3: Tags & Features Pills
        # -------------------------------------------------------------
        tags_layout = QHBoxLayout()
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(6)

        # Tags from metadata
        tags = self.skill.metadata.tags or []
        for tag in tags[:4]:  # Show at most 4 tags to keep card clean
            pill = QLabel(f"#{tag}")
            pill.setStyleSheet(f"""
                QLabel {{
                    background-color: rgba(0, 0, 0, 0.04);
                    color: {ThemeColors.TEXT_MUTED};
                    font-size: 10px;
                    font-weight: 500;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-family: {ThemeFonts.FONT_STACK};
                }}
            """)
            tags_layout.addWidget(pill)

        # Has Tools Indicator
        if hasattr(self.skill, "tools") and self.skill.tools:
            tools_badge = QLabel(f"⚡ {len(self.skill.tools)} Tools")
            tools_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: #FFF8EC;
                    color: {ThemeColors.WARNING};
                    border: 1px solid rgba(255, 149, 0, 0.3);
                    font-size: 10px;
                    font-weight: 600;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-family: {ThemeFonts.FONT_STACK};
                }}
            """)
            tags_layout.addWidget(tools_badge)

        tags_layout.addStretch(1)
        main_layout.addLayout(tags_layout)

        # -------------------------------------------------------------
        # Row 4: Footer (Bound Roles badges + Update action button)
        # -------------------------------------------------------------
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(6)

        # Bound Roles
        bound_roles = getattr(self.skill.metadata, "bound_roles", []) or []
        if bound_roles:
            for role_id in bound_roles[:3]:
                role_pill = QLabel(f"🤖 {role_id}")
                role_pill.setStyleSheet(f"""
                    QLabel {{
                        background-color: #F0F7FF;
                        color: {ThemeColors.PRIMARY};
                        font-size: 10px;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-family: {ThemeFonts.FONT_STACK};
                    }}
                """)
                footer_layout.addWidget(role_pill)
            if len(bound_roles) > 3:
                more_roles = QLabel(f"+{len(bound_roles) - 3}")
                more_roles.setStyleSheet(f"""
                    QLabel {{
                        color: {ThemeColors.TEXT_MUTED};
                        font-size: 10px;
                        font-weight: 600;
                    }}
                """)
                footer_layout.addWidget(more_roles)
        else:
            no_roles = QLabel("未挂载角色")
            no_roles.setStyleSheet(f"""
                QLabel {{
                    color: {ThemeColors.TEXT_MUTED};
                    font-size: 11px;
                    font-family: {ThemeFonts.FONT_STACK};
                }}
            """)
            footer_layout.addWidget(no_roles)

        footer_layout.addStretch(1)

        # Update button (shown/highlighted if source has update)
        has_update = False
        if hasattr(self.skill, "source") and self.skill.source:
            has_update = bool(getattr(self.skill.source, "has_update", False))

        self.btn_update = QPushButton("Update", self)
        self.btn_update.setObjectName("btnSkillUpdate")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setToolTip("拉取上游最新版本 (Update Skill)")
        if has_update:
            self.btn_update.setIcon(get_apple_icon("refresh", color="#FFFFFF"))
            self.btn_update.setStyleSheet(f"""
                QPushButton#btnSkillUpdate {{
                    background-color: {ThemeColors.PRIMARY};
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 600;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-family: {ThemeFonts.FONT_STACK};
                }}
                QPushButton#btnSkillUpdate:hover {{
                    background-color: {ThemeColors.PRIMARY_HOVER};
                }}
            """)
            self.btn_update.setVisible(True)
        else:
            self.btn_update.setVisible(False)

        self.btn_update.clicked.connect(self._on_update_clicked)
        footer_layout.addWidget(self.btn_update)

        main_layout.addLayout(footer_layout)

    def _get_source_badge_text(self) -> str:
        source = getattr(self.skill, "source", None)
        scope = getattr(self.skill, "scope", "global")
        if source and source.source_type == "github":
            repo = source.repo_url.split("/")[-1].replace(".git", "") if source.repo_url else "GitHub"
            if source.subpath:
                return f"GitHub: {repo}/{source.subpath}"
            return f"GitHub: {repo}"
        elif source and source.source_type == "scaffold":
            return "Custom"
        elif scope == "project":
            return "Project"
        else:
            return "Global"

    def _get_source_badge_colors(self) -> tuple[str, str, str]:
        source = getattr(self.skill, "source", None)
        scope = getattr(self.skill, "scope", "global")
        if source and source.source_type == "github":
            return ("#EBF5FF", ThemeColors.PRIMARY, "rgba(0, 122, 255, 0.25)")
        elif source and source.source_type == "scaffold":
            return ("#ECFDF5", "#059669", "rgba(5, 150, 105, 0.25)")
        elif scope == "project":
            return ("#F3E8FF", "#7C3AED", "rgba(124, 58, 237, 0.25)")
        else:
            return ("#F4F4F6", ThemeColors.TEXT_SECONDARY, ThemeColors.BORDER_SUBTLE)

    def _update_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#skillCard {{
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 12px;
            }}
            QFrame#skillCard:hover {{
                border-color: rgba(0, 122, 255, 0.38);
                background-color: #FFFFFF;
            }}
        """)

    def _on_switch_toggled(self, checked: bool) -> None:
        self.skill.metadata.enabled = checked
        self.skill_toggled.emit(self.skill.metadata.name, checked)

    def _on_update_clicked(self) -> None:
        self.update_requested.emit(self.skill.metadata.name)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked inside checkbox or update button
            if not self.enable_switch.geometry().contains(event.position().toPoint()):
                if not self.btn_update.isVisible() or not self.btn_update.geometry().contains(event.position().toPoint()):
                    self.card_clicked.emit(self.skill.metadata.name)
        super().mousePressEvent(event)


class SkillHubView(QWidget):
    """
    Apple HIG Central Skill Workbench View.
    Integrates:
    - Top Header Toolbar:
      - Title & counters
      - Search pill input
      - Filter category pills (All, Enabled, Updates, With Tools, Project, Global)
      - Quick actions (+ New, Import, Check Updates)
    - Scrollable Card Grid of SkillCard items
    - Empty State handling
    """

    skill_clicked = Signal(str)
    skill_toggled = Signal(str, bool)
    new_skill_requested = Signal()
    import_requested = Signal()
    check_updates_requested = Signal()
    skill_update_requested = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        skill_manager: Optional[SkillManager] = None,
    ) -> None:
        super().__init__(parent)
        self.skill_manager = skill_manager or SkillManager.get_instance()
        self._skills: List[Skill] = []
        self._active_filter_category: str = "all"
        self._search_query: str = ""
        self._cards: Dict[str, SkillCard] = {}
        self._active_workers: List[Any] = []

        self._init_ui()
        self.load_skills()

    def _init_ui(self) -> None:
        self.setObjectName("skillHubView")
        self.setStyleSheet(f"""
            QWidget#skillHubView {{
                background-color: {ThemeColors.BG_WINDOW};
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 20, 28, 20)
        root_layout.setSpacing(14)

        # -------------------------------------------------------------
        # 1. Top Header Row: Title & Action Buttons
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)

        self.title_label = QLabel("Skills Hub", self)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-weight: 700;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        title_col.addWidget(self.title_label)

        self.subtitle_label = QLabel("管理、扩展与装配智能专家技能包", self)
        self.subtitle_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        title_col.addWidget(self.subtitle_label)
        header_row.addLayout(title_col)

        header_row.addStretch(1)

        # Action Buttons
        self.btn_check_updates = QPushButton("🔄 检查更新", self)
        self.btn_check_updates.setObjectName("btnCheckUpdates")
        self.btn_check_updates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_updates.setIcon(get_apple_icon("refresh"))
        self.btn_check_updates.setStyleSheet(f"""
            QPushButton#btnCheckUpdates {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#btnCheckUpdates:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                border-color: {ThemeColors.BORDER_STRONG};
            }}
        """)
        self.btn_check_updates.clicked.connect(self.check_updates)
        header_row.addWidget(self.btn_check_updates)

        self.btn_import = QPushButton("⬇️ 导入技能", self)
        self.btn_import.setObjectName("btnImportSkill")
        self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import.setIcon(get_apple_icon("download"))
        self.btn_import.setStyleSheet(f"""
            QPushButton#btnImportSkill {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#btnImportSkill:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                border-color: {ThemeColors.BORDER_STRONG};
            }}
        """)
        self.btn_import.clicked.connect(self._show_import_dialog)
        header_row.addWidget(self.btn_import)

        self.btn_new = QPushButton("+ 新建技能", self)
        self.btn_new.setObjectName("btnNewSkill")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setIcon(get_apple_icon("plus", color="#FFFFFF"))
        self.btn_new.setStyleSheet(f"""
            QPushButton#btnNewSkill {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#btnNewSkill:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton#btnNewSkill:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """)
        self.btn_new.clicked.connect(self._show_new_skill_dialog)
        header_row.addWidget(self.btn_new)

        root_layout.addLayout(header_row)

        # -------------------------------------------------------------
        # 2. Search & Filter Bar
        # -------------------------------------------------------------
        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(0, 0, 0, 0)
        filter_bar.setSpacing(10)

        # Pill Search Input
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("skillSearchInput")
        self.search_input.setPlaceholderText("搜索技能名称、描述或标签...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(34)
        self.search_input.setMinimumWidth(260)
        self.search_input.setStyleSheet(f"""
            QLineEdit#skillSearchInput {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 13px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit#skillSearchInput:focus {{
                border-color: {ThemeColors.PRIMARY};
                background-color: #FFFFFF;
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self.search_input)

        # Filter Pills ButtonGroup
        self.pill_group = QButtonGroup(self)
        self.pill_group.setExclusive(True)

        self._filter_pills_defs = [
            ("all", "全部"),
            ("enabled", "已启用"),
            ("updates", "有更新 🔴"),
            ("tools", "含工具代码"),
            ("project", "项目内置"),
            ("global", "全局库"),
        ]

        self.pill_buttons: Dict[str, QPushButton] = {}
        pills_layout = QHBoxLayout()
        pills_layout.setContentsMargins(0, 0, 0, 0)
        pills_layout.setSpacing(6)

        pill_qss = f"""
            QPushButton.filterPill {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 14px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton.filterPill:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QPushButton.filterPill:checked {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border-color: {ThemeColors.PRIMARY};
                font-weight: 600;
            }}
        """

        for cat_id, cat_label in self._filter_pills_defs:
            btn = QPushButton(cat_label, self)
            btn.setProperty("class", "filterPill")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(pill_qss)
            if cat_id == "all":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, cid=cat_id: self._on_filter_pill_clicked(cid))
            self.pill_group.addButton(btn)
            self.pill_buttons[cat_id] = btn
            pills_layout.addWidget(btn)

        filter_bar.addLayout(pills_layout)
        filter_bar.addStretch(1)

        root_layout.addLayout(filter_bar)

        # -------------------------------------------------------------
        # 3. Content Body (Grid + Sliding Drawer)
        # -------------------------------------------------------------
        self.body_layout = QHBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        self.left_container = QWidget(self)
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self.left_container)
        self.scroll_area.setObjectName("skillHubScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea#skillHubScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea#skillHubScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            {SLIM_SCROLLBAR_QSS}
        """)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("skillGridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 8, 0, 8)
        self.grid_layout.setSpacing(14)
        self.scroll_area.setWidget(self.grid_container)
        left_layout.addWidget(self.scroll_area, 1)

        # -------------------------------------------------------------
        # 4. Empty State Placeholder
        # -------------------------------------------------------------
        self.empty_widget = QWidget(self.left_container)
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(10)

        self.empty_icon = QLabel("🧩", self.empty_widget)
        self.empty_icon.setStyleSheet("font-size: 36px;")
        empty_layout.addWidget(self.empty_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        self.empty_label = QLabel("暂无匹配的技能", self.empty_widget)
        self.empty_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        empty_layout.addWidget(self.empty_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_reset_filter = QPushButton("清除搜索与筛选", self.empty_widget)
        self.btn_reset_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_filter.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {ThemeColors.PRIMARY};
                font-size: 12px;
                font-weight: 600;
                border: none;
                text-decoration: underline;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        self.btn_reset_filter.clicked.connect(self._reset_filters)
        empty_layout.addWidget(self.btn_reset_filter, alignment=Qt.AlignmentFlag.AlignCenter)

        left_layout.addWidget(self.empty_widget, 1)
        self.empty_widget.setVisible(False)

        self.body_layout.addWidget(self.left_container, 1)

        # -------------------------------------------------------------
        # 5. Sliding Detail Drawer
        # -------------------------------------------------------------
        self.drawer = SkillDetailDrawer(skill_manager=self.skill_manager, parent=self)
        self.drawer.setVisible(False)
        self.drawer.closed.connect(self.close_skill_drawer)
        self.drawer.role_binding_changed.connect(self._on_drawer_role_binding_changed)
        self.drawer.skill_updated.connect(self.update_skill)
        self.drawer.skill_removed.connect(self._on_drawer_skill_removed)
        self.body_layout.addWidget(self.drawer, 0)

        root_layout.addLayout(self.body_layout, 1)

    def load_skills(self) -> None:
        """Discovers all skills from SkillManager and updates view."""
        skills_map = self.skill_manager.discover_all()
        # Sort skills: enabled first, then alphabetically
        skill_list = list(skills_map.values())
        skill_list.sort(key=lambda s: (not getattr(s.metadata, "enabled", True), s.metadata.name.lower()))
        self.set_skills(skill_list)

    def set_skills(self, skills: List[Skill]) -> None:
        """Explicitly sets the skills model and applies current filters."""
        self._skills = list(skills)
        self.apply_filters()

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text.strip().lower()
        self.apply_filters()

    def _on_filter_pill_clicked(self, category_id: str) -> None:
        self._active_filter_category = category_id
        self.apply_filters()

    def _reset_filters(self) -> None:
        self.search_input.clear()
        if "all" in self.pill_buttons:
            self.pill_buttons["all"].setChecked(True)
        self._active_filter_category = "all"
        self._search_query = ""
        self.apply_filters()

    def apply_filters(self) -> None:
        """Filters skills by search query and active category pill."""
        # Clear existing cards from grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()

        filtered: List[Skill] = []
        for s in self._skills:
            # 1. Category filter
            if not self._matches_category(s, self._active_filter_category):
                continue

            # 2. Search query filter (matches name, description, tags)
            if self._search_query:
                q = self._search_query
                name_match = q in s.metadata.name.lower()
                desc_match = q in (s.metadata.description or "").lower()
                tags_match = any(q in t.lower() for t in (s.metadata.tags or []))
                if not (name_match or desc_match or tags_match):
                    continue

            filtered.append(s)

        # Update empty state visibility
        if not filtered:
            self.scroll_area.setVisible(False)
            self.empty_widget.setVisible(True)
            return

        self.empty_widget.setVisible(False)
        self.scroll_area.setVisible(True)

        # Place cards in grid (2 columns layout)
        cols = 2
        for idx, skill in enumerate(filtered):
            row = idx // cols
            col = idx % cols
            card = SkillCard(skill, self.grid_container)
            card.card_clicked.connect(self.open_skill_drawer)
            card.skill_toggled.connect(self._handle_skill_toggled)
            card.update_requested.connect(self.update_skill)
            self.grid_layout.addWidget(card, row, col)
            self._cards[skill.metadata.name] = card

        # Subtitle counter update
        self.subtitle_label.setText(f"共 {len(self._skills)} 项技能 (当前展示 {len(filtered)} 项)")

    def _matches_category(self, skill: Skill, category: str) -> bool:
        if category == "all":
            return True
        elif category == "enabled":
            return bool(getattr(skill.metadata, "enabled", True))
        elif category == "updates":
            src = getattr(skill, "source", None)
            return bool(src and getattr(src, "has_update", False))
        elif category == "tools":
            return bool(hasattr(skill, "tools") and skill.tools)
        elif category == "project":
            return getattr(skill, "scope", "") == "project"
        elif category == "global":
            return getattr(skill, "scope", "") == "global"
        return True

    def _handle_skill_toggled(self, skill_name: str, enabled: bool) -> None:
        """Internal handler when skill toggle switch changes."""
        logger.info("Skill '%s' enabled toggled to: %s", skill_name, enabled)
        # Update via SkillManager if supported
        if hasattr(self.skill_manager, "set_skill_enabled"):
            try:
                self.skill_manager.set_skill_enabled(skill_name, enabled)
            except Exception as e:
                logger.warning("Failed persisting skill enabled flag: %s", e)
        self.skill_toggled.emit(skill_name, enabled)

    def count(self) -> int:
        """Returns the number of currently displayed cards."""
        return len(self._cards)

    def total_count(self) -> int:
        """Returns the total number of loaded skills."""
        return len(self._skills)

    def open_skill_drawer(self, skill_name: str) -> None:
        """Opens the sliding detail drawer displaying the specified skill."""
        skill = self.skill_manager.get_skill(skill_name)
        if not skill:
            for s in self._skills:
                if s.metadata.name == skill_name:
                    skill = s
                    break
        if skill:
            self.drawer.set_skill(skill)
            self.drawer.setVisible(True)
            self.skill_clicked.emit(skill_name)

    def close_skill_drawer(self) -> None:
        """Closes the skill detail drawer."""
        self.drawer.setVisible(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self.drawer.isVisible():
            self.close_skill_drawer()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_new_skill_dialog(self) -> NewSkillDialog:
        self.new_skill_requested.emit()
        dlg = NewSkillDialog(self)
        dlg.create_requested.connect(self._handle_create_skill)
        dlg.open()
        return dlg

    def _handle_create_skill(
        self, name: str, desc: str, tags: list, with_tools: bool, scope: str
    ) -> None:
        try:
            skill = self.skill_manager.create_skill(
                name=name,
                description=desc,
                tags=tags,
                with_tools=with_tools,
                target_scope=scope,
            )
            logger.info("Successfully scaffolded skill %s", name)
            self._publish_event(
                SkillInstalledEvent(
                    skill_name=skill.metadata.name,
                    source_type="scaffold",
                    scope=scope,
                )
            )
            self.load_skills()
        except Exception as e:
            logger.error("Failed creating skill %s: %s", name, e)

    def _show_import_dialog(self) -> GitHubImportDialog:
        self.import_requested.emit()
        dlg = GitHubImportDialog(self)
        dlg.import_requested.connect(self._handle_import_requested)
        dlg.open()
        return dlg

    def _handle_import_requested(
        self, source: str, scope: str, name: str, overwrite: bool
    ) -> None:
        s = source.strip()
        is_local = (
            s.startswith(("/", "~", "."))
            or (len(s) > 2 and s[1] == ":")
            or Path(s).exists()
        ) and not (s.startswith("http://") or s.startswith("https://") or "github.com" in s)
        src_type = "local" if is_local else "github"
        self.import_skill_async(
            source=s,
            source_type=src_type,
            target_scope=scope,
            skill_name=name or None,
            overwrite=overwrite,
        )

    def import_skill_async(
        self,
        source: str,
        source_type: Literal["github", "local"] = "github",
        target_scope: Literal["global", "project"] = "global",
        skill_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> SkillImportWorker:
        """Launches asynchronous worker to import a skill from GitHub or local."""
        worker = SkillImportWorker(
            source=source,
            source_type=source_type,
            target_scope=target_scope,
            skill_name=skill_name,
            overwrite=overwrite,
            skill_manager=self.skill_manager,
            parent=self,
        )
        self._active_workers.append(worker)

        def on_finished(success: bool, msg: str, skill_obj: Any) -> None:
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            if success and skill_obj is not None:
                logger.info("Imported skill %s successfully", skill_obj.metadata.name)
                self._publish_event(
                    SkillInstalledEvent(
                        skill_name=skill_obj.metadata.name,
                        source_type=source_type,
                        scope=target_scope,
                    )
                )
                self.load_skills()
            else:
                logger.error("Skill import failed: %s", msg)

        worker.finished.connect(on_finished)
        worker.start()
        return worker

    def check_updates(self) -> SkillCheckUpdatesWorker:
        """Checks upstream Git repositories for updates on all skills asynchronously."""
        self.check_updates_requested.emit()
        self.btn_check_updates.setEnabled(False)
        self.btn_check_updates.setText("🔄 检查中...")

        worker = SkillCheckUpdatesWorker(
            skill_manager=self.skill_manager,
            parent=self,
        )
        self._active_workers.append(worker)

        def on_finished(results: Dict[str, bool]) -> None:
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            self.btn_check_updates.setEnabled(True)
            self.btn_check_updates.setText("🔄 检查更新")
            logger.info("Checked updates for skills: %s", results)
            self.load_skills()
            has_updates_count = sum(1 for v in results.values() if v)
            if has_updates_count > 0:
                self.btn_check_updates.setToolTip(f"检查完成：发现 {has_updates_count} 个技能有新更新")
            else:
                self.btn_check_updates.setToolTip("检查完成：所有技能均已是最新")

        worker.finished.connect(on_finished)
        worker.start()
        return worker

    def update_skill(self, skill_name: str) -> SkillUpdateWorker:
        """Launches asynchronous worker to update a skill from upstream Git."""
        self.skill_update_requested.emit(skill_name)
        worker = SkillUpdateWorker(
            skill_name=skill_name,
            skill_manager=self.skill_manager,
            parent=self,
        )
        self._active_workers.append(worker)

        def on_finished(success: bool, msg: str, skill_obj: Any) -> None:
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            if success and skill_obj is not None:
                logger.info("Updated skill %s successfully", skill_name)
                self._publish_event(
                    SkillUpdatedEvent(
                        skill_name=skill_name,
                        version=getattr(skill_obj.metadata, "version", "") or "",
                        message=msg,
                    )
                )
                self.load_skills()
                if (
                    self.drawer.isVisible()
                    and self.drawer.skill
                    and self.drawer.skill.metadata.name == skill_name
                ):
                    self.drawer.set_skill(skill_obj)
            else:
                logger.error("Skill update failed for %s: %s", skill_name, msg)

        worker.finished.connect(on_finished)
        worker.start()
        return worker

    def _on_drawer_role_binding_changed(
        self, skill_name: str, role_id: str, is_bound: bool
    ) -> None:
        self._publish_event(
            SkillBoundRoleEvent(
                skill_name=skill_name,
                role_id=role_id,
                action="bind" if is_bound else "unbind",
            )
        )
        self.load_skills()

    def _on_drawer_skill_removed(self, skill_name: str) -> None:
        logger.info("Skill %s removed from drawer", skill_name)
        self.load_skills()

    def _publish_event(self, event: Any) -> None:
        try:
            bus = get_global_event_bus()
            if bus:
                bus.publish_sync(event)
        except Exception as e:
            logger.debug("Failed publishing event to EventBus: %s", e)
