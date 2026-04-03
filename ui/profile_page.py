"""My Profile page — self-service name, email, and password management."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QFrame, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from services.auth_service import UserSession


def _section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "font-size: 11px; font-weight: bold; color: #64748b; letter-spacing: 1px;"
    )
    return lbl


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #e2e8f0;")
    return f


def _send_notification(recipient_email: str, subject: str, body: str) -> None:
    """Fire-and-forget SMTP notification. Fails silently if SMTP not configured."""
    try:
        from services.notification_service import _send_smtp, get_smtp_config
        cfg = get_smtp_config()
        if cfg.get("smtp_host") and cfg.get("smtp_user"):
            _send_smtp(subject=subject, body=body, recipients=[recipient_email], cfg=cfg)
    except Exception:
        pass


class ProfilePage(QWidget):
    def __init__(self, session: Session, caller: UserSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._caller = caller
        self._build()
        self._load()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(4)

        # Page title
        title = QLabel("My Profile")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        root.addWidget(title)

        # Current user info badge
        self._info_label = QLabel()
        self._info_label.setStyleSheet(
            "color: #64748b; font-size: 12px; margin-bottom: 8px;"
        )
        root.addWidget(self._info_label)

        root.addWidget(_divider())
        root.addSpacing(8)

        # ---- Section 1: Personal Info ----
        root.addWidget(_section_header("PERSONAL INFORMATION"))
        root.addSpacing(6)
        form1 = QFormLayout()
        form1.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Your full name")
        self._role_label = QLabel()
        self._role_label.setStyleSheet("color: #64748b;")

        form1.addRow("Full Name", self._name_edit)
        form1.addRow("Role", self._role_label)
        root.addLayout(form1)

        save_name_btn = QPushButton("Save Name")
        save_name_btn.setFixedWidth(120)
        save_name_btn.clicked.connect(self._save_name)
        root.addWidget(save_name_btn)

        root.addSpacing(16)
        root.addWidget(_divider())
        root.addSpacing(8)

        # ---- Section 2: Change Email ----
        root.addWidget(_section_header("CHANGE EMAIL ADDRESS"))
        root.addSpacing(4)
        root.addWidget(QLabel(
            "A verification link will be sent to the new address. You will need to\n"
            "click it and set a new password to confirm the change."
        ))
        root.addSpacing(6)
        form2 = QFormLayout()
        form2.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._current_email_label = QLabel()
        self._current_email_label.setStyleSheet("color: #64748b;")
        self._new_email_edit = QLineEdit()
        self._new_email_edit.setPlaceholderText("new@example.com")
        self._email_current_pw = QLineEdit()
        self._email_current_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._email_current_pw.setPlaceholderText("Current password (required to confirm)")

        form2.addRow("Current Email", self._current_email_label)
        form2.addRow("New Email", self._new_email_edit)
        form2.addRow("Password", self._email_current_pw)
        root.addLayout(form2)

        send_verify_btn = QPushButton("Send Verification Link")
        send_verify_btn.setFixedWidth(180)
        send_verify_btn.clicked.connect(self._request_email_change)
        root.addWidget(send_verify_btn)

        root.addSpacing(16)
        root.addWidget(_divider())
        root.addSpacing(8)

        # ---- Section 3: Change Password ----
        root.addWidget(_section_header("CHANGE PASSWORD"))
        root.addSpacing(6)
        form3 = QFormLayout()
        form3.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._old_pw = QLineEdit()
        self._old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._old_pw.setPlaceholderText("Current password")
        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setPlaceholderText("New password (min 8 characters)")
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw.setPlaceholderText("Confirm new password")

        form3.addRow("Current Password", self._old_pw)
        form3.addRow("New Password", self._new_pw)
        form3.addRow("Confirm", self._confirm_pw)
        root.addLayout(form3)

        change_pw_btn = QPushButton("Change Password")
        change_pw_btn.setFixedWidth(150)
        change_pw_btn.clicked.connect(self._change_password)
        root.addWidget(change_pw_btn)

        root.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------ load

    def _load(self) -> None:
        from models.orm import User
        user = self._session.get(User, self._caller.user_id)
        if not user:
            return
        self._name_edit.setText(user.full_name or "")
        self._role_label.setText(user.role.value.capitalize())
        self._current_email_label.setText(user.email)
        self._info_label.setText(
            f"{user.full_name or user.email}  ·  {user.role.value}"
        )

    # ------------------------------------------------------------------ actions

    def _save_name(self) -> None:
        from services.user_service import update_user_info
        from models.orm import User

        new_name = self._name_edit.text().strip()
        try:
            update_user_info(self._session, self._caller, self._caller.user_id,
                             full_name=new_name)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        user = self._session.get(User, self._caller.user_id)
        self._load()

        # Notification email
        _send_notification(
            self._caller.email,
            "Your display name was updated — Product License Timer",
            f"Hello,\n\n"
            f"Your display name on Product License Timer has been updated to:\n\n"
            f"    {new_name or '(cleared)'}\n\n"
            f"If you did not make this change, contact your administrator.\n",
        )
        QMessageBox.information(self, "Saved", "Your name has been updated.")

    def _request_email_change(self) -> None:
        from services.auth_service import create_email_change_token
        from services.verification_server import make_email_change_link
        from services.notification_service import _send_smtp, get_smtp_config

        new_email = self._new_email_edit.text().strip()
        current_pw = self._email_current_pw.text()

        if not new_email:
            QMessageBox.warning(self, "Error", "Please enter the new email address.")
            return
        if not current_pw:
            QMessageBox.warning(self, "Error", "Please enter your current password.")
            return

        try:
            token = create_email_change_token(
                self._session, self._caller.user_id, new_email, current_pw
            )
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        if token is None:
            QMessageBox.warning(self, "Incorrect Password",
                                "The current password you entered is incorrect.")
            return

        link = make_email_change_link(token)
        cfg = get_smtp_config()
        sent = False
        if cfg.get("smtp_host") and cfg.get("smtp_user"):
            sent = _send_smtp(
                subject="Confirm your email address change — Product License Timer",
                body=(
                    f"Hello,\n\n"
                    f"A request was made to change the email address for your "
                    f"Product License Timer account to this address.\n\n"
                    f"Click the link below to confirm the change and set a new password:\n\n"
                    f"    {link}\n\n"
                    f"This link expires in 24 hours and can only be used once.\n"
                    f"If you did not request this, ignore this email — "
                    f"your account remains unchanged.\n"
                ),
                recipients=[new_email],
                cfg=cfg,
            )

        self._new_email_edit.clear()
        self._email_current_pw.clear()

        if sent:
            QMessageBox.information(
                self, "Verification Sent",
                f"A confirmation link has been sent to {new_email}.\n\n"
                f"Click the link in the email to confirm the change and set your new password.\n"
                f"After confirming, please log out and log back in with your new email address."
            )
        else:
            # SMTP not configured — show link for admin to share
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox
            dlg = QDialog(self)
            dlg.setWindowTitle("Verification Link")
            dlg.setMinimumWidth(540)
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(
                f"SMTP is not configured. Share this link with {new_email}:\n"
                f"(The app must be running for the link to work.)"
            ))
            box = QLineEdit(link)
            box.setReadOnly(True)
            box.selectAll()
            layout.addWidget(box)
            layout.addWidget(QLabel("Expires in 24 hours."))
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btns.accepted.connect(dlg.accept)
            layout.addWidget(btns)
            dlg.exec()

    def _change_password(self) -> None:
        from services.auth_service import change_password
        from models.orm import User

        old_pw = self._old_pw.text()
        new_pw = self._new_pw.text()
        confirm = self._confirm_pw.text()

        if not old_pw:
            QMessageBox.warning(self, "Error", "Please enter your current password.")
            return
        if len(new_pw) < 8:
            QMessageBox.warning(self, "Error", "New password must be at least 8 characters.")
            return
        if new_pw != confirm:
            QMessageBox.warning(self, "Error", "New passwords do not match.")
            return

        ok = change_password(self._session, self._caller.user_id, old_pw, new_pw)
        if not ok:
            QMessageBox.warning(self, "Incorrect Password",
                                "The current password you entered is incorrect.")
            return

        self._old_pw.clear()
        self._new_pw.clear()
        self._confirm_pw.clear()

        user = self._session.get(User, self._caller.user_id)
        display = (user.full_name or self._caller.email) if user else self._caller.email

        # Generate a secure-account token so the user can lock their account
        # from the notification email if they did not make this change.
        from services.auth_service import create_account_secure_token
        from services.verification_server import make_account_secure_link
        secure_token = create_account_secure_token(
            self._session, self._caller.user_id,
            triggered_from_email=self._caller.email,
        )
        secure_link = make_account_secure_link(secure_token)

        _send_notification(
            self._caller.email,
            "Your password was changed — Product License Timer",
            f"Hello {display},\n\n"
            f"Your password for Product License Timer was changed successfully.\n\n"
            f"If you did NOT make this change, click the link below immediately.\n"
            f"Your account will be locked at once and your administrator will be notified:\n\n"
            f"    {secure_link}\n\n"
            f"This security link expires in 72 hours and can only be used once.\n"
            f"If you made this change yourself, you can ignore this email.\n",
        )
        QMessageBox.information(self, "Password Changed",
                                "Your password has been updated successfully.")
