"""
Entry point. Handles --minimized flag for Windows auto-start via registry.
"""
import sys
from pathlib import Path

# Ensure project root is importable when launched via pythonw.exe
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Product License Timer")
    app.setQuitOnLastWindowClosed(False)  # Allow tray-only mode

    window = MainWindow()

    if "--minimized" not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
