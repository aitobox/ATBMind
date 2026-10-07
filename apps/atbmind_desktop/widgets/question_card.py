"""
ATBMind QuestionCardWidget
Inline Apple HIG style interactive card item for human-in-the-loop decision questions (ask_question).
Presents multiple choice / multi-select options directly inside the ChatStreamView message flow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from apps.atbmind_desktop.theme import (
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)

logger = logging.getLogger("atbmind.desktop.question_card")

__all__ = ["QuestionCardItem"]


class QuestionCardItem(QFrame):
    """
    Interactive inline decision card item rendered inside ChatStreamView.
    Suspends execution until the user selects and submits their choices.
    """

    submitted = Signal(object)  # Emits list of answer strings or dict

    def __init__(
        self,
        question_data: Dict[str, Any],
        response_future: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.question_data = question_data or {}
        self.response_future = response_future
        self._is_submitted = False
        self._question_widgets: List[Dict[str, Any]] = []

        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QuestionCardItem {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-left: 4px solid {ThemeColors.PRIMARY};
                border-radius: 12px;
                margin: 8px 20px;
            }}
            QLabel#headerBadge {{
                font-size: 11px;
                font-weight: 700;
                color: {ThemeColors.PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel#headerAction {{
                font-size: 12px;
                color: {ThemeColors.TEXT_MUTED};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel#questionTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
                padding-top: 4px;
            }}
            QRadioButton, QCheckBox {{
                font-size: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
                spacing: 8px;
                padding: 3px 0;
            }}
            QRadioButton:hover, QCheckBox:hover {{
                color: {ThemeColors.PRIMARY};
            }}
            QLineEdit {{
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                background: #F9FAFB;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
                background: #FFFFFF;
            }}
            QPushButton#submitBtn {{
                background-color: {ThemeColors.PRIMARY};
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 16px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton#submitBtn:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton#submitBtn:disabled {{
                background-color: #E5E7EB;
                color: #9CA3AF;
            }}
            QLabel#statusLabel {{
                font-size: 12px;
                font-weight: 500;
                color: #059669;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        badge_lbl = QLabel("🤖 智能决策确认")
        badge_lbl.setObjectName("headerBadge")
        header_layout.addWidget(badge_lbl)

        action_text = (
            self.question_data.get("tool_action")
            or self.question_data.get("toolAction")
            or self.question_data.get("tool_summary")
            or self.question_data.get("toolSummary")
            or ""
        )
        if action_text:
            action_lbl = QLabel(f"•  {action_text}")
            action_lbl.setObjectName("headerAction")
            header_layout.addWidget(action_lbl)

        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        # 2. Questions List
        questions_raw = self.question_data.get("questions") or []
        if isinstance(questions_raw, dict):
            questions_raw = [questions_raw]

        for q_idx, q_item in enumerate(questions_raw, start=1):
            if not isinstance(q_item, dict):
                continue

            q_text = str(q_item.get("question", "")).strip()
            is_multi = bool(q_item.get("is_multi_select") or q_item.get("isMultiSelect", False))
            options = list(q_item.get("options") or [])

            q_lbl = QLabel(f"{q_idx}. {q_text}" if len(questions_raw) > 1 else q_text)
            q_lbl.setObjectName("questionTitle")
            q_lbl.setWordWrap(True)
            layout.addWidget(q_lbl)

            q_record: Dict[str, Any] = {
                "question": q_text,
                "is_multi": is_multi,
                "buttons": [],
                "button_group": None,
                "custom_edit": None,
            }

            if not is_multi:
                group = QButtonGroup(self)
                q_record["button_group"] = group

            for opt_idx, opt_text in enumerate(options):
                opt_str = str(opt_text).strip()
                if is_multi:
                    btn = QCheckBox(opt_str, self)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    if "(recommended)" in opt_str.lower() or "(推荐)" in opt_str:
                        btn.setChecked(True)
                else:
                    btn = QRadioButton(opt_str, self)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    q_record["button_group"].addButton(btn, opt_idx)
                    if opt_idx == 0 or "(recommended)" in opt_str.lower() or "(推荐)" in opt_str:
                        btn.setChecked(True)

                q_record["buttons"].append(btn)
                layout.addWidget(btn)

            # Custom answer input
            custom_edit = QLineEdit(self)
            custom_edit.setPlaceholderText("可在此补充或输入其他具体要求（可选）...")
            q_record["custom_edit"] = custom_edit
            layout.addWidget(custom_edit)

            self._question_widgets.append(q_record)

        # 3. Footer Action Bar
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(10)

        self.submit_btn = QPushButton("确认并继续")
        self.submit_btn.setObjectName("submitBtn")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.clicked.connect(self._on_submit)
        footer_layout.addWidget(self.submit_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("statusLabel")
        self.status_lbl.hide()
        footer_layout.addWidget(self.status_lbl)

        footer_layout.addStretch(1)
        layout.addLayout(footer_layout)

    def _on_submit(self) -> None:
        if self._is_submitted:
            return

        answers: List[str] = []
        for q_idx, qw in enumerate(self._question_widgets, start=1):
            chosen = []
            if qw["is_multi"]:
                for btn in qw["buttons"]:
                    if btn.isChecked():
                        chosen.append(btn.text())
            else:
                for btn in qw["buttons"]:
                    if btn.isChecked():
                        chosen.append(btn.text())
                        break

            custom_val = qw["custom_edit"].text().strip()
            if custom_val:
                chosen.append(f"Custom: {custom_val}")

            ans_text = " | ".join(chosen) if chosen else "None selected"
            prefix = f"A{q_idx}: " if len(self._question_widgets) > 1 else ""
            answers.append(f"{prefix}{ans_text}")

        final_response = answers[0] if len(answers) == 1 else answers

        self._is_submitted = True
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("已提交")

        for qw in self._question_widgets:
            for btn in qw["buttons"]:
                btn.setEnabled(False)
            qw["custom_edit"].setEnabled(False)

        self.status_lbl.setText("✅ 已提交反馈并恢复执行")
        self.status_lbl.show()

        # Resolve async future if provided
        if self.response_future is not None and not self.response_future.done():
            try:
                loop = self.response_future.get_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(self.response_future.set_result, final_response)
                else:
                    self.response_future.set_result(final_response)
            except Exception as e:
                logger.debug("Failed setting future in thread-safe loop: %s", e)
                try:
                    self.response_future.set_result(final_response)
                except Exception:
                    pass

        self.submitted.emit(final_response)
