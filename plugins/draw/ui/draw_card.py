"""
ATBDraw DrawResultCard
Dedicated PySide6 image result comparison card component for ATBDraw.
Renders Before (original) and After (retouched) images side-by-side with modern Apple HIG aesthetics,
displays metadata bar (elapsed time, template name badge), and provides action buttons.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
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


class ClickableImageLabel(QLabel):
    """QLabel that emits clicked signal for instant preview."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DrawResultCard(QFrame):
    """
    Dedicated Before/After image comparison result card for ATBDraw results.
    Adheres to Apple HIG styling with rounded container, refined elevation, and clear primary CTA.
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
        self.setStyleSheet(f"""
            DrawResultCard {{
                background-color: {ThemeColors.BG_CARD};
                border: 1px solid {ThemeColors.BORDER_CARD};
                border-radius: {ThemeRadii.CARD};
                margin: 8px 20px;
            }}
            QLabel {{
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_STRONG};
                border-radius: {ThemeRadii.BUTTON};
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_INPUT};
                border-color: {ThemeColors.PRIMARY};
                color: {ThemeColors.PRIMARY};
            }}
            QPushButton#refineBtn {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: 1px solid {ThemeColors.PRIMARY};
                font-weight: 600;
            }}
            QPushButton#refineBtn:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
                border-color: {ThemeColors.PRIMARY_HOVER};
                color: #FFFFFF;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        # 1. Meta Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self.badge = QLabel(f"🎨 ATBDraw: {self.template_name}")
        self.badge.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 700;
            color: {ThemeColors.PRIMARY};
            background-color: {ThemeColors.PRIMARY_LIGHT};
            border-radius: {ThemeRadii.PILL};
            padding: 3px 10px;
            border: 1px solid {ThemeColors.PRIMARY_BORDER};
        """)
        header.addWidget(self.badge)

        header.addStretch(1)

        self.time_label = QLabel(f"⏱ 耗时: {self.elapsed:.1f}s")
        self.time_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_MUTED};
            font-size: 11px;
            background-color: {ThemeColors.BG_INPUT};
            border-radius: {ThemeRadii.PILL};
            padding: 3px 8px;
        """)
        header.addWidget(self.time_label)
        layout.addLayout(header)

        # 2. Images Row (Before / After)
        img_row = QHBoxLayout()
        img_row.setSpacing(16)

        # Before Image Box
        self.before_box = self._create_image_box("原图 (Before)", self.before_path, is_after=False)
        img_row.addWidget(self.before_box)

        # After Image Box
        self.after_box = self._create_image_box("精修效果 (After)", self.after_path, is_after=True)
        img_row.addWidget(self.after_box)

        layout.addLayout(img_row)

        # 3. Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addStretch(1)

        if self.after_path:
            self.zoom_btn = QPushButton("🔍 放大查看")
            self.zoom_btn.setObjectName("zoomBtn")
            self.zoom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.zoom_btn.clicked.connect(lambda: self.zoom_requested.emit(self.after_path))
            actions_row.addWidget(self.zoom_btn)

            self.save_btn = QPushButton("💾 另存为")
            self.save_btn.setObjectName("saveBtn")
            self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.save_btn.clicked.connect(self._on_save_as)
            actions_row.addWidget(self.save_btn)

            self.refine_btn = QPushButton("↺ 以此结果微调")
            self.refine_btn.setObjectName("refineBtn")
            self.refine_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.refine_btn.setToolTip("将精修图填入下一轮输入框作为底图继续微调")
            self.refine_btn.clicked.connect(
                lambda: self.refine_requested.emit(self.after_path, "在此基础上：")
            )
            actions_row.addWidget(self.refine_btn)

        layout.addLayout(actions_row)

    def _create_image_box(self, label_text: str, img_path: str, is_after: bool = False) -> QWidget:
        container = QWidget()
        box_layout = QVBoxLayout(container)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(6)

        cap = QLabel(label_text)
        cap.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
        """)
        box_layout.addWidget(cap)

        img_label = ClickableImageLabel()
        img_label.setFixedSize(220, 220)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setCursor(Qt.CursorShape.PointingHandCursor if img_path else Qt.CursorShape.ArrowCursor)
        img_label.setStyleSheet(f"""
            ClickableImageLabel {{
                border: 1px solid {ThemeColors.BORDER_CARD};
                border-radius: 10px;
                background-color: {ThemeColors.BG_INPUT};
            }}
            ClickableImageLabel:hover {{
                border-color: {ThemeColors.PRIMARY if img_path else ThemeColors.BORDER_CARD};
            }}
        """)

        if img_path and Path(img_path).exists():
            pix = QPixmap(img_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    216,
                    216,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("图片解析失败")
        else:
            img_label.setText("无对应图像")
            img_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 12px;")

        if img_path:
            img_label.clicked.connect(lambda: self.zoom_requested.emit(img_path))

        box_layout.addWidget(img_label)
        return container

    def _on_save_as(self) -> None:
        if not self.after_path:
            return
        self.save_requested.emit(self.after_path)

        orig_name = Path(self.after_path).name
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存精修图像",
            orig_name,
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if target_path:
            try:
                shutil.copy2(self.after_path, target_path)
            except Exception:
                pass
