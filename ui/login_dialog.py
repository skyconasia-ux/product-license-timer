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


class _ForgotPasswordDialog(QDialog):
    """Two-step password reset: enter email → send token → enter token + new password."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forgot Password")
        self.setFixedWidth(420)
        self._token_from_no_smtp: str | None = None
        self._build()

    def _build(self) -> None:
        from PyQt6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._stack)
        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())

    def _build_step1(self) -> QWidget:
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(QLabel(
            "Enter your email address.\n"
            "A password reset token will be sent if the account exists."
        ))
        self._email = QLineEdit()
        self._email.setPlaceholderText("Email address")
        layout.addWidget(self._email)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Send Reset Token")
        btns.accepted.connect(self._send_token)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        return w

    def _build_step2(self) -> QWidget:
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        self._step2_label = QLabel(
            "Enter the reset token from your email, then set a new password."
        )
        self._step2_label.setWordWrap(True)
        layout.addWidget(self._step2_label)
        self._token = QLineEdit()
        self._token.setPlaceholderText("Paste reset token here")
        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setPlaceholderText("New password (min 8 characters)")
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw.setPlaceholderText("Confirm new password")
        for w2 in [self._token, self._new_pw, self._confirm_pw]:
            layout.addWidget(w2)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Reset Password")
        btns.accepted.connect(self._do_reset)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        return w

    def _send_token(self) -> None:
        from services.auth_service import create_password_reset_token
        from services.notification_service import _send_smtp, get_smtp_config

        email = self._email.text().strip()
        if not email:
            QMessageBox.warning(self, "Error", "Please enter your email address.")
            return

        session = get_session()
        try:
            token = create_password_reset_token(session, email)
        finally:
            session.close()

        if token is not None:
            cfg = get_smtp_config()
            sent = False
            if cfg.get("smtp_host") and cfg.get("smtp_user"):
                sent = _send_smtp(
                    subject="Password Reset — Product License Timer",
                    body=(
                        f"Hello,\n\n"
                        f"A password reset was requested for your account ({email}).\n\n"
                        f"Your reset token is:\n\n"
                        f"    {token}\n\n"
                        f"Enter this token in the app to reset your password.\n"
                        f"This token expires in 20 minutes and can only be used once.\n\n"
                        f"If you did not request this, ignore this email.\n"
                    ),
                    recipients=[email],
                    cfg=cfg,
                )
            if not sent:
                # SMTP not configured — pre-fill the token and inform admin
                self._token.setText(token)
                self._step2_label.setText(
                    f"SMTP is not configured. Token for {email} (pre-filled below):\n"
                    f"Expires in 20 minutes."
                )
                self._stack.setCurrentIndex(1)
                return

        # Generic message to avoid email enumeration
        QMessageBox.information(
            self, "Token Sent",
            "If this email exists, a reset token has been sent.\n"
            "Check your inbox and enter the token below."
        )
        self._stack.setCurrentIndex(1)

    def _do_reset(self) -> None:
        from services.auth_service import reset_password_with_token

        token = self._token.text().strip()
        new_pw = self._new_pw.text()
        confirm = self._confirm_pw.text()

        if not token:
            QMessageBox.warning(self, "Error", "Please enter the reset token.")
            return
        if len(new_pw) < 8:
            QMessageBox.warning(self, "Error", "Password must be at least 8 characters.")
            return
        if new_pw != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return

        session = get_session()
        try:
            ok = reset_password_with_token(session, token, new_pw)
        finally:
            session.close()

        if ok:
            QMessageBox.information(
                self, "Password Reset",
                "Your password has been reset. You can now log in."
            )
            self.accept()
        else:
            QMessageBox.warning(
                self, "Reset Failed",
                "Token is invalid or has expired. Please request a new token."
            )


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

        forgot_btn = QPushButton("Forgot Password")
        forgot_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #3b82f6;
                border: none; padding: 4px;
            }
            QPushButton:hover { color: #2563eb; text-decoration: underline; }
        """)
        forgot_btn.clicked.connect(self._open_forgot_password)

        for w in [title, subtitle, self._email, self._password,
                  self._error_label, sign_in_btn, forgot_btn]:
            layout.addWidget(w)

        outer.addWidget(card)

    def _open_forgot_password(self) -> None:
        _ForgotPasswordDialog(self).exec()

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
