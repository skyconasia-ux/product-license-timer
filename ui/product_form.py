"""Add/Edit product dialog with ownership dropdowns and DD-MM-YYYY dates."""
from __future__ import annotations
from datetime import date, timedelta
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QDateEdit, QTextEdit, QDialogButtonBox, QLabel, QFrame,
    QComboBox, QMessageBox,
)
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.contact_service import list_contacts_by_role

UNASSIGNED = "— Unassigned —"
DATE_FORMAT = "dd-MM-yyyy"


def _date_to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _qdate_to_date(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class ProductForm(QDialog):
    def __init__(
        self,
        parent=None,
        product=None,
        session: Session | None = None,
        caller: UserSession | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Add Product" if product is None else "Edit Product")
        self.setMinimumWidth(440)
        self._product = product
        self._session = session
        self._caller = caller
        self._build()
        if product:
            self._populate(product)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        # Core fields
        self._name = QLineEdit()
        self._customer = QLineEdit()
        self._order = QLineEdit()

        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDisplayFormat(DATE_FORMAT)
        self._start_date.setDate(QDate.currentDate())
        self._start_date.dateChanged.connect(self._update_expiry_preview)

        self._duration = QSpinBox()
        self._duration.setRange(1, 3650)
        self._duration.setValue(90)
        self._duration.valueChanged.connect(self._update_expiry_preview)

        self._expiry_preview = QLabel()
        self._expiry_preview.setStyleSheet("color: #64748b;")
        self._update_expiry_preview()

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(64)

        form.addRow("Product Name *", self._name)
        form.addRow("Customer Name", self._customer)
        form.addRow("Order Number", self._order)
        form.addRow("Start Date", self._start_date)
        form.addRow("Duration (days)", self._duration)
        form.addRow("Expiry Date", self._expiry_preview)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)

        # Ownership section
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(divider)

        ownership_label = QLabel("OWNERSHIP (OPTIONAL)")
        ownership_label.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #64748b; letter-spacing: 1px;"
        )
        layout.addWidget(ownership_label)

        own_form = QFormLayout()
        self._consultant = self._make_contact_combo("Consultant")
        self._technical_consultant = self._make_contact_combo("Technical Consultant")
        self._account_manager = self._make_contact_combo("Account Manager")
        self._project_manager = self._make_contact_combo("Project Manager")
        own_form.addRow("Consultant", self._consultant)
        own_form.addRow("Technical Consultant", self._technical_consultant)
        own_form.addRow("Account Manager", self._account_manager)
        own_form.addRow("Project Manager", self._project_manager)
        layout.addLayout(own_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_contact_combo(self, role: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(UNASSIGNED, userData=None)
        if self._session:
            for c in list_contacts_by_role(self._session, role):
                combo.addItem(c.name, userData=c.id)
        return combo

    def _update_expiry_preview(self) -> None:
        start = _qdate_to_date(self._start_date.date())
        days = self._duration.value()
        expiry = start + timedelta(days=days)
        self._expiry_preview.setText(expiry.strftime("%d-%m-%Y"))

    def _populate(self, product) -> None:
        # Support both ORM Product and legacy dict
        def g(key, default=""):
            if isinstance(product, dict):
                return product.get(key, default)
            return getattr(product, key, default)

        self._name.setText(g("product_name") or g("name"))
        self._customer.setText(g("customer_name"))
        self._order.setText(g("order_number"))
        sd = g("start_date")
        if isinstance(sd, str):
            sd = date.fromisoformat(sd)
        if sd:
            self._start_date.setDate(_date_to_qdate(sd))
        self._duration.setValue(int(g("duration_days", 90)))
        self._notes.setPlainText(g("notes"))

        for combo, key in [
            (self._consultant, "consultant_id"),
            (self._technical_consultant, "technical_consultant_id"),
            (self._account_manager, "account_manager_id"),
            (self._project_manager, "project_manager_id"),
        ]:
            cid = g(key)
            if cid:
                for i in range(combo.count()):
                    if combo.itemData(i) == cid:
                        combo.setCurrentIndex(i)
                        break

    def _validate(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Product name is required.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "product_name": self._name.text().strip(),
            "customer_name": self._customer.text().strip(),
            "order_number": self._order.text().strip(),
            "start_date": _qdate_to_date(self._start_date.date()),
            "duration_days": self._duration.value(),
            "notes": self._notes.toPlainText().strip(),
            "consultant_id": self._consultant.currentData(),
            "technical_consultant_id": self._technical_consultant.currentData(),
            "account_manager_id": self._account_manager.currentData(),
            "project_manager_id": self._project_manager.currentData(),
        }
