"""System recipients management page. Admin+ only."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QToolBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.contact_service import (
    add_recipient, update_recipient, delete_recipient,
    list_recipients, toggle_recipient,
)

ROLES = ["Solutions Team", "Admin", "Support"]
COLS = ["Name", "Email", "Role", "Active"]


class _RecipientForm(QDialog):
    def __init__(self, parent=None, recipient=None):
        super().__init__(parent)
        self.setWindowTitle("Recipient" if recipient is None else "Edit Recipient")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit(recipient.name if recipient else "")
        self._email = QLineEdit(recipient.email if recipient else "")
        self._role = QComboBox()
        self._role.addItems(ROLES)
        if recipient:
            try:
                idx = ROLES.index(recipient.role_type.value)
            except ValueError:
                idx = 0
            self._role.setCurrentIndex(idx)
        form.addRow("Name", self._name)
        form.addRow("Email", self._email)
        form.addRow("Role", self._role)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Name is required.")
            return
        if "@" not in self._email.text():
            QMessageBox.warning(self, "Error", "Invalid email.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "email": self._email.text().strip(),
            "role_type": self._role.currentText(),
        }


class RecipientsPage(QWidget):
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
        for label, slot in [
            ("+ Add", self._add), ("✏ Edit", self._edit),
            ("🗑 Delete", self._delete), ("⏺ Toggle Active", self._toggle),
        ]:
            a = QAction(label, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._edit)

        layout.addWidget(tb)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        recipients = list_recipients(self._session)
        self._recipients = recipients
        self._table.setRowCount(0)
        for row, r in enumerate(recipients):
            self._table.insertRow(row)
            for col, val in enumerate([r.name, r.email, r.role_type.value,
                                        "Yes" if r.is_active else "No"]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, r.id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self) -> None:
        dlg = _RecipientForm(self)
        if dlg.exec():
            try:
                add_recipient(self._session, self._caller, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, "No Selection", "Select a recipient to edit.")
            return
        r = next((x for x in self._recipients if x.id == rid), None)
        dlg = _RecipientForm(self, recipient=r)
        if dlg.exec():
            try:
                update_recipient(self._session, self._caller, rid, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, "No Selection", "Select a recipient to delete.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this recipient?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_recipient(self._session, self._caller, rid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _toggle(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, "No Selection", "Select a recipient to toggle.")
            return
        try:
            toggle_recipient(self._session, self._caller, rid)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
