"""
Modal QDialog for adding or editing a product.
Single responsibility: collect and validate product input fields.
"""
from __future__ import annotations
from datetime import date
from typing import Optional

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QDateEdit, QTextEdit, QVBoxLayout,
    QMessageBox,
)

from utils.date_utils import calculate_expiry_date


class ProductForm(QDialog):
    def __init__(self, parent=None, product: Optional[dict] = None):
        """
        Pass product=None for Add mode.
        Pass a product dict (from DatabaseService.get_product) for Edit mode.
        """
        super().__init__(parent)
        self._product = product
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setMinimumWidth(420)
        self._build_ui()
        if product:
            self._populate(product)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Equitrac 6")

        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Customer or company name")

        self.order_input = QLineEdit()
        self.order_input.setPlaceholderText("e.g. ORD-2026-001")

        self.start_date_input = QDateEdit(calendarPopup=True)
        self.start_date_input.setDate(QDate.currentDate())
        self.start_date_input.setDisplayFormat("yyyy-MM-dd")

        self.duration_input = QSpinBox()
        self.duration_input.setRange(1, 3650)
        self.duration_input.setValue(30)
        self.duration_input.setSuffix(" days")

        self.expiry_preview = QLabel()
        self.expiry_preview.setStyleSheet("color: #666; font-style: italic;")

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        self.notes_input.setPlaceholderText("Optional notes...")

        form.addRow("Product Name *", self.name_input)
        form.addRow("Customer Name", self.customer_input)
        form.addRow("Order Number", self.order_input)
        form.addRow("Start Date", self.start_date_input)
        form.addRow("Duration", self.duration_input)
        form.addRow("Expiry Date (preview)", self.expiry_preview)
        form.addRow("Notes", self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

        # Live expiry preview
        self.start_date_input.dateChanged.connect(self._update_expiry_preview)
        self.duration_input.valueChanged.connect(self._update_expiry_preview)
        self._update_expiry_preview()

    def _update_expiry_preview(self) -> None:
        qd = self.start_date_input.date()
        start = date(qd.year(), qd.month(), qd.day())
        expiry = calculate_expiry_date(start, self.duration_input.value())
        self.expiry_preview.setText(expiry.isoformat())

    def _populate(self, product: dict) -> None:
        """Fill all fields from an existing product dict."""
        self.name_input.setText(product.get("name", ""))
        self.customer_input.setText(product.get("customer_name", ""))
        self.order_input.setText(product.get("order_number", ""))
        sd = date.fromisoformat(product["start_date"])
        self.start_date_input.setDate(QDate(sd.year, sd.month, sd.day))
        self.duration_input.setValue(product.get("duration_days", 30))
        self.notes_input.setPlainText(product.get("notes", ""))

    def _on_save(self) -> None:
        if not self.name_input.text().strip():
            self.name_input.setStyleSheet("border: 1px solid red;")
            self.name_input.setFocus()
            return
        self.name_input.setStyleSheet("")
        self.accept()

    def get_data(self) -> dict:
        """Return validated form data as a dict ready for DatabaseService."""
        qd = self.start_date_input.date()
        return {
            "name": self.name_input.text().strip(),
            "customer_name": self.customer_input.text().strip(),
            "order_number": self.order_input.text().strip(),
            "start_date": date(qd.year(), qd.month(), qd.day()),
            "duration_days": self.duration_input.value(),
            "notes": self.notes_input.toPlainText().strip(),
        }
