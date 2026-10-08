"""
ATBMind Desktop Theme & Design System Tokens
Centralizes colors, typography, spacing, radii, and component QSS stylesheets
grounded in Apple Human Interface Guidelines and modern AI desktop application aesthetics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap


class ThemeColors:
    # Primary Accent (Apple System Blue)
    PRIMARY = "#007AFF"
    PRIMARY_HOVER = "#0062CC"
    PRIMARY_PRESSED = "#004FB8"
    PRIMARY_LIGHT = "#EBF5FF"
    PRIMARY_SUBTLE = "rgba(0, 122, 255, 0.08)"
    PRIMARY_BORDER = "rgba(0, 122, 255, 0.3)"

    # Surfaces & Backgrounds
    BG_WINDOW = "#FBFBFD"
    BG_SIDEBAR = "#F5F5F7"
    BG_SIDEBAR_HOVER = "#EAEAEF"
    BG_SIDEBAR_SELECTED = "#E3E3E8"
    BG_CHAT = "#FFFFFF"
    BG_CARD = "#FFFFFF"
    BG_INPUT = "#F4F4F6"
    BG_INPUT_HOVER = "#ECECEF"
    BG_BUBBLE_ASSISTANT = "#F4F4F6"
    BG_BUBBLE_USER = "#007AFF"

    # Typography & Text
    TEXT_PRIMARY = "#1D1D1F"
    TEXT_SECONDARY = "#6E6E73"
    TEXT_MUTED = "#86868B"
    TEXT_PLACEHOLDER = "#AEAEB2"
    TEXT_ON_PRIMARY = "#FFFFFF"
    TEXT_LINK = "#007AFF"

    # Borders & Dividers
    BORDER_SUBTLE = "#E5E5EA"
    BORDER_LIGHT = "rgba(0, 0, 0, 0.06)"
    BORDER_CARD = "rgba(0, 0, 0, 0.08)"
    BORDER_FOCUS = "#007AFF"
    BORDER_STRONG = "#D2D2D7"

    # Feedback & Semantic Status
    SUCCESS = "#34C759"
    SUCCESS_LIGHT = "#EAF8EE"
    WARNING = "#FF9500"
    WARNING_LIGHT = "#FFF8EC"
    ERROR = "#FF3B30"
    ERROR_BG = "#FEF2F2"
    ERROR_BORDER = "#FECACA"
    ERROR_HOVER = "#FF2D20"


class ThemeFonts:
    FONT_STACK = (
        '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", '
        '"PingFang SC", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
    )
    FONT_MONO = '"SF Mono", Menlo, Monaco, "Courier New", monospace'


class ThemeRadii:
    WINDOW = "12px"
    CARD = "14px"
    DOCK = "16px"
    BUBBLE = "16px"
    BUTTON = "8px"
    INPUT = "8px"
    POPOVER = "12px"
    PILL = "9999px"


# ----------------------------------------------------------------------
# Reusable QSS Mixins
# ----------------------------------------------------------------------

SLIM_SCROLLBAR_QSS = f"""
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 0px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: rgba(0, 0, 0, 0.15);
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(0, 0, 0, 0.28);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""

MODERN_COMBOBOX_QSS = f"""
QComboBox {{
    background-color: {ThemeColors.BG_INPUT};
    color: {ThemeColors.TEXT_PRIMARY};
    border: 1px solid {ThemeColors.BORDER_SUBTLE};
    border-radius: {ThemeRadii.BUTTON};
    padding: 5px 24px 5px 10px;
    font-size: 12px;
    font-weight: 500;
    font-family: {ThemeFonts.FONT_STACK};
}}
QComboBox:hover {{
    background-color: {ThemeColors.BG_INPUT_HOVER};
    border-color: {ThemeColors.BORDER_STRONG};
}}
QComboBox:focus {{
    border: 1.5px solid {ThemeColors.BORDER_FOCUS};
    background-color: #FFFFFF;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
    border-top-right-radius: {ThemeRadii.BUTTON};
    border-bottom-right-radius: {ThemeRadii.BUTTON};
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {ThemeColors.TEXT_MUTED};
    width: 0px;
    height: 0px;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: #FFFFFF;
    color: {ThemeColors.TEXT_PRIMARY};
    border: 1px solid {ThemeColors.BORDER_SUBTLE};
    border-radius: 8px;
    selection-background-color: {ThemeColors.PRIMARY_LIGHT};
    selection-color: {ThemeColors.PRIMARY};
    padding: 4px;
    outline: none;
}}
"""

APPLE_TOOLBAR_BUTTON_QSS = f"""
QPushButton {{
    background-color: rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 6px;
    padding: 4px 8px;
    color: {ThemeColors.TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 500;
    font-family: {ThemeFonts.FONT_STACK};
}}
QPushButton:hover {{
    background-color: rgba(0, 0, 0, 0.08);
    border-color: rgba(0, 0, 0, 0.16);
    color: {ThemeColors.TEXT_PRIMARY};
}}
QPushButton:pressed {{
    background-color: rgba(0, 0, 0, 0.12);
}}
QPushButton:checked {{
    background-color: {ThemeColors.PRIMARY_LIGHT};
    border-color: {ThemeColors.PRIMARY_BORDER};
    color: {ThemeColors.PRIMARY};
}}
QPushButton:disabled {{
    background-color: rgba(0, 0, 0, 0.02);
    border-color: rgba(0, 0, 0, 0.04);
    color: {ThemeColors.TEXT_MUTED};
}}
"""

APPLE_ICON_BUTTON_QSS = f"""
QPushButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px;
    color: {ThemeColors.TEXT_SECONDARY};
}}
QPushButton:hover {{
    background-color: rgba(0, 0, 0, 0.06);
    border-color: rgba(0, 0, 0, 0.06);
    color: {ThemeColors.TEXT_PRIMARY};
}}
QPushButton:pressed {{
    background-color: rgba(0, 0, 0, 0.10);
}}
QPushButton:checked {{
    background-color: {ThemeColors.PRIMARY_LIGHT};
    border-color: {ThemeColors.PRIMARY_BORDER};
    color: {ThemeColors.PRIMARY};
}}
"""


class BrandAssets:
    """Centralized brand asset provider for ATBMind Desktop."""

    _brand_dir: Optional[Path] = None
    _app_icon_cache: Optional[QIcon] = None
    _avatar_cache: Dict[int, QPixmap] = {}
    _hero_cache: Optional[QPixmap] = None

    @classmethod
    def get_brand_dir(cls) -> Path:
        if cls._brand_dir is not None:
            return cls._brand_dir
        root = Path(__file__).resolve().parents[2]
        return root / "resource" / "assets" / "brand"

    @classmethod
    def get_app_icon(cls) -> QIcon:
        if cls._app_icon_cache is not None and not cls._app_icon_cache.isNull():
            return cls._app_icon_cache

        brand_dir = cls.get_brand_dir()
        icon = QIcon()

        if brand_dir.exists():
            sizes = [16, 32, 64, 128, 256, 512, 1024]
            for s in sizes:
                png_path = brand_dir / f"app_icon_{s}.png"
                if png_path.exists():
                    icon.addFile(str(png_path))

            if icon.isNull():
                master = brand_dir / "app_icon_1024.png"
                if master.exists():
                    icon.addFile(str(master))

        if icon.isNull():
            from apps.atbmind_desktop.icons import get_apple_icon
            icon = get_apple_icon("sidebar_left")

        cls._app_icon_cache = icon
        return icon

    @classmethod
    def get_mascot_avatar(cls, size: int = 24) -> QPixmap:
        if size in cls._avatar_cache and not cls._avatar_cache[size].isNull():
            return cls._avatar_cache[size]

        brand_dir = cls.get_brand_dir()
        avatar_path = brand_dir / "mascot_avatar.png"

        pixmap = QPixmap()
        if avatar_path.exists():
            pixmap.load(str(avatar_path))

        if pixmap.isNull():
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setBrush(Qt.GlobalColor.lightGray)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, size, size)
            painter.end()
            cls._avatar_cache[size] = pixmap
            return pixmap

        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        cls._avatar_cache[size] = scaled
        return scaled

    @classmethod
    def get_mascot_hero(cls) -> QPixmap:
        if cls._hero_cache is not None and not cls._hero_cache.isNull():
            return cls._hero_cache

        brand_dir = cls.get_brand_dir()
        hero_path = brand_dir / "mascot_hero.png"

        pixmap = QPixmap()
        if hero_path.exists():
            pixmap.load(str(hero_path))

        if pixmap.isNull():
            pixmap = QPixmap(256, 256)
            pixmap.fill(Qt.GlobalColor.transparent)

        cls._hero_cache = pixmap
        return pixmap


