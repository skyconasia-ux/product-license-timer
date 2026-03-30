"""
QTableWidget displaying all tracked products with live countdowns.
Single responsibility: render and filter the product list -- no DB access.
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

from utils.date_utils import days_remaining, format_countdown, get_row_color, remaining_seconds

# Column index constants
COL_ID        = 0
COL_NAME      = 1
COL_CUSTOMER  = 2
COL_ORDER     = 3
COL_START     = 4
COL_DURATION  = 5
COL_EXPIRY    = 6
COL_DAYS      = 7
COL_REMAINING = 8
COL_STATUS    = 9

COLUMNS = [
    "ID", "Product Name", "Customer", "Order #",
    "Start Date", "Duration", "Expiry Date",
    "Days Left", "Remaining Time", "Status",
]


class ProductTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setColumnHidden(COL_ID, True)   # ID hidden -- used only for lookups
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_REMAINING, QHeaderView.ResizeMode.ResizeToContents)
        self.setSortingEnabled(True)
        self._all_products: List[dict] = []
        self._filter_text: str = ""

    def refresh(self, products: List[dict]) -> None:
        """Reload all rows from the given product list."""
        self._all_products = products
        self._render(self._filtered(products))

    def apply_filter(self, text: str) -> None:
        """Filter visible rows by name, customer, or order number (case-insensitive)."""
        self._filter_text = text.lower().strip()
        self._render(self._filtered(self._all_products))

    def _filtered(self, products: List[dict]) -> List[dict]:
        if not self._filter_text:
            return products
        return [
            p for p in products
            if self._filter_text in p.get("name", "").lower()
            or self._filter_text in p.get("customer_name", "").lower()
            or self._filter_text in p.get("order_number", "").lower()
        ]

    def _render(self, products: List[dict]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(products))

        for row, p in enumerate(products):
            expiry = date.fromisoformat(p["expiry_date"])
            days_left = days_remaining(expiry)
            secs = remaining_seconds(expiry)
            countdown, is_expired = format_countdown(secs)

            if is_expired:
                status = "EXPIRED"
            elif days_left <= 5:
                status = "CRITICAL"
            elif days_left <= 10:
                status = "WARNING"
            elif days_left <= 15:
                status = "MONITOR"
            else:
                status = "OK"

            color = get_row_color(days_left)

            values = [
                str(p["id"]),
                p.get("name", ""),
                p.get("customer_name", ""),
                p.get("order_number", ""),
                p.get("start_date", ""),
                f"{p.get('duration_days', '')} days",
                p.get("expiry_date", ""),
                str(days_left),
                countdown,
                status,
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setBackground(QColor(color))
                if is_expired:
                    font = QFont()
                    font.setItalic(True)
                    item.setFont(font)
                self.setItem(row, col, item)

        self.setSortingEnabled(True)

    def get_selected_product_id(self) -> Optional[int]:
        """Return the product id of the currently selected row, or None."""
        selected = self.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        id_item = self.item(row, COL_ID)
        return int(id_item.text()) if id_item else None
