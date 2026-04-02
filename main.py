"""
Entry point. Shows login dialog before main window.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QDialog
from ui.login_dialog import LoginDialog


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Product License Timer")
    app.setQuitOnLastWindowClosed(False)

    login_dlg = LoginDialog()
    if login_dlg.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    user_session = login_dlg.get_user_session()
    db_session = login_dlg.get_db_session()

    from ui.main_window import MainWindow
    window = MainWindow(user_session=user_session, db_session=db_session)

    if "--minimized" not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
