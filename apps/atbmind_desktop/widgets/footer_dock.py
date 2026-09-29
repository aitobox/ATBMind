"""
ATBMind FooterDock
Pluggable docked footer container featuring dynamic plugin control bar,
style selection popover, attachment chip, and auto-resizing prompt input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from plugins.draw.plugin import (
    DRAW_UI_ASPECT_RATIOS,
    DRAW_UI_MODELS,
    DRAW_UI_STYLES,
)


class AutoResizingTextEdit(QTextEdit):
    """
    QTextEdit that auto-adjusts its height between min_height and max_height based on content.
    Enter sends; Shift+Enter creates a new line.
    """

    submit_pressed = Signal()

    def __init__(
        self,
        min_height: int = 40,
        max_height: int = 120,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.min_height = min_height
        self.max_height = max_height
        self.setPlaceholderText("输入描述或人像修图意图 (Enter 发送，Shift+Enter 换行)...")
        self.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                font-size: 14px;
                color: #1d1d1f;
                padding: 4px 6px;
            }
        """)
        self.setFixedHeight(self.min_height)
        self.textChanged.connect(self._adjust_height)

    def _adjust_height(self) -> None:
        doc: QTextDocument = self.document()
        doc_height = int(doc.size().height()) + 14
        new_height = max(self.min_height, min(doc_height, self.max_height))
        if self.height() != new_height:
            self.setFixedHeight(new_height)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.submit_pressed.emit()
        else:
            super().keyPressEvent(event)


class AttachmentChip(QFrame):
    """Miniature attachment chip showing file name with an ✕ remove button."""

    remove_requested = Signal()

    def __init__(self, file_path: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file_path = file_path
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            AttachmentChip {
                background-color: #f2f2f7;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
            }
            QLabel {
                font-size: 11px;
                color: #1d1d1f;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #86868b;
                font-size: 11px;
                font-weight: bold;
                padding: 0 4px;
            }
            QPushButton:hover {
                color: #ff3b30;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        name = Path(self.file_path).name
        label = QLabel(f"🖼️ {name}")
        layout.addWidget(label)

        del_btn = QPushButton("✕")
        del_btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(del_btn)


class FooterDock(QWidget):
    """
    Bottom floating dock for input and dynamic plugin controls.
    """

    submit_requested = Signal(str, str, dict)  # prompt, attachment_path, plugin_state
    plugin_changed = Signal(str, dict)        # plugin_id ("" or "draw"), plugin_state

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.active_plugin_id: Optional[str] = None
        self.attachment_path: Optional[str] = None
        self.current_style_id: str = "portrait"
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            FooterDock {
                background-color: transparent;
            }
            QFrame#outerContainer {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 16px;
            }
            QPushButton#loadPluginBtn {
                background-color: #f2f2f7;
                border: 1px solid #e5e5ea;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton#loadPluginBtn:hover {
                background-color: #e5e5ea;
                border-color: #0071e3;
            }
            QPushButton#capsuleBtn {
                background-color: #e3f2fd;
                border: 1px solid #90caf9;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                color: #0071e3;
                font-weight: 500;
            }
            QPushButton#capsuleBtn:hover {
                background-color: #bbdefb;
            }
            QComboBox {
                background-color: #f5f5f7;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton#styleBtn {
                background-color: #f5f5f7;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton#styleBtn:hover {
                background-color: #e5e5ea;
            }
            QPushButton#attachBtn {
                background-color: #f2f2f7;
                border: 1px solid #d2d2d7;
                border-radius: 16px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
                font-size: 16px;
                color: #1d1d1f;
            }
            QPushButton#attachBtn:hover {
                background-color: #e5e5ea;
            }
            QPushButton#sendBtn {
                background-color: #0071e3;
                border: none;
                border-radius: 16px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
                font-size: 15px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#sendBtn:hover {
                background-color: #0077ed;
            }
        """)

        dock_layout = QVBoxLayout(self)
        dock_layout.setContentsMargins(16, 8, 16, 16)

        # Outer Floating Box
        self.container = QFrame()
        self.container.setObjectName("outerContainer")
        box_layout = QVBoxLayout(self.container)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(8)

        # Upper: Plugin Control Bar
        self.plugin_bar = QWidget()
        self.plugin_layout = QHBoxLayout(self.plugin_bar)
        self.plugin_layout.setContentsMargins(0, 0, 0, 0)
        self.plugin_layout.setSpacing(8)

        # Mode A: Load button
        self.load_plugin_btn = QPushButton("+ 载入插件")
        self.load_plugin_btn.setObjectName("loadPluginBtn")
        self.load_plugin_btn.clicked.connect(self._show_load_menu)
        self.plugin_layout.addWidget(self.load_plugin_btn)

        # Mode B widgets
        self.capsule_btn = QPushButton("🖼️ 图像生成 (ATBDraw) ✕")
        self.capsule_btn.setObjectName("capsuleBtn")
        self.capsule_btn.clicked.connect(self.unload_plugin)
        self.plugin_layout.addWidget(self.capsule_btn)

        # Model Dropdown
        self.model_combo = QComboBox()
        self.model_combo.addItems(DRAW_UI_MODELS)
        self.model_combo.currentIndexChanged.connect(self._on_plugin_param_changed)
        self.plugin_layout.addWidget(self.model_combo)

        # Ratio Dropdown
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(DRAW_UI_ASPECT_RATIOS)
        self.ratio_combo.currentIndexChanged.connect(self._on_plugin_param_changed)
        self.plugin_layout.addWidget(self.ratio_combo)

        # Style Button (Popover Menu)
        self.style_btn = QPushButton("🎨 人像摄影 ▾")
        self.style_btn.setObjectName("styleBtn")
        self.style_btn.clicked.connect(self._show_style_menu)
        self.plugin_layout.addWidget(self.style_btn)

        # Template Dropdown
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "智能全身自然显瘦塑形",
            "双频原生磨皮",
            "面部立体轮廓微雕",
            "服装边缘防畸变锁定",
        ])
        self.template_combo.currentIndexChanged.connect(self._on_plugin_param_changed)
        self.plugin_layout.addWidget(self.template_combo)

        self.plugin_layout.addStretch(1)
        box_layout.addWidget(self.plugin_bar)

        # Lower: Prompt Input Bar
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)
        input_row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # Attachment button
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.clicked.connect(self._on_pick_attachment)
        input_row.addWidget(self.attach_btn)

        # Attachment Chip placeholder container
        self.chip_container = QWidget()
        self.chip_layout = QHBoxLayout(self.chip_container)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        self.chip_container.hide()
        input_row.addWidget(self.chip_container)

        # Input Text Edit
        self.text_edit = AutoResizingTextEdit()
        self.text_edit.submit_pressed.connect(self._on_submit)
        input_row.addWidget(self.text_edit, 1)

        # Send Button
        self.send_btn = QPushButton("↑")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.send_btn)

        box_layout.addLayout(input_row)
        dock_layout.addWidget(self.container)

        # Initialize to plain-text mode
        self._update_plugin_bar_visibility(loaded=False)

    def _update_plugin_bar_visibility(self, loaded: bool) -> None:
        self.load_plugin_btn.setVisible(not loaded)
        self.capsule_btn.setVisible(loaded)
        self.model_combo.setVisible(loaded)
        self.ratio_combo.setVisible(loaded)
        self.style_btn.setVisible(loaded)
        self.template_combo.setVisible(loaded)

    def _show_load_menu(self) -> None:
        menu = QMenu(self)
        act_draw = menu.addAction("🎨 ATBDraw (图像生成)")
        chosen = menu.exec(self.load_plugin_btn.mapToGlobal(self.load_plugin_btn.rect().bottomLeft()))
        if chosen == act_draw:
            self.load_plugin("draw")

    def _show_style_menu(self) -> None:
        menu = QMenu(self)
        for s in DRAW_UI_STYLES:
            act = menu.addAction(f"{s['icon']} {s['name']}")
            act.setData(s['id'])
        chosen = menu.exec(self.style_btn.mapToGlobal(self.style_btn.rect().bottomLeft()))
        if chosen:
            style_id = chosen.data()
            style_name = chosen.text()
            self.current_style_id = style_id
            self.style_btn.setText(f"{style_name} ▾")
            self._on_plugin_param_changed()

    def _on_pick_attachment(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择人像图片",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if file_path:
            self.set_attachment(file_path)

    def set_attachment(self, file_path: Optional[str]) -> None:
        self.attachment_path = file_path
        # Clear existing chips
        while self.chip_layout.count():
            child = self.chip_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if file_path:
            chip = AttachmentChip(file_path)
            chip.remove_requested.connect(self.clear_attachment)
            self.chip_layout.addWidget(chip)
            self.chip_container.show()
        else:
            self.chip_container.hide()

    def clear_attachment(self) -> None:
        self.set_attachment(None)

    def load_plugin(self, plugin_id: str, state: Optional[Dict[str, Any]] = None) -> None:
        self.active_plugin_id = plugin_id
        self._update_plugin_bar_visibility(loaded=True)
        if state:
            self.set_plugin_state(state)
        self.plugin_changed.emit(plugin_id, self.get_plugin_state())

    def unload_plugin(self) -> None:
        self.active_plugin_id = None
        self._update_plugin_bar_visibility(loaded=False)
        self.plugin_changed.emit("", {})

    def get_plugin_state(self) -> Dict[str, Any]:
        if not self.active_plugin_id:
            return {}
        return {
            "model": self.model_combo.currentText(),
            "aspect_ratio": self.ratio_combo.currentText(),
            "style_id": self.current_style_id,
            "template_id": self.template_combo.currentText(),
        }

    def set_plugin_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "model" in state:
            idx = self.model_combo.findText(state["model"])
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        if "aspect_ratio" in state:
            idx = self.ratio_combo.findText(state["aspect_ratio"])
            if idx >= 0:
                self.ratio_combo.setCurrentIndex(idx)
        if "style_id" in state:
            self.current_style_id = state["style_id"]
            # Update style button text
            for s in DRAW_UI_STYLES:
                if s["id"] == self.current_style_id:
                    self.style_btn.setText(f"{s['icon']} {s['name']} ▾")
                    break
        if "template_id" in state:
            idx = self.template_combo.findText(state["template_id"])
            if idx >= 0:
                self.template_combo.setCurrentIndex(idx)

    def _on_plugin_param_changed(self) -> None:
        if self.active_plugin_id:
            self.plugin_changed.emit(self.active_plugin_id, self.get_plugin_state())

    def _on_submit(self) -> None:
        prompt = self.text_edit.toPlainText().strip()
        if not prompt and not self.attachment_path:
            return

        plugin_state = self.get_plugin_state()
        self.submit_requested.emit(prompt, self.attachment_path or "", plugin_state)

        # Clear prompt
        self.text_edit.clear()

    def set_prompt_text(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(self.text_edit.textCursor().MoveOperation.End)
        self.text_edit.setFocus()
