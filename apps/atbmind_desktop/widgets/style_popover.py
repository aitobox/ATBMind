"""
ATBMind StylePopover
Doubao-style popover menu for selecting art styles with Apple HIG aesthetics.
"""

from __future__ import annotations

from typing import Dict, Optional
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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
        self.setFixedHeight(36)
        self._update_style(selected=False)

    def _update_style(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ThemeColors.PRIMARY_LIGHT};
                    border: 1.5px solid {ThemeColors.PRIMARY};
                    border-radius: {ThemeRadii.BUTTON};
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 600;
                    color: {ThemeColors.PRIMARY};
                    font-family: {ThemeFonts.FONT_STACK};
                    text-align: left;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    border: 1px solid {ThemeColors.BORDER_SUBTLE};
                    border-radius: {ThemeRadii.BUTTON};
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 500;
                    color: {ThemeColors.TEXT_PRIMARY};
                    font-family: {ThemeFonts.FONT_STACK};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {ThemeColors.BG_INPUT_HOVER};
                    border-color: {ThemeColors.BORDER_STRONG};
                    color: {ThemeColors.PRIMARY};
                }}
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
        self.setStyleSheet(f"""
            QFrame#stylePopoverFrame {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_CARD};
                border-radius: {ThemeRadii.POPOVER};
            }}
            QLabel#popoverHeader {{
                font-size: 11px;
                font-weight: 700;
                color: {ThemeColors.TEXT_MUTED};
                letter-spacing: 0.5px;
                padding-bottom: 2px;
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        # Header Title
        header_layout = QHBoxLayout()
        header_label = QLabel("🎨 艺术风格预设 (ART STYLES)")
        header_label.setObjectName("popoverHeader")
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        # 2-column Grid of Styles
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(10)
        grid_layout.setVerticalSpacing(8)

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
        self.close()

    def set_selected_style(self, style_id: str) -> None:
        self.current_style_id = style_id
        for s_id, btn in self.style_buttons.items():
            btn._update_style(selected=(s_id == style_id))

    def get_selected_style(self) -> str:
        return self.current_style_id

    def show_at_widget(self, target_widget: QWidget) -> None:
        """Pops up the menu anchored above the target button."""
        self.adjustSize()
        global_pos = target_widget.mapToGlobal(QPoint(0, 0))
        pop_w = self.sizeHint().width()
        pop_h = self.sizeHint().height()

        target_center_x = global_pos.x() + (target_widget.width() // 2)
        target_top_y = global_pos.y()

        x = target_center_x - (pop_w // 2)
        y = target_top_y - pop_h - 8

        screen = target_widget.screen()
        if screen:
            screen_geom = screen.availableGeometry()
            if x + pop_w > screen_geom.right():
                x = screen_geom.right() - pop_w - 8
            if x < screen_geom.left():
                x = screen_geom.left() + 8
            if y < screen_geom.top():
                y = target_top_y + target_widget.height() + 8

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
