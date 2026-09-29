"""
ATBMind Desktop UI Widgets
Modular PySide6 components compliant with Apple HIG principles.
"""

from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView
from apps.atbmind_desktop.widgets.footer_dock import (
    AttachmentChip,
    AutoResizingTextEdit,
    FooterDock,
)
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog
from apps.atbmind_desktop.widgets.sidebar import SidebarWidget
from apps.atbmind_desktop.widgets.style_popover import StylePopover

__all__ = [
    "AttachmentChip",
    "AutoResizingTextEdit",
    "ChatStreamView",
    "FooterDock",
    "ImageViewerDialog",
    "SettingsDialog",
    "SidebarWidget",
    "StylePopover",
]
