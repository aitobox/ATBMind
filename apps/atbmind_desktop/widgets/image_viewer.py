"""
ATBMind ImageViewerDialog
Modal full-resolution image previewer with smooth scaling and Esc shortcut dismiss.
Adheres to Apple HIG QuickLook and dark photo canvas aesthetics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apps.atbmind_desktop.theme import ThemeFonts, ThemeRadii


class ImageViewerDialog(QDialog):
    """
    Clean, modal full-resolution image viewer adhering to Apple HIG.
    """

    def __init__(self, image_path: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.image_path = image_path
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(f"预览: {Path(self.image_path).name}")
        self.setMinimumSize(600, 450)
        self.resize(800, 600)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #18181A;
                color: #FFFFFF;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel {{
                color: #FFFFFF;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: {ThemeRadii.BUTTON};
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.22);
                border-color: rgba(255, 255, 255, 0.35);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header bar with file path and close button
        header_bar = QHBoxLayout()
        self.title_label = QLabel(Path(self.image_path).name)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #F5F5F7;")
        header_bar.addWidget(self.title_label)

        header_bar.addStretch(1)

        self.close_btn = QPushButton("✕ 关闭 (Esc)")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.accept)
        header_bar.addWidget(self.close_btn)
        layout.addLayout(header_bar)

        # Image display area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            # Initial scale preserving aspect ratio
            scaled = pixmap.scaled(
                760, 500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText(f"无法加载图像: {self.image_path}")
            self.image_label.setStyleSheet("color: #FF6B6B; font-size: 14px;")

        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
