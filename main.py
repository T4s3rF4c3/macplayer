import sys
import os

# Ensure project root is on the path so imports work from any working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor


def _dark_palette() -> QPalette:
    p = QPalette()
    bg       = QColor(22, 22, 22)
    bg_input = QColor(18, 18, 18)
    bg_alt   = QColor(32, 32, 32)
    accent   = QColor(0, 120, 212)
    text     = QColor(220, 220, 220)
    text_dim = QColor(128, 128, 128)
    btn      = QColor(45, 45, 45)

    p.setColor(QPalette.ColorRole.Window,          bg)
    p.setColor(QPalette.ColorRole.WindowText,      text)
    p.setColor(QPalette.ColorRole.Base,            bg_input)
    p.setColor(QPalette.ColorRole.AlternateBase,   bg_alt)
    p.setColor(QPalette.ColorRole.ToolTipBase,     bg_alt)
    p.setColor(QPalette.ColorRole.ToolTipText,     text)
    p.setColor(QPalette.ColorRole.Text,            text)
    p.setColor(QPalette.ColorRole.Button,          btn)
    p.setColor(QPalette.ColorRole.ButtonText,      text)
    p.setColor(QPalette.ColorRole.BrightText,      Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link,            accent)
    p.setColor(QPalette.ColorRole.Highlight,       accent)
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       text_dim)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, text_dim)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, text_dim)

    return p


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MacPlayer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MacPlayer")
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())

    # Import after QApplication is created
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
