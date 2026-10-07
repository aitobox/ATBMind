"""
ATBMind ArtifactViewerDialog
Adheres to Apple HIG and Antigravity artifact preview paradigms.
Provides rich Markdown rendering, unified diff comparison, raw content inspection,
and interactive RequestFeedback approval gates (Proceed / Revise).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from apps.atbmind_desktop.theme import (
    SLIM_SCROLLBAR_QSS,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)


class ArtifactViewerDialog(QDialog):
    """
    Antigravity Artifact Preview and Feedback Dialog.
    Displays artifact metadata, rendered markdown, syntax/diff comparisons,
    and handles interactive 'Proceed' feedback loops.
    """

    proceed_requested = Signal(str)            # artifact_id
    revise_requested = Signal(str, str)        # artifact_id, feedback_text

    def __init__(self, artifact: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.artifact = dict(artifact)
        self.artifact_id = str(self.artifact.get("artifact_id", ""))
        self.title = str(self.artifact.get("title", "Artifact"))
        self.summary = str(self.artifact.get("summary", ""))
        self.file_path = str(self.artifact.get("file_path", ""))
        self.version = int(self.artifact.get("version", 1))
        self.content = str(self.artifact.get("content", ""))
        self.diff = str(self.artifact.get("diff", ""))
        self.request_feedback = bool(self.artifact.get("request_feedback", False))

        # If content is empty but file_path exists on disk, load from disk
        if not self.content and self.file_path and os.path.exists(self.file_path):
            try:
                self.content = Path(self.file_path).read_text(encoding="utf-8", errors="replace")
            except Exception:
                self.content = ""

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(f"工件预览: {self.title} (v{self.version})")
        self.resize(840, 640)
        self.setMinimumSize(640, 480)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_WINDOW};
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QTabWidget::pane {{
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                background: #FFFFFF;
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 14px;
                margin-right: 4px;
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QTabBar::tab:selected {{
                background: #FFFFFF;
                border-color: {ThemeColors.BORDER_SUBTLE};
                color: {ThemeColors.TEXT_PRIMARY};
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                background: rgba(0, 0, 0, 0.04);
            }}
            {SLIM_SCROLLBAR_QSS}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 1. Header Information Block
        header_card = QFrame(self)
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        icon_label = QLabel("📦", header_card)
        icon_label.setStyleSheet("font-size: 18px;")
        title_row.addWidget(icon_label)

        self.title_label = QLabel(self.title, header_card)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: 700;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        title_row.addWidget(self.title_label)

        self.badge_ver = QLabel(f"v{self.version}", header_card)
        self.badge_ver.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(0, 122, 255, 0.10);
                color: {ThemeColors.PRIMARY};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        title_row.addWidget(self.badge_ver)
        title_row.addStretch(1)

        h_layout.addLayout(title_row)

        if self.file_path:
            path_label = QLabel(f"📄 {self.file_path}", header_card)
            path_label.setToolTip(self.file_path)
            path_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 11px;
                    color: {ThemeColors.TEXT_MUTED};
                    font-family: {ThemeFonts.FONT_MONO};
                }}
            """)
            h_layout.addWidget(path_label)

        if self.summary:
            summary_label = QLabel(self.summary, header_card)
            summary_label.setWordWrap(True)
            summary_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 12px;
                    color: {ThemeColors.TEXT_SECONDARY};
                    font-family: {ThemeFonts.FONT_STACK};
                }}
            """)
            h_layout.addWidget(summary_label)

        layout.addWidget(header_card)

        # 2. Tab Widget: Markdown Rendered, Unified Diff, Raw Source
        self.tabs = QTabWidget(self)

        # Tab 1: Rendered View
        self.browser_render = QTextBrowser(self.tabs)
        self.browser_render.setOpenExternalLinks(True)
        self.browser_render.setMarkdown(self.content or "*(空工件内容)*")
        self.browser_render.setStyleSheet(f"""
            QTextBrowser {{
                background: #FFFFFF;
                border: none;
                padding: 16px;
                font-size: 13px;
                line-height: 1.6;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        self.tabs.addTab(self.browser_render, "📄 渲染预览")

        # Tab 2: Unified Diff (if diff available or fallback)
        if self.diff:
            self.browser_diff = QTextBrowser(self.tabs)
            self._render_diff(self.diff)
            self.tabs.addTab(self.browser_diff, "🔄 变更对比 (Diff)")

        # Tab 3: Raw Source
        self.browser_raw = QTextBrowser(self.tabs)
        self.browser_raw.setPlainText(self.content)
        self.browser_raw.setStyleSheet(f"""
            QTextBrowser {{
                background: #FAF9F6;
                border: none;
                padding: 12px;
                font-size: 12px;
                font-family: {ThemeFonts.FONT_MONO};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        self.tabs.addTab(self.browser_raw, "📝 源码")

        layout.addWidget(self.tabs, 1)

        # 3. Interactive Footer Bar
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 4, 0, 0)
        footer_row.setSpacing(10)

        if self.request_feedback:
            # Feedback prompt input
            self.input_feedback = QLineEdit(self)
            self.input_feedback.setPlaceholderText("填写修改意见（若需要微调）...")
            self.input_feedback.setStyleSheet(f"""
                QLineEdit {{
                    background: #FFFFFF;
                    border: 1px solid {ThemeColors.BORDER_SUBTLE};
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 12px;
                    color: {ThemeColors.TEXT_PRIMARY};
                }}
                QLineEdit:focus {{
                    border-color: {ThemeColors.PRIMARY};
                }}
            """)
            footer_row.addWidget(self.input_feedback, 1)

            # Proceed Button (Primary Action)
            self.btn_proceed = QPushButton("✓ 采纳并执行 (Proceed)", self)
            self.btn_proceed.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_proceed.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ThemeColors.PRIMARY};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 600;
                    font-family: {ThemeFonts.FONT_STACK};
                }}
                QPushButton:hover {{
                    background-color: {ThemeColors.PRIMARY_HOVER};
                }}
            """)
            self.btn_proceed.clicked.connect(self._on_proceed_clicked)
            footer_row.addWidget(self.btn_proceed)

            # Revise Button
            self.btn_revise = QPushButton("✎ 反馈修订", self)
            self.btn_revise.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_revise.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    color: {ThemeColors.TEXT_PRIMARY};
                    border: 1px solid {ThemeColors.BORDER_SUBTLE};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {ThemeColors.BG_INPUT};
                }}
            """)
            self.btn_revise.clicked.connect(self._on_revise_clicked)
            footer_row.addWidget(self.btn_revise)
        else:
            footer_row.addStretch(1)

        # Close Button
        btn_close = QPushButton("关闭", self)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                color: {ThemeColors.TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: rgba(0, 0, 0, 0.05);
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        footer_row.addWidget(btn_close)

        layout.addLayout(footer_row)

    def _render_diff(self, diff_text: str) -> None:
        """Formats unified diff text with Apple-style syntax highlights."""
        self.browser_diff.clear()
        self.browser_diff.setStyleSheet(f"""
            QTextBrowser {{
                background: #FAF9F6;
                border: none;
                padding: 12px;
                font-size: 12px;
                font-family: {ThemeFonts.FONT_MONO};
            }}
        """)
        cursor = self.browser_diff.textCursor()
        for line in diff_text.splitlines():
            fmt = QTextCharFormat()
            if line.startswith("+"):
                fmt.setForeground(QColor(ThemeColors.SUCCESS))
                fmt.setBackground(QColor(ThemeColors.SUCCESS_LIGHT))
            elif line.startswith("-"):
                fmt.setForeground(QColor(ThemeColors.ERROR))
                fmt.setBackground(QColor(ThemeColors.ERROR_BG))
            elif line.startswith("@@"):
                fmt.setForeground(QColor(ThemeColors.PRIMARY))
                fmt.setFontWeight(QFont.Weight.Bold)
            else:
                fmt.setForeground(QColor(ThemeColors.TEXT_MUTED))

            cursor.insertText(line + "\n", fmt)

    def _on_proceed_clicked(self) -> None:
        self.proceed_requested.emit(self.artifact_id)
        self.accept()

    def _on_revise_clicked(self) -> None:
        fb_text = self.input_feedback.text().strip() if hasattr(self, "input_feedback") else ""
        self.revise_requested.emit(self.artifact_id, fb_text)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
