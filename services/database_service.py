"""
CRUD operations for products and notification log.
Single responsibility: all database reads and writes go through this service.
"""
from __future__ import annotations
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from models.database import get_connection, initialize_db, DB_PATH
from utils.date_utils import calculate_expiry_date


class DatabaseService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        initialize_db(db_path)

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    # ---------------------------------------------------------------- Products

    def add_product(
        self,
        name: str,
        start_date: date,
        duration_days: int,
        customer_name: str = "",
        order_number: str = "",
        notes: str = "",
    ) -> int:
        """Insert a new product. Returns the new row id."""
        expiry = calculate_expiry_date(start_date, duration_days)
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO products
                   (name, customer_name, order_number, start_date, duration_days, expiry_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, customer_name, order_number,
                 start_date.isoformat(), duration_days,
                 expiry.isoformat(), notes),
            )
            return cursor.lastrowid

    def update_product(
        self,
        product_id: int,
        name: str,
        start_date: date,
        duration_days: int,
        customer_name: str = "",
        order_number: str = "",
        notes: str = "",
    ) -> None:
        """Update all fields of an existing product by id."""
        expiry = calculate_expiry_date(start_date, duration_days)
        with self._conn() as conn:
            conn.execute(
                """UPDATE products SET
                   name=?, customer_name=?, order_number=?,
                   start_date=?, duration_days=?, expiry_date=?, notes=?
                   WHERE id=?""",
                (name, customer_name, order_number,
                 start_date.isoformat(), duration_days,
                 expiry.isoformat(), notes, product_id),
            )

    def delete_product(self, product_id: int) -> None:
        """Delete a product (and its notification log via CASCADE)."""
        with self._conn() as conn:
            conn.execute("DELETE FROM products WHERE id=?", (product_id,))

    def delete_expired_products(self) -> int:
        """Delete all products whose expiry_date < today. Returns count deleted."""
        today = date.today().isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM products WHERE expiry_date < ?", (today,)
            )
            return cursor.rowcount

    def get_all_products(self) -> List[dict]:
        """Return all products ordered by expiry_date ascending."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY expiry_date ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_product(self, product_id: int) -> Optional[dict]:
        """Return a single product dict, or None if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE id=?", (product_id,)
            ).fetchone()
            return dict(row) if row else None

    # ---------------------------------------------------------- Notifications

    def notification_sent(self, product_id: int, notification_type: str) -> bool:
        """Return True if this threshold alert was already sent for this product."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT 1 FROM notifications_log
                   WHERE product_id=? AND notification_type=?""",
                (product_id, notification_type),
            ).fetchone()
            return row is not None

    def log_notification(self, product_id: int, notification_type: str) -> None:
        """Record that a notification was sent. Silently ignores duplicates."""
        with self._conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO notifications_log (product_id, notification_type, sent_at)
                       VALUES (?, ?, ?)""",
                    (product_id, notification_type, datetime.now().isoformat()),
                )
            except sqlite3.IntegrityError:
                pass  # UNIQUE constraint hit -- already logged, safe to ignore
