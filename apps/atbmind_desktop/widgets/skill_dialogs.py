"""
ATBMind Skill Dialogs: GitHubImportDialog, NewSkillDialog, and LocalImportDialog
Native Apple HIG modal dialogs for adding and creating skills.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Literal, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.skills.manager import SkillManager, parse_github_url
from atbmind_core.skills.schema import Skill
from apps.atbmind_desktop.icons import get_apple_icon
from apps.atbmind_desktop.theme import (
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)
from apps.atbmind_desktop.widgets.sidebar import LoadingSpinner

logger = logging.getLogger(__name__)


class GitHubImportDialog(QDialog):
    """
    Apple HIG modal dialog for importing skills from GitHub repositories or subpaths.
    Features:
    - Real-time URL format parsing and validation preview
    - Scope selection (Global vs Project)
    - Overwrite checkbox
    - Inline progress status
    """

    import_requested = Signal(str, str, str, bool)  # url, scope, name, overwrite

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("从 GitHub 导入技能")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._parsed_target: Optional[dict] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_WINDOW};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel {{
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        title_label = QLabel("导入 GitHub 技能", self)
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {ThemeColors.TEXT_PRIMARY};
        """)
        layout.addWidget(title_label)

        sub_label = QLabel("支持完整仓库、子目录路径（tree/main/...）或简写格式 (owner/repo)", self)
        sub_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(sub_label)

        # URL Input
        url_header = QLabel("仓库地址 (URL 或 owner/repo):", self)
        url_header.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(url_header)

        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("https://github.com/owner/repo/tree/main/skills/subpath")
        self.url_input.textChanged.connect(self._on_url_changed)
        layout.addWidget(self.url_input)

        # Validation Preview Card
        self.preview_card = QFrame(self)
        self.preview_card.setStyleSheet(f"""
            QFrame {{
                background-color: #F8F9FA;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(4)

        self.preview_label = QLabel("请输入有效的 GitHub 地址", self.preview_card)
        self.preview_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_card)

        # Scope Selection
        scope_header = QLabel("安装目标范围:", self)
        scope_header.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(scope_header)

        scope_layout = QHBoxLayout()
        scope_layout.setSpacing(16)
        self.radio_global = QRadioButton("全局库 (Global: ~/.atbmind/skills)", self)
        self.radio_global.setChecked(True)
        self.radio_project = QRadioButton("项目内置 (Project: ./skills)", self)
        scope_layout.addWidget(self.radio_global)
        scope_layout.addWidget(self.radio_project)
        scope_layout.addStretch(1)
        layout.addLayout(scope_layout)

        # Overwrite option & Local link
        opts_row = QHBoxLayout()
        opts_row.setContentsMargins(0, 0, 0, 0)
        self.chk_overwrite = QCheckBox("覆盖已存在的同名技能 (Overwrite)", self)
        self.chk_overwrite.setStyleSheet("font-size: 12px;")
        opts_row.addWidget(self.chk_overwrite)
        opts_row.addStretch(1)

        self.btn_local_link = QPushButton("📁 从本地目录或 ZIP 导入...", self)
        self.btn_local_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_local_link.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {ThemeColors.PRIMARY};
                font-size: 12px;
                text-decoration: underline;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {ThemeColors.PRIMARY_HOVER};
            }}
        """)
        self.btn_local_link.clicked.connect(self._on_local_link_clicked)
        opts_row.addWidget(self.btn_local_link)
        layout.addLayout(opts_row)

        # Progress / Status indicator
        self.status_layout = QHBoxLayout()
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(8)

        self.spinner = LoadingSpinner(self, size=16)
        self.status_layout.addWidget(self.spinner)
        self.spinner.stop()

        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        self.status_layout.addWidget(self.status_label, 1)
        layout.addLayout(self.status_layout)

        layout.addSpacing(6)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton("取消", self)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SIDEBAR_HOVER};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_import = QPushButton("导入", self)
        self.btn_import.setEnabled(False)
        self.btn_import.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #D2D2D7;
                color: #8E8E93;
            }}
        """)
        self.btn_import.clicked.connect(self._on_import_clicked)
        btn_row.addWidget(self.btn_import)

        layout.addLayout(btn_row)

    def _on_url_changed(self, text: str) -> None:
        raw = text.strip()
        if not raw:
            self.preview_label.setText("请输入有效的 GitHub 地址")
            self.preview_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
            self.btn_import.setEnabled(False)
            self._parsed_target = None
            return

        try:
            info = parse_github_url(raw)
            repo_url = info["clone_url"]
            repo_name = info["repo"]
            branch = info["branch"]
            subpath = info["subpath"]
            target_name = Path(subpath).name if subpath else repo_name

            msg = f"✓ 识别成功: 仓库 <b>{repo_name}</b> | 分支: <b>{branch}</b>"
            if subpath:
                msg += f" | 子目录: <b>{subpath}</b>"
            msg += f" | 技能名称: <b>{target_name}</b>"

            self.preview_label.setText(msg)
            self.preview_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.PRIMARY};")
            self.btn_import.setEnabled(True)
            self._parsed_target = {
                "repo_url": repo_url,
                "branch": branch,
                "subpath": subpath,
                "skill_name": target_name,
            }
        except Exception:
            self.preview_label.setText("⚠️ 无法识别的 GitHub 地址格式，请检查输入的 URL")
            self.preview_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.ERROR};")
            self.btn_import.setEnabled(False)
            self._parsed_target = None

    def _on_import_clicked(self) -> None:
        if not self._parsed_target:
            return
        scope = "global" if self.radio_global.isChecked() else "project"
        name = self._parsed_target.get("skill_name") or ""
        overwrite = self.chk_overwrite.isChecked()
        self.import_requested.emit(self.url_input.text().strip(), scope, name, overwrite)
        self.accept()

    def _on_local_link_clicked(self) -> None:
        local_dlg = LocalImportDialog(self)
        local_dlg.import_requested.connect(self._handle_local_import_forward)
        local_dlg.accepted.connect(self.accept)
        local_dlg.open()

    def _handle_local_import_forward(self, path: str, scope: str, name: str, overwrite: bool) -> None:
        self.import_requested.emit(path, scope, name, overwrite)

    def set_loading(self, loading: bool, message: str = "") -> None:
        """Sets loading spinner and disable actions during async operation."""
        if loading:
            self.spinner.start()
            self.status_label.setText(message)
            self.btn_import.setEnabled(False)
        else:
            self.spinner.stop()
            self.status_label.setText(message)
            self.btn_import.setEnabled(bool(self._parsed_target))


class NewSkillDialog(QDialog):
    """
    Apple HIG modal dialog for scaffolding a new custom skill.
    Features:
    - Identifier name sanitation and validation
    - Description and tag pill inputs
    - With Tools checkbox (Python AgentTool)
    - Live preview of generated SKILL.md and tools.py
    """

    create_requested = Signal(str, str, list, bool, str)  # name, desc, tags, with_tools, scope

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("创建新技能")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_WINDOW};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel {{
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header Title
        title_label = QLabel("新建标准化技能包", self)
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {ThemeColors.TEXT_PRIMARY};
        """)
        layout.addWidget(title_label)

        # Name Input
        name_label = QLabel("技能名称 (英文小写、数字、下划线或减号):", self)
        name_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(name_label)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("例如: my_expert_skill")
        self.name_input.textChanged.connect(self._update_preview)
        layout.addWidget(self.name_input)

        # Description Input
        desc_label = QLabel("简要描述:", self)
        desc_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(desc_label)

        self.desc_input = QLineEdit(self)
        self.desc_input.setPlaceholderText("例如: 为智能体提供专项操作指引与实用工具")
        self.desc_input.textChanged.connect(self._update_preview)
        layout.addWidget(self.desc_input)

        # Tags Input
        tags_label = QLabel("分类标签 (逗号分隔):", self)
        tags_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(tags_label)

        self.tags_input = QLineEdit(self)
        self.tags_input.setPlaceholderText("例如: productivity, tools, dev")
        self.tags_input.textChanged.connect(self._update_preview)
        layout.addWidget(self.tags_input)

        # Options Row: with tools & scope
        opts_layout = QHBoxLayout()
        self.chk_tools = QCheckBox("包含 Python 工具代码 (AgentTool / tools.py)", self)
        self.chk_tools.setChecked(True)
        self.chk_tools.setStyleSheet("font-size: 12px;")
        self.chk_tools.toggled.connect(self._update_preview)
        opts_layout.addWidget(self.chk_tools)

        opts_layout.addSpacing(20)
        self.radio_global = QRadioButton("全局库 (Global)", self)
        self.radio_global.setChecked(True)
        self.radio_project = QRadioButton("项目内置 (Project)", self)
        opts_layout.addWidget(self.radio_global)
        opts_layout.addWidget(self.radio_project)
        opts_layout.addStretch(1)
        layout.addLayout(opts_layout)

        # Tabs Live Preview
        layout.addSpacing(4)
        preview_title = QLabel("模板即时预览:", self)
        preview_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #86868B;")
        layout.addWidget(preview_title)

        self.tabs = QTabWidget(self)
        self.preview_skill_md = QTextEdit(self)
        self.preview_skill_md.setReadOnly(True)
        self.preview_skill_md.setStyleSheet(f"font-family: {ThemeFonts.FONT_MONO}; font-size: 11px;")
        self.tabs.addTab(self.preview_skill_md, "SKILL.md")

        self.preview_tools_py = QTextEdit(self)
        self.preview_tools_py.setReadOnly(True)
        self.preview_tools_py.setStyleSheet(f"font-family: {ThemeFonts.FONT_MONO}; font-size: 11px;")
        self.tabs.addTab(self.preview_tools_py, "tools.py")
        layout.addWidget(self.tabs, 1)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton("取消", self)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_create = QPushButton("创建", self)
        self.btn_create.setEnabled(False)
        self.btn_create.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #D2D2D7;
                color: #8E8E93;
            }}
        """)
        self.btn_create.clicked.connect(self._on_create_clicked)
        btn_row.addWidget(self.btn_create)

        layout.addLayout(btn_row)

        self._update_preview()

    def _update_preview(self) -> None:
        raw_name = self.name_input.text().strip()
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_name)
        desc = self.desc_input.text().strip() or f"Domain guidelines for {clean_name or 'my_skill'}"
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()] or ["custom"]
        with_tools = self.chk_tools.isChecked()

        is_valid = bool(clean_name and len(clean_name) >= 2)
        self.btn_create.setEnabled(is_valid)

        display_name = clean_name or "my_skill"
        md_text = f"""---
name: {display_name}
description: "{desc}"
version: 1.0.0
tags: {tags}
author: "ATBMind User"
enabled: true
bound_roles: []
---

# {display_name}

## Overview
{desc}

## Instructions & Best Practices
- Guideline 1: Carefully verify parameters before action.
- Guideline 2: Ensure structured responses.
"""
        self.preview_skill_md.setPlainText(md_text)

        if with_tools:
            tool_py = f'''"""
Executable tools exported by skill {display_name}.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from atbmind_core.harness.tools.base import AgentTool, ToolResult


class {display_name.capitalize()}Input(BaseModel):
    query: str = Field(default="", description="Query parameter")


class {display_name.capitalize()}Tool(AgentTool):
    name = "{display_name.replace('-', '_')}_action"
    description = "Action tool provided by skill {display_name}"
    parameters_schema = {display_name.capitalize()}Input

    async def execute(self, args: Any, context: Optional[Any] = None) -> ToolResult:
        return ToolResult(content="Success", is_error=False)
'''
            self.preview_tools_py.setPlainText(tool_py)
            self.tabs.setTabEnabled(1, True)
        else:
            self.preview_tools_py.setPlainText("# 纯指南类技能（未启用 tools.py）")
            self.tabs.setTabEnabled(1, False)

    def _on_create_clicked(self) -> None:
        raw_name = self.name_input.text().strip()
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_name)
        if not clean_name:
            return
        desc = self.desc_input.text().strip()
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        with_tools = self.chk_tools.isChecked()
        scope = "global" if self.radio_global.isChecked() else "project"
        self.create_requested.emit(clean_name, desc, tags, with_tools, scope)
        self.accept()


class LocalImportDialog(QDialog):
    """
    Apple HIG modal dialog for importing local directories or ZIP archives.
    """

    import_requested = Signal(str, str, str, bool)  # path, scope, skill_name, overwrite

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("从本地导入技能")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_WINDOW};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title_label = QLabel("从本地文件/文件夹导入", self)
        title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title_label)

        sub_label = QLabel("选择包含 SKILL.md 的本地目录，或包含技能包的 .zip 压缩文件", self)
        sub_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(sub_label)

        # File Chooser Row
        path_header = QLabel("本地路径 (目录或 .zip):", self)
        path_header.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(path_header)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit(self)
        self.path_input.setPlaceholderText("/path/to/skill_folder 或 /path/to/skill.zip")
        self.path_input.textChanged.connect(self._validate)
        path_row.addWidget(self.path_input, 1)

        self.btn_browse = QPushButton("浏览...", self)
        self.btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
            }}
        """)
        self.btn_browse.clicked.connect(self._browse_path)
        path_row.addWidget(self.btn_browse)
        layout.addLayout(path_row)

        # Scope
        scope_header = QLabel("安装目标范围:", self)
        scope_header.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(scope_header)

        scope_layout = QHBoxLayout()
        self.radio_global = QRadioButton("全局库 (Global: ~/.atbmind/skills)", self)
        self.radio_global.setChecked(True)
        self.radio_project = QRadioButton("项目内置 (Project: ./skills)", self)
        scope_layout.addWidget(self.radio_global)
        scope_layout.addWidget(self.radio_project)
        scope_layout.addStretch(1)
        layout.addLayout(scope_layout)

        self.chk_overwrite = QCheckBox("覆盖已存在的同名技能 (Overwrite)", self)
        layout.addWidget(self.chk_overwrite)

        layout.addSpacing(10)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton("取消", self)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_import = QPushButton("导入", self)
        self.btn_import.setEnabled(False)
        self.btn_import.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #D2D2D7;
                color: #8E8E93;
            }}
        """)
        self.btn_import.clicked.connect(self._on_import_clicked)
        btn_row.addWidget(self.btn_import)

        layout.addLayout(btn_row)

    def _browse_path(self) -> None:
        # Choose folder or zip
        path, _ = QFileDialog.getOpenFileName(
            self, "选择技能压缩包", "", "ZIP Archives (*.zip);;All Files (*)"
        )
        if not path:
            path = QFileDialog.getExistingDirectory(self, "选择技能目录")
        if path:
            self.path_input.setText(path)

    def _validate(self, text: str) -> None:
        p = Path(text.strip())
        self.btn_import.setEnabled(p.exists())

    def _on_import_clicked(self) -> None:
        src = self.path_input.text().strip()
        if not src:
            return
        scope = "global" if self.radio_global.isChecked() else "project"
        overwrite = self.chk_overwrite.isChecked()
        self.import_requested.emit(src, scope, "", overwrite)
        self.accept()
