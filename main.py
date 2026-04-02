"""
Entry point. Shows login dialog before main window.
Loops to support logout → re-login without restarting the process.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QDialog


def _apply_light_theme(app: QApplication) -> None:
    """Force a light theme so text is always readable, regardless of OS dark mode."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(248, 250, 252))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(30,  41,  59))
    pal.setColor(QPalette.ColorRole.Base,            QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(241, 245, 249))
    pal.setColor(QPalette.ColorRole.Text,            QColor(30,  41,  59))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(30,  41,  59))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(30,  41,  59))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(30,  41,  59))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(148, 163, 184))
    pal.setColor(QPalette.ColorRole.Button,          QColor(241, 245, 249))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(59,  130, 246))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Product License Timer")
    app.setQuitOnLastWindowClosed(False)
    _apply_light_theme(app)

    from ui.login_dialog import LoginDialog

    while True:
        login_dlg = LoginDialog()
        if login_dlg.exec() != QDialog.DialogCode.Accepted:
            break

        user_session = login_dlg.get_user_session()
        db_session   = login_dlg.get_db_session()

        from ui.main_window import MainWindow
        window = MainWindow(user_session=user_session, db_session=db_session)

        if "--minimized" not in sys.argv:
            window.show()

        app.exec()  # blocks until QApplication.quit() is called

        if not window.logout_requested:
            break  # user clicked Exit → stop the loop

    sys.exit(0)


if __name__ == "__main__":
    main()
