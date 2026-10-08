"""
ATBMind Desktop Native SkillDetailDrawer
Apple HIG sliding detail drawer for previewing SKILL.md, inspecting tools schema,
diagnosing environment dependencies, and dynamically binding expert roles.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.roles.registry import get_role_registry
from atbmind_core.skills.manager import SkillManager
from atbmind_core.skills.schema import Skill
from apps.atbmind_desktop.icons import get_apple_icon
from apps.atbmind_desktop.workers import SkillPipInstallWorker
from apps.atbmind_desktop.theme import (
    APPLE_ICON_BUTTON_QSS,
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)

logger = logging.getLogger(__name__)


class SkillDetailDrawer(QFrame):
    """
    Sliding detail drawer providing deep inspection and management for a selected skill:
    - SKILL.md rich Markdown viewer
    - Exported AgentTool parameters schema inspector
    - requirements.txt environment dependency diagnostics
    - Interactive RobotRole binding checkboxes with instant persistence
    - Management actions: Update, Reveal in Finder, Remove Skill
    """

    closed = Signal()
    role_binding_changed = Signal(str, str, bool)  # skill_name, role_id, is_bound
    skill_updated = Signal(str)                    # skill_name
    skill_removed = Signal(str)                    # skill_name

    def __init__(
        self,
        skill: Optional[Skill] = None,
        skill_manager: Optional[SkillManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.skill = skill
        self.skill_manager = skill_manager or SkillManager.get_instance()
        self.role_registry = (
            getattr(self.skill_manager, "role_registry", None) or get_role_registry()
        )

        self.setFixedWidth(440)
        self.setObjectName("skillDetailDrawer")
        self.btn_install_deps: Optional[QPushButton] = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._init_ui()

        if self.skill:
            self.set_skill(self.skill)

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#skillDetailDrawer {{
                background-color: #FFFFFF;
                border-left: 1px solid {ThemeColors.BORDER_SUBTLE};
            }}
            QLabel {{
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QTabWidget::pane {{
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                background-color: #FFFFFF;
                top: -1px;
            }}
            QTabBar::tab {{
                background: #F4F4F6;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QTabBar::tab:selected {{
                background: #FFFFFF;
                color: {ThemeColors.PRIMARY};
                font-weight: 600;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # -------------------------------------------------------------
        # Header Row: Title, Badges, Close Button
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title_badge_row = QHBoxLayout()
        title_badge_row.setSpacing(6)

        self.title_label = QLabel("技能详情", self)
        self.title_label.setObjectName("drawerTitle")
        self.title_label.setStyleSheet(f"""
            QLabel#drawerTitle {{
                font-size: 16px;
                font-weight: 700;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        title_badge_row.addWidget(self.title_label)

        self.version_badge = QLabel("v1.0.0", self)
        self.version_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #F2F2F7;
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 600;
                border-radius: 4px;
                padding: 2px 6px;
            }}
        """)
        title_badge_row.addWidget(self.version_badge)

        self.source_badge = QLabel("Global", self)
        self.source_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #EBF5FF;
                color: {ThemeColors.PRIMARY};
                border: 1px solid rgba(0, 122, 255, 0.2);
                font-size: 10px;
                font-weight: 600;
                border-radius: 4px;
                padding: 1px 6px;
            }}
        """)
        title_badge_row.addWidget(self.source_badge)
        title_badge_row.addStretch(1)

        title_col.addLayout(title_badge_row)

        self.desc_label = QLabel("技能描述信息", self)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        title_col.addWidget(self.desc_label)

        header_row.addLayout(title_col, 1)

        # Close [✕] Button
        self.btn_close = QPushButton(self)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setText("✕")
        self.btn_close.setToolTip("关闭详情抽屉 (ESC)")
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 12px;
                color: {ThemeColors.TEXT_MUTED};
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        self.btn_close.clicked.connect(self.closed.emit)
        header_row.addWidget(self.btn_close)

        layout.addLayout(header_row)

        # -------------------------------------------------------------
        # Tabbed Content Area
        # -------------------------------------------------------------
        self.tabs = QTabWidget(self)

        # Tab 1: SKILL.md Markdown Preview
        self.markdown_viewer = QTextBrowser(self)
        self.markdown_viewer.setOpenExternalLinks(True)
        self.markdown_viewer.setStyleSheet(f"""
            QTextBrowser {{
                background-color: #FFFFFF;
                border: none;
                padding: 10px;
                font-size: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            {SLIM_SCROLLBAR_QSS}
        """)
        self.tabs.addTab(self.markdown_viewer, "文档 (SKILL.md)")

        # Tab 2: Exported Tools Inspector
        self.tools_widget = QWidget()
        tools_layout = QVBoxLayout(self.tools_widget)
        tools_layout.setContentsMargins(10, 10, 10, 10)
        tools_layout.setSpacing(8)

        self.tools_scroll = QScrollArea(self.tools_widget)
        self.tools_scroll.setWidgetResizable(True)
        self.tools_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tools_scroll.setStyleSheet(f"background: transparent; {SLIM_SCROLLBAR_QSS}")

        self.tools_container = QWidget()
        self.tools_container_layout = QVBoxLayout(self.tools_container)
        self.tools_container_layout.setContentsMargins(0, 0, 0, 0)
        self.tools_container_layout.setSpacing(8)
        self.tools_scroll.setWidget(self.tools_container)

        tools_layout.addWidget(self.tools_scroll)
        self.tabs.addTab(self.tools_widget, "工具清单")

        # Tab 3: Environment Requirements Diagnostic
        self.env_widget = QWidget()
        env_layout = QVBoxLayout(self.env_widget)
        env_layout.setContentsMargins(12, 12, 12, 12)
        env_layout.setSpacing(10)

        self.env_info_label = QLabel("正在诊断 Python 依赖环境...", self.env_widget)
        self.env_info_label.setWordWrap(True)
        self.env_info_label.setStyleSheet("font-size: 12px;")
        env_layout.addWidget(self.env_info_label)

        self.env_scroll = QScrollArea(self.env_widget)
        self.env_scroll.setWidgetResizable(True)
        self.env_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.env_scroll.setStyleSheet(f"background: transparent; {SLIM_SCROLLBAR_QSS}")

        self.env_container = QWidget()
        self.env_container_layout = QVBoxLayout(self.env_container)
        self.env_container_layout.setContentsMargins(0, 0, 0, 0)
        self.env_container_layout.setSpacing(6)
        self.env_scroll.setWidget(self.env_container)

        env_layout.addWidget(self.env_scroll, 1)
        self.tabs.addTab(self.env_widget, "环境诊断")

        # Tab 4: Role Binding Checkbox Matrix
        self.roles_widget = QWidget()
        roles_layout = QVBoxLayout(self.roles_widget)
        roles_layout.setContentsMargins(12, 12, 12, 12)
        roles_layout.setSpacing(8)

        roles_header = QLabel("一键装配至专家角色:", self.roles_widget)
        roles_header.setStyleSheet("font-size: 12px; font-weight: 600; color: #86868B;")
        roles_layout.addWidget(roles_header)

        self.roles_scroll = QScrollArea(self.roles_widget)
        self.roles_scroll.setWidgetResizable(True)
        self.roles_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.roles_scroll.setStyleSheet(f"background: transparent; {SLIM_SCROLLBAR_QSS}")

        self.roles_container = QWidget()
        self.roles_container_layout = QVBoxLayout(self.roles_container)
        self.roles_container_layout.setContentsMargins(0, 0, 0, 0)
        self.roles_container_layout.setSpacing(6)
        self.roles_scroll.setWidget(self.roles_container)

        roles_layout.addWidget(self.roles_scroll, 1)
        self.tabs.addTab(self.roles_widget, "角色装配")

        layout.addWidget(self.tabs, 1)

        # -------------------------------------------------------------
        # Footer Action Buttons Row
        # -------------------------------------------------------------
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 4, 0, 0)
        footer_row.setSpacing(8)

        self.btn_update = QPushButton("检查更新", self)
        self.btn_update.setIcon(get_apple_icon("refresh"))
        self.btn_update.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)
        self.btn_update.clicked.connect(self._on_update_clicked)
        footer_row.addWidget(self.btn_update)

        self.btn_finder = QPushButton("在访达中打开", self)
        self.btn_finder.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)
        self.btn_finder.clicked.connect(self._open_in_finder)
        footer_row.addWidget(self.btn_finder)

        footer_row.addStretch(1)

        self.btn_remove = QPushButton("卸载", self)
        self.btn_remove.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFF0F0;
                color: {ThemeColors.ERROR};
                border: 1px solid rgba(255, 59, 48, 0.2);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #FFE5E5;
                border-color: {ThemeColors.ERROR};
            }}
        """)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        footer_row.addWidget(self.btn_remove)

        layout.addLayout(footer_row)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_skill(self, skill: Skill) -> None:
        """Populates the drawer with the details of the specified skill."""
        self.skill = skill
        self.title_label.setText(skill.metadata.name)
        ver = f"v{skill.metadata.version}" if skill.metadata.version else "v1.0.0"
        self.version_badge.setText(ver)
        self.desc_label.setText(skill.metadata.description or "暂无详细描述")

        # Source badge
        source = getattr(skill, "source", None)
        scope = getattr(skill, "scope", "global")
        if source and source.source_type == "github":
            self.source_badge.setText("GitHub")
        elif source and source.source_type == "scaffold":
            self.source_badge.setText("Custom")
        elif scope == "project":
            self.source_badge.setText("Project")
        else:
            self.source_badge.setText("Global")

        # Check if skill supports remote git updates
        is_git = bool(source and getattr(source, "source_type", "") == "github" and getattr(source, "repo_url", ""))
        self.btn_update.setEnabled(is_git)
        if is_git:
            self.btn_update.setToolTip("检查远端 Git 仓库更新")
        else:
            self.btn_update.setToolTip("本地或内置技能暂不支持远端更新")

        # 1. Render SKILL.md
        skill_dir = Path(skill.skill_dir) if skill.skill_dir else None
        md_file = skill_dir / "SKILL.md" if skill_dir else None
        if md_file and md_file.exists():
            content = md_file.read_text(encoding="utf-8")
            self.markdown_viewer.setMarkdown(content)
        else:
            self.markdown_viewer.setMarkdown(f"# {skill.metadata.name}\n\n*未找到 SKILL.md 文档文件。*")

        # 2. Render Tools
        self._render_tools(skill)

        # 3. Render Requirements
        self._render_requirements(skill.metadata.name)

        # 4. Render Role Binding Checkboxes
        self._render_roles(skill)

    def _render_tools(self, skill: Skill) -> None:
        while self.tools_container_layout.count():
            item = self.tools_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        tools = getattr(skill, "tools", []) or []
        if not tools:
            empty_lbl = QLabel("纯指南类技能（未导出可执行工具）", self.tools_container)
            empty_lbl.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 12px; padding: 8px;")
            self.tools_container_layout.addWidget(empty_lbl)
            return

        for tool in tools:
            tool_frame = QFrame(self.tools_container)
            tool_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #F8F9FA;
                    border: 1px solid rgba(0, 0, 0, 0.08);
                    border-radius: 8px;
                    padding: 8px;
                }}
            """)
            t_layout = QVBoxLayout(tool_frame)
            t_layout.setContentsMargins(6, 6, 6, 6)
            t_layout.setSpacing(4)

            t_name = getattr(tool, "name", "tool")
            t_desc = getattr(tool, "description", "") or "无描述"
            name_lbl = QLabel(f"⚡ <b>{t_name}</b>", tool_frame)
            name_lbl.setStyleSheet("font-size: 13px; color: #1D1D1F;")
            t_layout.addWidget(name_lbl)

            desc_lbl = QLabel(t_desc, tool_frame)
            desc_lbl.setStyleSheet("font-size: 11px; color: #6E6E73;")
            desc_lbl.setWordWrap(True)
            t_layout.addWidget(desc_lbl)

            # Parameters schema properties
            schema_cls = getattr(tool, "parameters_schema", None)
            if schema_cls and hasattr(schema_cls, "model_json_schema"):
                try:
                    js = schema_cls.model_json_schema()
                    props = js.get("properties", {})
                    if props:
                        prop_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in props.items())
                        props_lbl = QLabel(f"参数: <code>{prop_str}</code>", tool_frame)
                        props_lbl.setStyleSheet("font-size: 10px; color: #007AFF;")
                        t_layout.addWidget(props_lbl)
                except Exception:
                    pass

            self.tools_container_layout.addWidget(tool_frame)

    def _render_requirements(self, skill_name: str) -> None:
        while self.env_container_layout.count():
            item = self.env_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        try:
            diag = self.skill_manager.check_requirements(skill_name)
            has_req = diag.get("has_requirements", False)
            if not has_req:
                self.env_info_label.setText("✓ 该技能无特定第三方 Python 依赖需求，即装即用。")
                self.env_info_label.setStyleSheet("color: #34C759; font-weight: 500;")
                return

            missing = diag.get("missing", [])
            satisfied = diag.get("satisfied", [])

            if missing:
                self.env_info_label.setText(f"⚠️ 发现 {len(missing)} 项缺失依赖，请点击下方按钮一键安装或在终端执行 pip install。")
                self.env_info_label.setStyleSheet("color: #FF9500; font-weight: 600;")

                btn = QPushButton("📦 一键安装缺失依赖", self.env_container)
                btn.setObjectName("btnInstallMissingDeps")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton#btnInstallMissingDeps {{
                        background-color: {ThemeColors.PRIMARY};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-size: 11px;
                        font-weight: 600;
                    }}
                    QPushButton#btnInstallMissingDeps:hover {{
                        background-color: {ThemeColors.PRIMARY_HOVER};
                    }}
                    QPushButton#btnInstallMissingDeps:disabled {{
                        background-color: #C7C7CC;
                    }}
                """)

                def on_install_clicked():
                    btn.setEnabled(False)
                    btn.setText("⏳ 正在安装中...")
                    worker = SkillPipInstallWorker(packages=missing, parent=self)
                    self._pip_worker = worker

                    def on_done(ok: bool, msg: str):
                        self._render_requirements(skill_name)

                    worker.finished.connect(on_done)
                    worker.start()

                btn.clicked.connect(on_install_clicked)
                self.btn_install_deps = btn
                self.env_container_layout.addWidget(btn)
            else:
                self.btn_install_deps = None
                self.env_info_label.setText(f"✓ 所有 {len(satisfied)} 项依赖均已满足！")
                self.env_info_label.setStyleSheet("color: #34C759; font-weight: 500;")

            for pkg in satisfied:
                lbl = QLabel(f"✓ {pkg}", self.env_container)
                lbl.setStyleSheet("font-size: 11px; color: #34C759;")
                self.env_container_layout.addWidget(lbl)

            for pkg in missing:
                lbl = QLabel(f"✕ {pkg} (未安装)", self.env_container)
                lbl.setStyleSheet("font-size: 11px; color: #FF3B30; font-weight: 600;")
                self.env_container_layout.addWidget(lbl)

        except Exception as e:
            self.btn_install_deps = None
            self.env_info_label.setText(f"诊断失败: {e}")
            self.env_info_label.setStyleSheet("color: #86868B;")

    def _render_roles(self, skill: Skill) -> None:
        while self.roles_container_layout.count():
            item = self.roles_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        role_objs = []
        if hasattr(self.role_registry, "get_all_roles"):
            role_objs = list(self.role_registry.get_all_roles().values())
        if not role_objs and hasattr(self.role_registry, "list_roles"):
            for rid in self.role_registry.list_roles():
                r = self.role_registry.get_role(rid) if hasattr(self.role_registry, "get_role") else None
                if r:
                    role_objs.append(r)

        if not role_objs:
            empty_lbl = QLabel("当前未检测到已注册的专家角色", self.roles_container)
            empty_lbl.setStyleSheet("color: #86868B; font-size: 12px;")
            self.roles_container_layout.addWidget(empty_lbl)
            return

        bound_roles = getattr(skill.metadata, "bound_roles", []) or []

        for role in role_objs:
            row_frame = QFrame(self.roles_container)
            row_frame.setStyleSheet("""
                QFrame {
                    background-color: #F8F9FA;
                    border: 1px solid rgba(0, 0, 0, 0.06);
                    border-radius: 6px;
                    padding: 4px 8px;
                }
            """)
            r_layout = QHBoxLayout(row_frame)
            r_layout.setContentsMargins(4, 4, 4, 4)
            r_layout.setSpacing(8)

            role_id = getattr(role, "id", None) or getattr(role, "role_id", str(role))
            role_name = getattr(role, "name", role_id)
            chk = QCheckBox(f"🤖 {role_name} ({role_id})", row_frame)
            is_bound = (role_id in bound_roles) or (skill.metadata.name in getattr(role, "skills", []))
            chk.setChecked(is_bound)
            chk.setStyleSheet("font-size: 12px; font-weight: 500;")
            chk.toggled.connect(lambda checked, rid=role_id: self._on_role_toggled(rid, checked))
            r_layout.addWidget(chk, 1)

            self.roles_container_layout.addWidget(row_frame)

    def _on_role_toggled(self, role_id: str, checked: bool) -> None:
        if not self.skill:
            return
        skill_name = self.skill.metadata.name
        try:
            if checked:
                self.skill_manager.bind_skill_to_role(role_id, skill_name)
            else:
                self.skill_manager.unbind_skill_from_role(role_id, skill_name)
            self.role_binding_changed.emit(skill_name, role_id, checked)
            logger.info("Toggled role '%s' binding for '%s': %s", role_id, skill_name, checked)
        except Exception as e:
            logger.error("Failed toggling role binding: %s", e)
            QMessageBox.warning(self, "装配失败", f"无法更改角色绑定状态: {e}")

    def _on_update_clicked(self) -> None:
        if not self.skill:
            return
        self.skill_updated.emit(self.skill.metadata.name)

    def _open_in_finder(self) -> None:
        if not self.skill or not self.skill.skill_dir:
            return
        p = Path(self.skill.skill_dir).resolve()
        if p.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _on_remove_clicked(self) -> None:
        if not self.skill:
            return
        name = self.skill.metadata.name
        res = QMessageBox.question(
            self,
            "确认卸载",
            f"确定要卸载并彻底删除技能 '{name}' 吗？此操作无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            try:
                scope = getattr(self.skill, "scope", None)
                self.skill_manager.remove_skill(name, scope=scope)
                self.skill_removed.emit(name)
                self.closed.emit()
            except Exception as e:
                QMessageBox.critical(self, "卸载失败", f"删除技能时发生错误: {e}")
