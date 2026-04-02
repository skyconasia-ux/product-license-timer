"""Address book management page. Admin+ only."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QToolBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.contact_service import (
    add_contact, update_contact, delete_contact, list_contacts,
)

ROLES = ["Consultant", "Account Manager", "Project Manager"]
COLS = ["Name", "Email", "Role"]


class _ContactForm(QDialog):
    def __init__(self, parent=None, contact=None):
        super().__init__(parent)
        self.setWindowTitle("Contact" if contact is None else "Edit Contact")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit(contact.name if contact else "")
        self._email = QLineEdit(contact.email if contact else "")
        self._role = QComboBox()
        self._role.addItems(ROLES)
        if contact:
            try:
                idx = ROLES.index(contact.role_type.value)
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


class ContactsPage(QWidget):
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
        for label, slot in [("+ Add", self._add), ("✏ Edit", self._edit), ("🗑 Delete", self._delete)]:
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
        contacts = list_contacts(self._session)
        self._table.setRowCount(0)
        self._contacts = contacts
        for row, c in enumerate(contacts):
            self._table.insertRow(row)
            for col, val in enumerate([c.name, c.email, c.role_type.value]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self) -> None:
        dlg = _ContactForm(self)
        if dlg.exec():
            try:
                add_contact(self._session, self._caller, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            QMessageBox.information(self, "No Selection", "Select a contact to edit.")
            return
        contact = next((c for c in self._contacts if c.id == cid), None)
        dlg = _ContactForm(self, contact=contact)
        if dlg.exec():
            try:
                update_contact(self._session, self._caller, cid, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            QMessageBox.information(self, "No Selection", "Select a contact to delete.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this contact?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_contact(self._session, self._caller, cid)
            self.refresh()
