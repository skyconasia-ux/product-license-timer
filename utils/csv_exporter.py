"""
CSV export utility. Opens a QFileDialog and writes all product rows.
Single responsibility: serialize product list to CSV file.
"""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import QFileDialog, QWidget

from utils.date_utils import days_remaining


FIELDNAMES = [
    "id", "name", "customer_name", "order_number",
    "start_date", "duration_days", "expiry_date",
    "days_remaining", "notes",
]


def export_to_csv(products: List[dict], parent: QWidget = None) -> bool:
    """
    Open a save-file dialog and write products to CSV.
    Returns True if the file was written, False if user cancelled.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Export to CSV",
        str(Path.home() / "license_export.csv"),
        "CSV Files (*.csv)",
    )
    if not path:
        return False

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for p in products:
            expiry = date.fromisoformat(p["expiry_date"])
            row = {k: p.get(k, "") for k in FIELDNAMES}
            row["days_remaining"] = days_remaining(expiry)
            writer.writerow(row)
    return True
