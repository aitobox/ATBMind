"""
ATBMind StylePopover
Doubao-style popover menu for selecting art styles with Apple HIG aesthetics.
"""

from __future__ import annotations

from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from plugins.draw.plugin import DRAW_UI_STYLES


class StyleItemButton(QPushButton):
    """Button representing an art style option inside the grid."""

    def __init__(
        self,
        style_id: str,
        name: str,
        icon: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(f"{icon}  {name}", parent)
        self.style_id = style_id
        self.style_name = name
        self.style_icon = icon
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self.setFixedHeight(34)
        self._update_style(selected=False)

    def _update_style(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #e3f2fd;
                    border: 1.5px solid #0071e3;
                    border-radius: 8px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: 600;
                    color: #0071e3;
                    text-align: left;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #fbfbfd;
                    border: 1px solid #e5e5ea;
                    border-radius: 8px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: normal;
                    color: #1d1d1f;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #f2f2f7;
                    border-color: #0071e3;
                }
            """)


class StylePopover(QFrame):
    """
    Popup grid menu for selecting art styles.
    Adheres to Apple HIG styling with rounded container, subtle shadow, and clean grid.
    """

    style_selected = Signal(str, str)  # (style_id, style_name)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("stylePopoverFrame")
        self.current_style_id: str = "portrait"
        self.style_buttons: Dict[str, StyleItemButton] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#stylePopoverFrame {
                background-color: #ffffff;
                border: 1px solid #d2d2d7;
                border-radius: 12px;
            }
            QLabel#popoverHeader {
                font-size: 11px;
                font-weight: 600;
                color: #86868b;
                letter-spacing: 0.5px;
                padding-bottom: 2px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # Header Title
        header_layout = QHBoxLayout()
        header_label = QLabel("🎨 艺术风格 (Art Styles)")
        header_label.setObjectName("popoverHeader")
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        # 2-column Grid of Styles
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(6)

        columns = 2
        for idx, item in enumerate(DRAW_UI_STYLES):
            s_id = item["id"]
            name = item["name"]
            icon = item["icon"]

            btn = StyleItemButton(style_id=s_id, name=name, icon=icon, parent=self)
            btn.clicked.connect(lambda checked=False, sid=s_id, sname=name: self._on_item_clicked(sid, sname))
            self.style_buttons[s_id] = btn

            row = idx // columns
            col = idx % columns
            grid_layout.addWidget(btn, row, col)

        layout.addLayout(grid_layout)
        self.set_selected_style(self.current_style_id)

    def _on_item_clicked(self, style_id: str, style_name: str) -> None:
        self.set_selected_style(style_id)
        self.style_selected.emit(style_id, style_name)
        self.hide()

    def set_selected_style(self, style_id: str) -> None:
        self.current_style_id = style_id
        for s_id, btn in self.style_buttons.items():
            btn._update_style(selected=(s_id == style_id))

    def get_selected_style(self) -> str:
        return self.current_style_id

    def show_at_widget(self, anchor_widget: QWidget) -> None:
        """Position the popover above or below anchor_widget and display it."""
        self.adjustSize()
        hint = self.sizeHint()
        anchor_rect = anchor_widget.rect()
        global_pos = anchor_widget.mapToGlobal(anchor_rect.topLeft())

        # Prefer popping up above the button
        x = global_pos.x()
        y = global_pos.y() - hint.height() - 6

        # If too high, show below
        if y < 10:
            y = global_pos.y() + anchor_rect.height() + 6

        self.move(x, y)
        self.show()
        self.raise_()
