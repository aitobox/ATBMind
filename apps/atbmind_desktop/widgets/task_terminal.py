"""
ATBMind TaskTerminalDialog
Interactive task terminal inspector dialog adhering to Apple Human Interface Guidelines.
Enables viewing live streaming process logs, sending stdin, and cleanly terminating background tasks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from apps.atbmind_desktop.theme import (
    ThemeColors,
    ThemeFonts,
    SLIM_SCROLLBAR_QSS,
)


class TaskTerminalDialog(QDialog):
    """
    Interactive process terminal dialog for inspecting background tasks.
    Displays streaming stdout/stderr, supports stdin interaction and process termination.
    """

    kill_requested = Signal(str)
    input_submitted = Signal(str, str)

    def __init__(self, task_info: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task_info = dict(task_info)
        self.task_id = str(self.task_info.get("id", self.task_info.get("task_id", "")))
        self.task_name = str(self.task_info.get("name", self.task_info.get("command", self.task_id)))
        self.status = str(self.task_info.get("status", "running")).lower()
        self.output = str(self.task_info.get("output", ""))

        self._init_ui()
        self._load_initial_logs()

    def _init_ui(self) -> None:
        self.setWindowTitle(f"任务终端: {self.task_name}")
        self.resize(780, 540)
        self.setMinimumSize(600, 400)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_WINDOW};
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            {SLIM_SCROLLBAR_QSS}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 1. Header Information Card
        header_card = QFrame(self)
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(8)

        icon_label = QLabel("⚡", header_card)
        icon_label.setStyleSheet("font-size: 16px;")
        h_layout.addWidget(icon_label)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)

        name_label = QLabel(self.task_name, header_card)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        info_box.addWidget(name_label)

        self.id_label = QLabel(f"ID: {self.task_id}", header_card)
        self.id_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_MONO};
            }}
        """)
        info_box.addWidget(self.id_label)
        h_layout.addLayout(info_box)

        h_layout.addStretch(1)

        self.badge_status = QLabel(self.status.upper(), header_card)
        self._update_badge_style()
        h_layout.addWidget(self.badge_status)

        layout.addWidget(header_card)

        # 2. Terminal Output Browser
        self.browser_terminal = QTextBrowser(self)
        self.browser_terminal.setOpenExternalLinks(True)
        self.browser_terminal.setStyleSheet(f"""
            QTextBrowser {{
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.4;
                font-family: {ThemeFonts.FONT_MONO};
            }}
        """)
        layout.addWidget(self.browser_terminal, 1)

        # 3. Interactive Input Bar (stdin)
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.stdin_edit = QLineEdit(self)
        self.stdin_edit.setPlaceholderText("输入标准输入 (stdin)...")
        self.stdin_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-family: {ThemeFonts.FONT_MONO};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.stdin_edit.returnPressed.connect(self._on_send_stdin)
        input_row.addWidget(self.stdin_edit, 1)

        self.btn_send = QPushButton("发送", self)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
        """)
        self.btn_send.clicked.connect(self._on_send_stdin)
        input_row.addWidget(self.btn_send)

        layout.addLayout(input_row)

        # 4. Action Toolbar (Kill, Refresh, Close)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_kill = QPushButton("终止任务", self)
        self.btn_kill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_kill.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.ERROR};
                border: 1px solid {ThemeColors.ERROR};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.ERROR_BG};
            }}
        """)
        self.btn_kill.clicked.connect(self._on_kill_task)
        toolbar.addWidget(self.btn_kill)

        btn_refresh = QPushButton("刷新日志", self)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_INPUT};
            }}
        """)
        btn_refresh.clicked.connect(self._load_initial_logs)
        toolbar.addWidget(btn_refresh)

        toolbar.addStretch(1)

        btn_close = QPushButton("关闭", self)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 12px;
                color: {ThemeColors.TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: rgba(0, 0, 0, 0.05);
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        toolbar.addWidget(btn_close)

        layout.addLayout(toolbar)

    def _update_badge_style(self) -> None:
        st = self.status.lower()
        if st in ("running", "active"):
            bg = "rgba(52, 199, 89, 0.15)"
            color = ThemeColors.SUCCESS
        elif st in ("done", "completed", "success"):
            bg = "rgba(0, 122, 255, 0.12)"
            color = ThemeColors.PRIMARY
        elif st in ("failed", "error", "killed"):
            bg = "rgba(255, 59, 48, 0.15)"
            color = ThemeColors.ERROR
        else:
            bg = "rgba(0, 0, 0, 0.08)"
            color = ThemeColors.TEXT_MUTED

        self.badge_status.setText(st.upper())
        self.badge_status.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 700;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)

    def _load_initial_logs(self) -> None:
        """Loads log content from disk log file or in-memory output buffer."""
        log_file = Path("data/tasks") / f"{self.task_id}.log"
        content = ""
        if log_file.exists():
            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
        if not content and self.output:
            content = self.output

        if content:
            self.browser_terminal.setPlainText(content)
            self._scroll_to_bottom()

    def append_output(self, chunk: str) -> None:
        """Appends new streaming output chunk and scrolls to bottom."""
        if not chunk:
            return
        cursor = self.browser_terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.browser_terminal.setTextCursor(cursor)
        self._scroll_to_bottom()

    def set_status(self, status: str, summary: str = "") -> None:
        """Updates task status badge and state."""
        self.status = status
        self._update_badge_style()
        if summary:
            self.id_label.setText(f"ID: {self.task_id}  ({summary})")

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.browser_terminal.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _on_send_stdin(self) -> None:
        text = self.stdin_edit.text()
        if not text:
            return
        if not text.endswith("\n"):
            text += "\n"
        self.input_submitted.emit(self.task_id, text)
        self.stdin_edit.clear()

    def _on_kill_task(self) -> None:
        self.kill_requested.emit(self.task_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
