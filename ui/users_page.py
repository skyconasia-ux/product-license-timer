"""User management page. Admin+ only."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QDialogButtonBox, QMessageBox, QToolBar, QLabel, QMenu,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.user_service import (
    create_user, promote_to_admin, demote_admin,
    delete_user, list_users, reset_password, set_active, change_email,
)

COLS = ["Email", "Role", "Verified", "Active"]


class _UserForm(QDialog):
    """Create new user — email + password + role."""
    def __init__(self, parent=None, caller: UserSession | None = None):
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._email = QLineEdit()
        self._email.setPlaceholderText("user@company.com")

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Min 8 characters")

        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm.setPlaceholderText("Repeat password")

        self._role = QComboBox()
        roles = ["user", "admin"] if caller and caller.role in ("admin", "superadmin") else ["user"]
        self._role.addItems(roles)

        note = QLabel("User will need to verify their email before logging in.\n"
                      "Use 'Resend Verification' if email is not received.")
        note.setStyleSheet("color: #64748b; font-size: 10px;")
        note.setWordWrap(True)

        form.addRow("Email", self._email)
        form.addRow("Password", self._password)
        form.addRow("Confirm", self._confirm)
        form.addRow("Role", self._role)
        layout.addLayout(form)
        layout.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self) -> None:
        if "@" not in self._email.text():
            QMessageBox.warning(self, "Error", "Invalid email address.")
            return
        if len(self._password.text()) < 8:
            QMessageBox.warning(self, "Error", "Password must be at least 8 characters.")
            return
        if self._password.text() != self._confirm.text():
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "email": self._email.text().strip(),
            "password": self._password.text(),
            "role": self._role.currentText(),
        }


class _EditUserDialog(QDialog):
    """Edit existing user — role, active, password reset, email (superadmin)."""
    def __init__(self, user, caller: UserSession, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit User — {user.email}")
        self.setMinimumWidth(380)
        self._user = user
        self._caller = caller
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._email = QLineEdit(user.email)
        self._email.setEnabled(caller.role == "superadmin")

        self._role = QComboBox()
        if caller.role == "superadmin":
            roles = ["user", "admin", "superadmin"]
        else:
            roles = ["user", "admin"]
        self._role.addItems(roles)
        try:
            self._role.setCurrentIndex(roles.index(user.role.value))
        except ValueError:
            self._role.setCurrentIndex(0)

        self._active = QCheckBox("Active")
        self._active.setChecked(user.is_active)

        self._verified = QCheckBox("Verified")
        self._verified.setChecked(user.is_verified)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Leave blank to keep current password")

        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm.setPlaceholderText("Confirm new password")

        form.addRow("Email", self._email)
        form.addRow("Role", self._role)
        form.addRow("", self._active)
        form.addRow("", self._verified)
        form.addRow("New Password", self._password)
        form.addRow("Confirm", self._confirm)
        layout.addLayout(form)

        if caller.role != "superadmin":
            note = QLabel("Email editing requires superadmin.")
            note.setStyleSheet("color: #64748b; font-size: 10px;")
            layout.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self) -> None:
        pw = self._password.text()
        if pw:
            if len(pw) < 8:
                QMessageBox.warning(self, "Error", "Password must be at least 8 characters.")
                return
            if pw != self._confirm.text():
                QMessageBox.warning(self, "Error", "Passwords do not match.")
                return
        self.accept()

    def get_data(self) -> dict:
        return {
            "email": self._email.text().strip(),
            "role": self._role.currentText(),
            "is_active": self._active.isChecked(),
            "is_verified": self._verified.isChecked(),
            "password": self._password.text() or None,
        }


class UsersPage(QWidget):
    def __init__(self, session: Session, caller: UserSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._caller = caller
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        tb = QToolBar()
        tb.setMovable(False)

        actions = [("+ Add User", self._add_user)]
        if self._caller.role in ("admin", "superadmin"):
            actions += [
                ("✏ Edit", self._edit_user),
                ("✓ Verify", self._verify_user),
                ("↑ Make Admin", self._promote),
            ]
        if self._caller.role == "superadmin":
            actions += [
                ("↓ Remove Admin", self._demote),
                ("🗑 Delete", self._delete_user),
            ]

        for label, slot in actions:
            a = QAction(label, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(lambda _: self._edit_user())
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(tb)
        layout.addWidget(self._table)

    def _show_context_menu(self, pos) -> None:
        if self._selected_id() is None:
            return
        menu = QMenu(self)
        menu.addAction("✏ Edit", self._edit_user)
        menu.addAction("✓ Verify", self._verify_user)
        menu.addAction("↑ Make Admin", self._promote)
        if self._caller.role == "superadmin":
            menu.addAction("↓ Remove Admin", self._demote)
            menu.addSeparator()
            menu.addAction("🗑 Delete", self._delete_user)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def refresh(self) -> None:
        try:
            users = list_users(self._session, self._caller)
        except Exception:
            users = []
        self._users = users
        self._table.setRowCount(0)
        for row, u in enumerate(users):
            self._table.insertRow(row)
            for col, val in enumerate([
                u.email,
                u.role.value,
                "Yes" if u.is_verified else "No",
                "Yes" if u.is_active else "No",
            ]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, u.id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add_user(self) -> None:
        dlg = _UserForm(self, caller=self._caller)
        if dlg.exec():
            data = dlg.get_data()
            try:
                create_user(self._session, self._caller,
                            email=data["email"],
                            password=data["password"],
                            role=data["role"])
                from models.orm import User
                from services.auth_service import create_verification_token
                from services.notification_service import _send_smtp, get_smtp_config
                u = self._session.query(User).filter_by(email=data["email"]).first()
                if u:
                    token = create_verification_token(self._session, u.id)
                    cfg = get_smtp_config()
                    sent = False
                    if cfg.get("smtp_host") and cfg.get("smtp_user"):
                        sent = _send_smtp(
                            subject="Verify your Product License Timer account",
                            body=(
                                f"Hello,\n\n"
                                f"Your account ({data['email']}) has been created.\n\n"
                                f"Your verification token is:\n\n"
                                f"    {token}\n\n"
                                f"Enter this token in the app using 'Verify Account' "
                                f"on the login screen.\n"
                                f"This token expires in 24 hours.\n"
                            ),
                            recipients=[data["email"]],
                            cfg=cfg,
                        )
                    if sent:
                        QMessageBox.information(
                            self, "User Created",
                            f"{data['email']} created.\n"
                            f"A verification email has been sent."
                        )
                    else:
                        QMessageBox.information(
                            self, "User Created",
                            f"{data['email']} created.\n\n"
                            f"Email could not be sent — verification token:\n\n"
                            f"{token}\n\n"
                            f"Share this with the user, or use 'Verify' to manually verify."
                        )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit_user(self) -> None:
        uid = self._selected_id()
        if uid is None:
            QMessageBox.information(self, "No Selection", "Select a user to edit.")
            return
        from models.orm import User, UserRole
        u = self._session.get(User, uid)
        if not u:
            return
        if u.role.value == "superadmin" and self._caller.role != "superadmin":
            QMessageBox.warning(self, "Permission Denied",
                                "Only a superadmin can edit a superadmin account.")
            return
        dlg = _EditUserDialog(u, caller=self._caller, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                # Email (superadmin only)
                if data["email"] != u.email:
                    change_email(self._session, self._caller, uid, data["email"])
                    self._session.refresh(u)
                # Role
                if data["role"] != u.role.value:
                    if data["role"] == "admin":
                        promote_to_admin(self._session, self._caller, uid)
                    elif data["role"] == "user":
                        demote_admin(self._session, self._caller, uid)
                    elif data["role"] == "superadmin" and self._caller.role == "superadmin":
                        u.role = UserRole.superadmin
                        self._session.commit()
                # Active
                if data["is_active"] != u.is_active:
                    set_active(self._session, self._caller, uid, data["is_active"])
                # Verified
                if data["is_verified"] != u.is_verified:
                    self._session.refresh(u)
                    u.is_verified = data["is_verified"]
                    self._session.commit()
                # Password reset
                if data["password"]:
                    reset_password(self._session, self._caller, uid, data["password"])
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _verify_user(self) -> None:
        uid = self._selected_id()
        if uid is None:
            QMessageBox.information(self, "No Selection", "Select a user to verify.")
            return
        from models.orm import User
        u = self._session.get(User, uid)
        if u:
            u.is_verified = True
            self._session.commit()
            self.refresh()

    def _promote(self) -> None:
        uid = self._selected_id()
        if uid is None:
            QMessageBox.information(self, "No Selection", "Select a user to promote.")
            return
        try:
            promote_to_admin(self._session, self._caller, uid)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _demote(self) -> None:
        uid = self._selected_id()
        if uid is None:
            QMessageBox.information(self, "No Selection", "Select an admin to demote.")
            return
        try:
            demote_admin(self._session, self._caller, uid)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _delete_user(self) -> None:
        uid = self._selected_id()
        if uid is None:
            QMessageBox.information(self, "No Selection", "Select a user to delete.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this user? This cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_user(self._session, self._caller, uid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
