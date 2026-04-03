"""User management page. Admin+ only."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QToolBar, QLabel,
    QCheckBox, QMenu,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.user_service import (
    create_user, promote_to_admin, demote_admin,
    delete_user, list_users, set_active, update_user_info,
)

COLS = ["Name", "Email", "Role", "Verified", "Status"]


class _UserForm(QDialog):
    """Create new user — name, email, role only. Password is set by the user via email link."""
    def __init__(self, parent=None, caller: UserSession | None = None):
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("Full name (optional)")

        self._email = QLineEdit()
        self._email.setPlaceholderText("user@company.com")

        self._role = QComboBox()
        roles = ["user", "admin"] if caller and caller.role in ("admin", "superadmin") else ["user"]
        self._role.addItems(roles)

        form.addRow("Name", self._name)
        form.addRow("Email", self._email)
        form.addRow("Role", self._role)
        layout.addLayout(form)

        note = QLabel(
            "A verification link will be emailed to the user.\n"
            "They must click it to set their password and activate their account."
        )
        note.setStyleSheet("color: #64748b; font-size: 10px;")
        note.setWordWrap(True)
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
        self.accept()

    def get_data(self) -> dict:
        return {
            "full_name": self._name.text().strip(),
            "email": self._email.text().strip(),
            "role": self._role.currentText(),
        }


class _UserPropertiesDialog(QDialog):
    """View and edit user properties."""
    def __init__(self, user, session: Session, caller: UserSession, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Properties")
        self.setMinimumWidth(400)
        self._user = user
        self._session = session
        self._caller = caller
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()

        self._full_name = QLineEdit(self._user.full_name or "")
        self._full_name.setPlaceholderText("Full name")

        self._email = QLineEdit(self._user.email)
        self._email.setReadOnly(True)
        self._email.setStyleSheet("color: #64748b;")

        self._role_label = QLabel(self._user.role.value)
        self._role_label.setStyleSheet("font-weight: bold;")

        is_superadmin = self._user.role.value == "superadmin"
        is_admin = self._user.role.value in ("admin", "superadmin")

        self._make_admin = QCheckBox("Make Admin")
        self._make_admin.setChecked(is_admin)
        if is_superadmin:
            self._make_admin.setEnabled(False)
            self._make_admin.setToolTip("Cannot change superadmin role")

        self._disable_account = QCheckBox("Disable Account")
        self._disable_account.setChecked(not self._user.is_active)
        if is_superadmin and self._caller.role != "superadmin":
            self._disable_account.setEnabled(False)

        form.addRow("Full Name", self._full_name)
        form.addRow("Email", self._email)
        form.addRow("Current Role", self._role_label)
        form.addRow("", self._make_admin)
        form.addRow("", self._disable_account)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self) -> None:
        try:
            update_user_info(self._session, self._caller, self._user.id,
                             full_name=self._full_name.text())

            is_superadmin = self._user.role.value == "superadmin"
            if not is_superadmin:
                currently_admin = self._user.role.value == "admin"
                want_admin = self._make_admin.isChecked()
                if want_admin and not currently_admin:
                    promote_to_admin(self._session, self._caller, self._user.id)
                elif not want_admin and currently_admin:
                    demote_admin(self._session, self._caller, self._user.id)

            want_active = not self._disable_account.isChecked()
            if want_active != self._user.is_active:
                set_active(self._session, self._caller, self._user.id, want_active)

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class UsersPage(QWidget):
    def __init__(self, session: Session, caller: UserSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._caller = caller
        self._users: list = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        tb = QToolBar()
        tb.setMovable(False)
        add_action = QAction("+ Add User", self)
        add_action.triggered.connect(self._add_user)
        tb.addAction(add_action)

        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.doubleClicked.connect(self._open_properties)

        layout.addWidget(tb)
        layout.addWidget(self._table)

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
                u.full_name or "",
                u.email,
                u.role.value,
                "Yes" if u.is_verified else "No",
                "Active" if u.is_active else "Disabled",
            ]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, u.id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _get_user(self, user_id: int):
        return next((u for u in self._users if u.id == user_id), None)

    def _show_context_menu(self, pos) -> None:
        uid = self._selected_id()
        if uid is None:
            return
        user = self._get_user(uid)
        if user is None:
            return

        is_superadmin = user.role.value == "superadmin"
        is_admin = user.role.value == "admin"
        caller_is_superadmin = self._caller.role == "superadmin"

        menu = QMenu(self)

        edit_act = menu.addAction("Edit")
        menu.addSeparator()

        make_admin_act = None
        remove_admin_act = None
        if not is_superadmin and not is_admin:
            make_admin_act = menu.addAction("Make Admin")
        if is_admin:
            remove_admin_act = menu.addAction("Remove Admin")

        menu.addSeparator()
        disable_act = None
        enable_act = None
        if user.is_active:
            disable_act = menu.addAction("Disable Account")
        else:
            enable_act = menu.addAction("Enable Account")

        menu.addSeparator()
        resend_act = menu.addAction("Resend Verification Link") if not user.is_verified else None

        if caller_is_superadmin:
            if not user.is_verified:
                verify_act = menu.addAction("✓ Verify Manually")
            else:
                verify_act = None
            menu.addSeparator()
            delete_act = menu.addAction("Delete")
        else:
            verify_act = None
            delete_act = None

        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == edit_act:
            self._open_properties()
        elif make_admin_act and chosen == make_admin_act:
            self._confirm_action(
                f"Make {user.email} an admin?",
                lambda: promote_to_admin(self._session, self._caller, uid),
            )
        elif remove_admin_act and chosen == remove_admin_act:
            self._confirm_action(
                f"Remove admin from {user.email}?",
                lambda: demote_admin(self._session, self._caller, uid),
            )
        elif disable_act and chosen == disable_act:
            self._confirm_action(
                f"Disable account for {user.email}?",
                lambda: set_active(self._session, self._caller, uid, False),
            )
        elif enable_act and chosen == enable_act:
            self._confirm_action(
                f"Enable account for {user.email}?",
                lambda: set_active(self._session, self._caller, uid, True),
            )
        elif resend_act and chosen == resend_act:
            self._resend_link(uid)
        elif verify_act and chosen == verify_act:
            self._verify_user(uid)
        elif delete_act and chosen == delete_act:
            self._delete_user(uid)

    def _confirm_action(self, message: str, action) -> None:
        reply = QMessageBox.question(
            self, "Confirm", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                action()
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _open_properties(self) -> None:
        uid = self._selected_id()
        if uid is None:
            return
        user = self._get_user(uid)
        if user is None:
            return
        dlg = _UserPropertiesDialog(user, self._session, self._caller, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _show_link_dialog(self, email: str, link: str) -> None:
        """Show the verification link in a selectable dialog so admin can copy/share it."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Verification Link")
        dlg.setMinimumWidth(520)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.addWidget(QLabel(
            f"SMTP is not configured. Share this activation link with <b>{email}</b>:\n"
            f"(The app must be running for the link to work.)"
        ))
        link_box = QLineEdit(link)
        link_box.setReadOnly(True)
        link_box.selectAll()
        layout.addWidget(link_box)
        layout.addWidget(QLabel("This link expires in 24 hours."))
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)
        dlg.exec()

    def _resend_link(self, uid: int) -> None:
        user = self._get_user(uid)
        if not user:
            return
        if user.is_verified:
            QMessageBox.information(self, "Already Verified",
                                    "This account is already verified.")
            return
        self._send_verification_link(user.email, resend=True)

    def _verify_user(self, uid: int) -> None:
        from models.orm import User
        u = self._session.get(User, uid)
        if u:
            u.is_verified = True
            self._session.commit()
            self.refresh()

    def _delete_user(self, uid: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this user? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_user(self._session, self._caller, uid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _add_user(self) -> None:
        dlg = _UserForm(self, caller=self._caller)
        if dlg.exec():
            data = dlg.get_data()
            try:
                import secrets
                temp_pw = secrets.token_urlsafe(24)  # random, unshared — replaced on verification
                create_user(self._session, self._caller,
                            email=data["email"],
                            password=temp_pw,
                            role=data["role"],
                            full_name=data["full_name"])
                self._send_verification_link(data["email"])
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _send_verification_link(self, email: str, resend: bool = False) -> None:
        """Generate a verification token and email the activation link to the user."""
        from models.orm import User
        from services.auth_service import create_verification_token
        from services.notification_service import _send_smtp, get_smtp_config
        from services.verification_server import make_verify_link

        u = self._session.query(User).filter_by(email=email).first()
        if not u:
            return

        token = create_verification_token(self._session, u.id)
        link = make_verify_link(token)
        action = "resent" if resend else "sent"

        cfg = get_smtp_config()
        sent = False
        if cfg.get("smtp_host") and cfg.get("smtp_user"):
            name_part = f"Hello {u.full_name},\n\n" if u.full_name else "Hello,\n\n"
            sent = _send_smtp(
                subject="Activate your Product License Timer account",
                body=(
                    f"{name_part}"
                    f"Your account ({email}) has been created on Product License Timer.\n\n"
                    f"Click the link below to set your password and activate your account:\n\n"
                    f"    {link}\n\n"
                    f"This link expires in 24 hours and can only be used once.\n"
                    f"Once activated, open the app and log in with your email address.\n\n"
                    f"If you did not expect this email, please ignore it.\n"
                ),
                recipients=[email],
                cfg=cfg,
            )

        if sent:
            QMessageBox.information(
                self, "Verification Link Sent",
                f"Activation email {action} to {email}.\n\n"
                f"The user must click the link to set their password."
            )
        else:
            # SMTP not configured — show link so admin can share it another way
            self._show_link_dialog(email, link)
