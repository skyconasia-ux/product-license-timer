"""
Raw SQLite connection and schema initialization.
Single responsibility: database connection and schema only.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "licenses.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a connection with foreign keys enabled and row_factory set to Row."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they do not exist. Safe to call multiple times."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL UNIQUE,
                customer_name   TEXT DEFAULT '',
                order_number    TEXT DEFAULT '',
                start_date      DATE NOT NULL,
                duration_days   INTEGER NOT NULL CHECK(duration_days > 0),
                expiry_date     DATE NOT NULL,
                notes           TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS notifications_log (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                notification_type   TEXT NOT NULL CHECK(notification_type IN ('15_days','10_days','5_days')),
                sent_at             DATETIME NOT NULL,
                UNIQUE(product_id, notification_type)
            );
        """)
