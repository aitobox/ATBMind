"""
ATBMind Desktop Apple HIG Icons
Provides lightweight, crisp vector SVG icons adhering to Apple Human Interface Guidelines
and macOS SF Symbols aesthetic conventions.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from apps.atbmind_desktop.theme import ThemeColors


# SVG Icon Definitions (16x16 coordinate space, 1.3-1.6px stroke width)
_SVG_TEMPLATES: Dict[str, Tuple[str, Optional[str]]] = {
    # name: (off_template, on_template)
    "sidebar_left": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1.5" y="2" width="13" height="12" rx="2.5" stroke="{stroke}" stroke-width="1.3"/>
            <line x1="5.5" y1="2" x2="5.5" y2="14" stroke="{stroke}" stroke-width="1.3"/>
        </svg>""",
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1.5" y="2" width="13" height="12" rx="2.5" stroke="{active_stroke}" stroke-width="1.3"/>
            <path d="M 1.5 4.5 C 1.5 3.1 2.6 2 4 2 L 5.5 2 L 5.5 14 L 4 14 C 2.6 14 1.5 12.9 1.5 11.5 Z" fill="{active_fill}"/>
            <line x1="5.5" y1="2" x2="5.5" y2="14" stroke="{active_stroke}" stroke-width="1.3"/>
        </svg>""",
    ),
    "sidebar_right": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1.5" y="2" width="13" height="12" rx="2.5" stroke="{stroke}" stroke-width="1.3"/>
            <line x1="10.5" y1="2" x2="10.5" y2="14" stroke="{stroke}" stroke-width="1.3"/>
        </svg>""",
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1.5" y="2" width="13" height="12" rx="2.5" stroke="{active_stroke}" stroke-width="1.3"/>
            <path d="M 10.5 2 L 12 2 C 13.4 2 14.5 3.1 14.5 4.5 L 14.5 11.5 C 14.5 12.9 13.4 14 12 14 L 10.5 14 Z" fill="{active_fill}"/>
            <line x1="10.5" y1="2" x2="10.5" y2="14" stroke="{active_stroke}" stroke-width="1.3"/>
        </svg>""",
    ),
    "chevron_left": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polyline points="10,3.5 5.5,8 10,12.5" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "chevron_right": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polyline points="6,3.5 10.5,8 6,12.5" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "plus": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="8" y1="3" x2="8" y2="13" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round"/>
            <line x1="3" y1="8" x2="13" y2="8" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "clock": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="8" cy="8" r="5.5" stroke="{stroke}" stroke-width="1.3"/>
            <polyline points="8,5 8,8 10.5,9.5" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "calendar": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2.5" y="3.5" width="11" height="10" rx="2" stroke="{stroke}" stroke-width="1.3"/>
            <line x1="2.5" y1="6.5" x2="13.5" y2="6.5" stroke="{stroke}" stroke-width="1.3"/>
            <line x1="5" y1="2" x2="5" y2="4" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
            <line x1="11" y1="2" x2="11" y2="4" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "gear": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="8" cy="8" r="2.5" stroke="{stroke}" stroke-width="1.3"/>
            <path d="M 8 1.5 L 8 3 M 8 13 L 8 14.5 M 1.5 8 L 3 8 M 13 8 L 14.5 8 M 3.4 3.4 L 4.5 4.5 M 11.5 11.5 L 12.6 12.6 M 3.4 12.6 L 4.5 11.5 M 11.5 4.5 L 12.6 3.4" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "code": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polyline points="5.5,5 2.5,8 5.5,11" stroke="{stroke}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="10.5,5 13.5,8 10.5,11" stroke="{stroke}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "more": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="3.5" cy="8" r="1.3" fill="{stroke}"/>
            <circle cx="8" cy="8" r="1.3" fill="{stroke}"/>
            <circle cx="12.5" cy="8" r="1.3" fill="{stroke}"/>
        </svg>""",
        None,
    ),
    "arrow_up": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="8" y1="12.5" x2="8" y2="3.5" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round"/>
            <polyline points="4.5,7 8,3.5 11.5,7" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "arrow_right": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="3.5" y1="8" x2="12.5" y2="8" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round"/>
            <polyline points="9,4.5 12.5,8 9,11.5" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "mic": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="5.5" y="2.5" width="5" height="7.5" rx="2.5" stroke="{stroke}" stroke-width="1.3"/>
            <path d="M 3.5 7 C 3.5 9.5 5.5 11.5 8 11.5 C 10.5 11.5 12.5 9.5 12.5 7" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
            <line x1="8" y1="11.5" x2="8" y2="14" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "paperclip": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 11.5 6.5 L 6.5 11.5 C 5.1 12.9 2.9 12.9 1.5 11.5 C 0.1 10.1 0.1 7.9 1.5 6.5 L 7 1 C 8 0 9.6 0 10.6 1 C 11.6 2 11.6 3.6 10.6 4.6 L 5.5 9.7 C 4.9 10.3 3.9 10.3 3.3 9.7 C 2.7 9.1 2.7 8.1 3.3 7.5 L 8 2.8" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "trash": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 3 4.5 L 13 4.5 M 5.5 4.5 L 5.5 3 C 5.5 2.5 6 2 6.5 2 L 9.5 2 C 10 2 10.5 2.5 10.5 3 L 10.5 4.5 M 4 4.5 L 4.5 13 C 4.5 13.5 5 14 5.5 14 L 10.5 14 C 11 14 11.5 13.5 11.5 13 L 12 4.5" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "pencil": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 11 2.5 L 13.5 5 L 5.5 13 L 2.5 13.5 L 3 10.5 Z" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "fullscreen": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 2.5 6 L 2.5 2.5 L 6 2.5 M 10 2.5 L 13.5 2.5 L 13.5 6 M 13.5 10 L 13.5 13.5 L 10 13.5 M 6 13.5 L 2.5 13.5 L 2.5 10" stroke="{stroke}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "search": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="7" cy="7" r="4.5" stroke="{stroke}" stroke-width="1.4"/>
            <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="{stroke}" stroke-width="1.4" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "puzzle": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 3 5.5 C 3 4.1 4.1 3 5.5 3 H 6.5 C 6.5 4.1 7.2 4.8 8 4.8 C 8.8 4.8 9.5 4.1 9.5 3 H 10.5 C 11.9 3 13 4.1 13 5.5 V 6.5 C 11.9 6.5 11.2 7.2 11.2 8 C 11.2 8.8 11.9 9.5 13 9.5 V 10.5 C 13 11.9 11.9 13 10.5 13 H 9.5 C 9.5 11.9 8.8 11.2 8 11.2 C 7.2 11.2 6.5 11.9 6.5 13 H 5.5 C 4.1 13 3 11.9 3 10.5 V 9.5 C 4.1 9.5 4.8 8.8 4.8 8 C 4.8 7.2 4.1 6.5 3 6.5 Z" stroke="{stroke}" stroke-width="1.3" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
    "download": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 8 2.5 V 10.5 M 5 7.5 L 8 10.5 L 11 7.5" stroke="{stroke}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M 2.5 11.5 V 13 C 2.5 13.5 2.9 14 3.5 14 H 12.5 C 13.1 14 13.5 13.5 13.5 13 V 11.5" stroke="{stroke}" stroke-width="1.4" stroke-linecap="round"/>
        </svg>""",
        None,
    ),
    "refresh": (
        """<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M 13.5 8 C 13.5 11 11 13.5 8 13.5 C 5 13.5 2.5 11 2.5 8 C 2.5 5 5 2.5 8 2.5 C 10.2 2.5 12.1 3.8 13 5.7" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round"/>
            <polyline points="13.5,2.5 13.5,5.8 10.2,5.8" stroke="{stroke}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
        None,
    ),
}

_ICON_CACHE: Dict[Tuple[str, int, str, str], QIcon] = {}


def _render_svg_pixmap(svg_xml: str, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_xml.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def get_apple_icon(
    name: str,
    size: int = 16,
    color: Optional[str] = None,
    active_color: Optional[str] = None,
) -> QIcon:
    """
    Returns an Apple HIG-styled vector QIcon for the given name.
    If GUI application is not active, safely returns an empty QIcon.
    """
    if QGuiApplication.instance() is None:
        return QIcon()

    stroke = color or ThemeColors.TEXT_SECONDARY
    active_stroke = active_color or ThemeColors.PRIMARY
    cache_key = (name, size, stroke, active_stroke)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    template_entry = _SVG_TEMPLATES.get(name)
    if not template_entry:
        return QIcon()

    off_tmpl, on_tmpl = template_entry
    off_xml = off_tmpl.format(stroke=stroke)

    icon = QIcon()
    pix_off = _render_svg_pixmap(off_xml, size)
    icon.addPixmap(pix_off, QIcon.Mode.Normal, QIcon.State.Off)

    if on_tmpl:
        on_xml = on_tmpl.format(
            active_stroke=active_stroke,
            active_fill=ThemeColors.PRIMARY_LIGHT,
        )
        pix_on = _render_svg_pixmap(on_xml, size)
        icon.addPixmap(pix_on, QIcon.Mode.Normal, QIcon.State.On)
    else:
        # Generate an active state pixmap with active color
        active_xml = off_tmpl.format(stroke=active_stroke)
        pix_active = _render_svg_pixmap(active_xml, size)
        icon.addPixmap(pix_active, QIcon.Mode.Normal, QIcon.State.On)
        icon.addPixmap(pix_active, QIcon.Mode.Active, QIcon.State.Off)

    _ICON_CACHE[cache_key] = icon
    return icon
