"""Login dialog shown before MainWindow. Light centered card style."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame,
    QDialogButtonBox,
)
from sqlalchemy.orm import Session
from services.auth_service import UserSession, login, is_default_password
from services.db_session import get_session


class _VerifyAccountDialog(QDialog):
    """Token entry dialog for email verification."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verify Account")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(QLabel(
            "Enter the verification token from your email.\n"
            "If SMTP was not configured, ask your admin for the token."
        ))
        self._token = QLineEdit()
        self._token.setPlaceholderText("Paste token here")
        layout.addWidget(self._token)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._verify)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _verify(self) -> None:
        from services.auth_service import verify_email_token
        token = self._token.text().strip()
        if not token:
            QMessageBox.warning(self, "Error", "Please enter a token.")
            return
        session = get_session()
        try:
            ok = verify_email_token(session, token)
        finally:
            session.close()
        if ok:
            QMessageBox.information(
                self, "Verified",
                "Account verified! You can now log in."
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Token",
                                "Token is invalid or has expired.")


class ChangePasswordDialog(QDialog):
    """Forced password change on first login."""

    def __init__(self, session: Session, user_session: UserSession, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.setFixedWidth(380)
        self._session = session
        self._user_session = user_session
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(QLabel(
            "You are using the default password.\nPlease set a new password to continue."
        ))
        self._new_pw = QLineEdit()
        self._new_pw.setPlaceholderText("New password")
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setPlaceholderText("Confirm new password")
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._new_pw)
        layout.addWidget(self._confirm_pw)
        btn = QPushButton("Save New Password")
        btn.clicked.connect(self._save)
        layout.addWidget(btn)

    def _save(self) -> None:
        from services.auth_service import change_password, DEFAULT_PASSWORD
        new = self._new_pw.text()
        confirm = self._confirm_pw.text()
        if new != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return
        if len(new) < 8:
            QMessageBox.warning(self, "Error", "Password must be at least 8 characters.")
            return
        ok = change_password(self._session, self._user_session.user_id, DEFAULT_PASSWORD, new)
        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Could not update password.")


class LoginDialog(QDialog):
    """Light centered card login screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Product License Timer")
        self.setFixedWidth(400)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        self._session: Session | None = None
        self._user_session: UserSession | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(40, 40, 40, 40)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setStyleSheet("""
            QFrame#loginCard {
                background: white;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Product License Timer")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")

        subtitle = QLabel("Sign in to continue")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 12px;")

        self._email = QLineEdit()
        self._email.setPlaceholderText("Email address")
        self._email.setStyleSheet("padding: 8px; border: 1px solid #e2e8f0; border-radius: 4px;")

        self._password = QLineEdit()
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setStyleSheet("padding: 8px; border: 1px solid #e2e8f0; border-radius: 4px;")
        self._password.returnPressed.connect(self._attempt_login)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ef4444; font-size: 11px;")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.hide()

        sign_in_btn = QPushButton("Sign In")
        sign_in_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6; color: white; border-radius: 4px;
                padding: 8px; font-weight: bold;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        sign_in_btn.clicked.connect(self._attempt_login)

        verify_btn = QPushButton("Verify Account")
        verify_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #3b82f6;
                border: none; padding: 4px;
            }
            QPushButton:hover { color: #2563eb; text-decoration: underline; }
        """)
        verify_btn.clicked.connect(self._open_verify)

        for w in [title, subtitle, self._email, self._password,
                  self._error_label, sign_in_btn, verify_btn]:
            layout.addWidget(w)

        outer.addWidget(card)

    def _open_verify(self) -> None:
        _VerifyAccountDialog(self).exec()

    def _attempt_login(self) -> None:
        email = self._email.text().strip()
        password = self._password.text()
        self._error_label.hide()

        try:
            session = get_session()
            from models.orm import User
            if session.query(User).count() == 0:
                self._error_label.setText(
                    "No users exist.\nRun: python -m migrations.init_schema"
                )
                self._error_label.show()
                session.close()
                return

            result = login(session, email, password)
            if result is None:
                self._error_label.setText("Invalid email or password.")
                self._error_label.show()
                session.close()
                return

            # Check for default password — force change
            if is_default_password(password):
                dlg = ChangePasswordDialog(session, result, self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    session.close()
                    return

            self._session = session
            self._user_session = result
            self.accept()

        except Exception as e:
            self._error_label.setText(f"Connection error:\n{e}")
            self._error_label.show()

    def get_user_session(self) -> UserSession | None:
        return self._user_session

    def get_db_session(self) -> Session | None:
        return self._session
