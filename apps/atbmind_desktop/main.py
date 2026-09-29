"""
ATBMind Desktop Application Main Entry Point
Initializes QApplication with Apple HIG styling and presents ATBMindMainWindow.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path when running as a standalone script
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from apps.atbmind_desktop.main_window import ATBMindMainWindow


def create_app(argv: list[str] | None = None) -> QApplication:
    """Creates or retrieves the QApplication singleton with Apple typography."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv or sys.argv)

    app.setApplicationName("ATBMind")
    app.setApplicationDisplayName("ATBMind Desktop")
    app.setOrganizationName("aitobox")

    # Set Apple HIG system font
    font = QFont(".AppleSystemUIFont", 13)
    if not font.exactMatch():
        font = QFont("-apple-system", 13)
    app.setFont(font)

    return app


def main() -> int:
    """Main desktop process entry point."""
    app = create_app(sys.argv)

    window = ATBMindMainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
