"""
ATBDraw DrawResultCard
Dedicated PySide6 image result comparison card component for ATBDraw.
Renders Before (original) and After (retouched) images side-by-side with 8px rounded corners,
displays metadata bar (elapsed time, template name badge), and provides action buttons.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DrawResultCard(QFrame):
    """
    Dedicated Before/After image comparison result card for ATBDraw results.
    """

    zoom_requested = Signal(str)
    save_requested = Signal(str)
    refine_requested = Signal(str, str)  # after_img_path, prompt_prefix

    def __init__(
        self,
        payload: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.payload = payload or {}
        self.before_path = str(self.payload.get("before_img") or "")
        self.after_path = str(self.payload.get("after_img") or "")
        self.elapsed = float(self.payload.get("elapsed_seconds") or 0.0)
        self.template_name = str(self.payload.get("template_name") or "人像精修")

        self.zoom_btn: Optional[QPushButton] = None
        self.save_btn: Optional[QPushButton] = None
        self.refine_btn: Optional[QPushButton] = None

        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            DrawResultCard {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 12px;
                margin: 6px 16px;
            }
            QLabel {
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton {
                background-color: #f5f5f7;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                color: #1d1d1f;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
                border-color: #0071e3;
            }
            QPushButton#refineBtn {
                background-color: #0071e3;
                color: #ffffff;
                border: none;
                font-weight: 500;
            }
            QPushButton#refineBtn:hover {
                background-color: #0077ed;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Meta Header
        header = QHBoxLayout()
        self.badge = QLabel(f"🎨 ATBDraw: {self.template_name}")
        self.badge.setStyleSheet("font-weight: bold; color: #0071e3; font-size: 13px;")
        header.addWidget(self.badge)

        header.addStretch(1)

        self.time_label = QLabel(f"耗时: {self.elapsed:.1f}s")
        self.time_label.setStyleSheet("color: #86868b;")
        header.addWidget(self.time_label)
        layout.addLayout(header)

        # Images Row (Before / After)
        img_row = QHBoxLayout()
        img_row.setSpacing(14)

        # Before Image Box
        self.before_box = self._create_image_box("原图 (Before)", self.before_path)
        img_row.addWidget(self.before_box)

        # After Image Box
        self.after_box = self._create_image_box("精修效果 (After)", self.after_path)
        img_row.addWidget(self.after_box)

        layout.addLayout(img_row)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.addStretch(1)

        if self.after_path:
            self.zoom_btn = QPushButton("🔍 放大查看")
            self.zoom_btn.setObjectName("zoomBtn")
            self.zoom_btn.clicked.connect(lambda: self.zoom_requested.emit(self.after_path))
            actions_row.addWidget(self.zoom_btn)

            self.save_btn = QPushButton("💾 另存为")
            self.save_btn.setObjectName("saveBtn")
            self.save_btn.clicked.connect(self._on_save_as)
            actions_row.addWidget(self.save_btn)

            self.refine_btn = QPushButton("↺ 以此结果微调")
            self.refine_btn.setObjectName("refineBtn")
            self.refine_btn.clicked.connect(
                lambda: self.refine_requested.emit(self.after_path, "在此基础上：")
            )
            actions_row.addWidget(self.refine_btn)

        layout.addLayout(actions_row)

    def _create_image_box(self, label_text: str, img_path: str) -> QWidget:
        container = QWidget()
        box_layout = QVBoxLayout(container)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(4)

        cap = QLabel(label_text)
        cap.setStyleSheet("color: #86868b; font-size: 11px;")
        box_layout.addWidget(cap)

        img_label = QLabel()
        img_label.setFixedSize(200, 200)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet("border: 1px solid #e5e5ea; border-radius: 8px; background: #fbfbfd;")

        if img_path and Path(img_path).exists():
            pix = QPixmap(img_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    196,
                    196,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("图片解析失败")
        else:
            img_label.setText("无对应图像")

        box_layout.addWidget(img_label)
        return container

    def _on_save_as(self) -> None:
        if not self.after_path:
            return
        # Always emit save_requested signal
        self.save_requested.emit(self.after_path)

        if not Path(self.after_path).exists():
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "保存图片",
            Path(self.after_path).name,
            "Images (*.png *.jpg *.jpeg)",
        )
        if dest:
            try:
                shutil.copy2(self.after_path, dest)
            except Exception:
                pass
