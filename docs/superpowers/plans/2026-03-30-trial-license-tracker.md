# Trial License Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PyQt6 desktop app that tracks software trial license expiry dates with real-time countdowns, email alerts, and Windows system tray support.

**Architecture:** Modular MVC — `models/` owns SQLite schema, `services/` handles business logic (CRUD, timers, notifications), `ui/` owns all widgets. A `QTimer` in `timer_service.py` drives all updates via Qt signals. The UI never touches the DB directly.

**Tech Stack:** Python 3.13, PyQt6>=6.6.0, SQLite (stdlib), smtplib (stdlib), winreg (stdlib), pytest, pytest-qt

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | Entry point, `--minimized` flag, QApplication init |
| `models/database.py` | SQLite connection, schema creation |
| `services/database_service.py` | CRUD for products + notification log |
| `services/notification_service.py` | Email threshold alerts, duplicate guard |
| `services/timer_service.py` | QTimer wrapper, configurable interval |
| `ui/main_window.py` | QMainWindow shell, menus, toolbar, tray |
| `ui/product_table.py` | QTableWidget with live countdown rows |
| `ui/product_form.py` | Add/Edit QDialog |
| `ui/settings_dialog.py` | Tabbed settings — timer, email, auto-start |
| `utils/date_utils.py` | Expiry math, countdown formatting, row colours |
| `utils/csv_exporter.py` | CSV export via file dialog |
| `config/app_config.json` | Timer interval + bounds (template) |
| `config/email_config.json` | SMTP credentials + recipients (template) |
| `tests/conftest.py` | Shared pytest fixtures (tmp DB path) |
| `tests/test_date_utils.py` | Unit tests for date_utils |
| `tests/test_database_service.py` | Unit tests for DatabaseService |
| `tests/test_notification_service.py` | Unit tests for NotificationService |
| `tests/test_timer_service.py` | Unit tests for TimerService |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `config/app_config.json`
- Create: `config/email_config.json`
- Create: `models/__init__.py`
- Create: `services/__init__.py`
- Create: `ui/__init__.py`
- Create: `utils/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
cd "C:\Claude Projects\Product License Timer"
mkdir -p models services ui utils config data tests
```

- [ ] **Step 2: Create `requirements.txt`**

```
PyQt6>=6.6.0
```

- [ ] **Step 3: Create `requirements-dev.txt`**

```
PyQt6>=6.6.0
pytest>=8.0.0
pytest-qt>=4.4.0
```

- [ ] **Step 4: Create all `__init__.py` files**

Create empty `__init__.py` in: `models/`, `services/`, `ui/`, `utils/`, `tests/`

- [ ] **Step 5: Create `config/app_config.json`**

```json
{
  "timer_interval_seconds": 300,
  "timer_min_seconds": 300,
  "timer_max_seconds": 432000
}
```

- [ ] **Step 6: Create `config/email_config.json`**

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "",
  "smtp_password": "",
  "sender_name": "License Tracker",
  "recipients": []
}
```

- [ ] **Step 7: Install dependencies**

```bash
python -m pip install PyQt6 pytest pytest-qt
```

Expected: `Successfully installed PyQt6-...`

- [ ] **Step 8: Verify PyQt6 loads**

```bash
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
```

Expected: `PyQt6 OK`

- [ ] **Step 9: Commit**

```bash
git init
git add .
git commit -m "chore: project scaffold with dependencies and config templates"
```

---

## Task 2: Database Layer

**Files:**
- Create: `models/database.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
import pytest
from pathlib import Path
from models.database import initialize_db, get_connection


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite DB initialized with schema."""
    db_path = tmp_path / "test_licenses.db"
    initialize_db(db_path)
    return db_path
```

- [ ] **Step 2: Write failing test**

Create `tests/test_database.py`:

```python
from models.database import initialize_db, get_connection


def test_initialize_creates_products_table(tmp_path):
    db = tmp_path / "licenses.db"
    initialize_db(db)
    with get_connection(db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
    assert "products" in names
    assert "notifications_log" in names


def test_foreign_keys_enabled(tmp_path):
    db = tmp_path / "licenses.db"
    initialize_db(db)
    with get_connection(db) as conn:
        result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1


def test_initialize_is_idempotent(tmp_path):
    db = tmp_path / "licenses.db"
    initialize_db(db)
    initialize_db(db)  # second call must not raise
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd "C:\Claude Projects\Product License Timer"
python -m pytest tests/test_database.py -v
```

Expected: `FAILED` (ImportError — module not created yet)

- [ ] **Step 4: Create `models/database.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_database.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add models/database.py tests/test_database.py tests/conftest.py
git commit -m "feat: database schema and connection layer"
```

---

## Task 3: Date Utilities

**Files:**
- Create: `utils/date_utils.py`
- Create: `tests/test_date_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_date_utils.py
from datetime import date, timedelta
from utils.date_utils import (
    calculate_expiry_date,
    remaining_seconds,
    format_countdown,
    days_remaining,
    get_row_color,
)


def test_calculate_expiry_date():
    start = date(2026, 1, 1)
    assert calculate_expiry_date(start, 30) == date(2026, 1, 31)


def test_calculate_expiry_date_45_days():
    start = date(2026, 3, 1)
    assert calculate_expiry_date(start, 45) == date(2026, 4, 15)


def test_days_remaining_future():
    future = date.today() + timedelta(days=10)
    assert days_remaining(future) == 10


def test_days_remaining_past():
    past = date.today() - timedelta(days=5)
    assert days_remaining(past) == -5


def test_format_countdown_active():
    total = 1 * 86400 + 2 * 3600 + 3 * 60 + 4  # 1d 2h 3m 4s
    result, expired = format_countdown(total)
    assert result == "1d 2h 3m 4s"
    assert expired is False


def test_format_countdown_expired():
    total = -(1 * 86400 + 0 * 3600 + 0 * 60 + 0)
    result, expired = format_countdown(total)
    assert result == "Expired for: 1d 0h 0m 0s"
    assert expired is True


def test_format_countdown_zero():
    result, expired = format_countdown(0)
    assert result == "0d 0h 0m 0s"
    assert expired is False


def test_get_row_color_green():
    assert get_row_color(20) == "#d4edda"


def test_get_row_color_yellow():
    assert get_row_color(15) == "#fff3cd"


def test_get_row_color_orange():
    assert get_row_color(10) == "#ffe0b2"


def test_get_row_color_red():
    assert get_row_color(5) == "#f8d7da"


def test_get_row_color_expired():
    assert get_row_color(-1) == "#e0e0e0"


def test_remaining_seconds_future():
    # A date far in the future should give a large positive number
    future = date.today() + timedelta(days=100)
    secs = remaining_seconds(future)
    assert secs > 0


def test_remaining_seconds_past():
    past = date.today() - timedelta(days=1)
    secs = remaining_seconds(past)
    assert secs < 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_date_utils.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: Create `utils/date_utils.py`**

```python
"""
Date calculation and countdown formatting utilities.
Single responsibility: all datetime math for license countdowns.
"""
from datetime import date, datetime, timedelta
from typing import Tuple


def calculate_expiry_date(start_date: date, duration_days: int) -> date:
    """Return expiry_date = start_date + duration_days."""
    return start_date + timedelta(days=duration_days)


def remaining_seconds(expiry_date: date) -> int:
    """
    Return seconds until end of expiry_date.
    Negative if expiry_date is in the past.
    """
    deadline = datetime.combine(expiry_date, datetime.max.time()).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    delta = deadline - datetime.now()
    return int(delta.total_seconds())


def format_countdown(total_seconds: int) -> Tuple[str, bool]:
    """
    Format total_seconds as 'Xd Xh Xm Xs'.
    Returns (formatted_string, is_expired).
    Negative input → 'Expired for: Xd Xh Xm Xs', is_expired=True.
    """
    expired = total_seconds < 0
    abs_sec = abs(int(total_seconds))
    days = abs_sec // 86400
    hours = (abs_sec % 86400) // 3600
    minutes = (abs_sec % 3600) // 60
    seconds = abs_sec % 60
    time_str = f"{days}d {hours}h {minutes}m {seconds}s"
    if expired:
        return f"Expired for: {time_str}", True
    return time_str, False


def days_remaining(expiry_date: date) -> int:
    """Return whole days remaining. Negative if expired."""
    return (expiry_date - date.today()).days


def get_row_color(days_left: int) -> str:
    """Return background hex colour for a given days_remaining value."""
    if days_left > 15:
        return "#d4edda"   # green
    if days_left > 10:
        return "#fff3cd"   # yellow
    if days_left > 5:
        return "#ffe0b2"   # orange
    if days_left >= 0:
        return "#f8d7da"   # red
    return "#e0e0e0"       # grey — expired
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_date_utils.py -v
```

Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add utils/date_utils.py tests/test_date_utils.py
git commit -m "feat: date utilities for expiry calculation and countdown formatting"
```

---

## Task 4: Database Service

**Files:**
- Create: `services/database_service.py`
- Create: `tests/test_database_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_database_service.py
from datetime import date
import pytest
from services.database_service import DatabaseService


@pytest.fixture
def svc(tmp_db):
    return DatabaseService(db_path=tmp_db)


def test_add_and_get_product(svc):
    pid = svc.add_product(
        name="Equitrac 6",
        start_date=date(2026, 1, 1),
        duration_days=30,
        customer_name="ABC Corp",
        order_number="ORD-001",
    )
    assert pid is not None
    p = svc.get_product(pid)
    assert p["name"] == "Equitrac 6"
    assert p["customer_name"] == "ABC Corp"
    assert p["expiry_date"] == "2026-01-31"


def test_get_all_products_sorted_by_expiry(svc):
    svc.add_product("B Product", date(2026, 3, 1), 30)
    svc.add_product("A Product", date(2026, 1, 1), 30)
    products = svc.get_all_products()
    assert products[0]["name"] == "A Product"  # earlier expiry first
    assert products[1]["name"] == "B Product"


def test_update_product(svc):
    pid = svc.add_product("PaperCut MF", date(2026, 1, 1), 30)
    svc.update_product(pid, "PaperCut MF", date(2026, 2, 1), 45, customer_name="XYZ Ltd")
    p = svc.get_product(pid)
    assert p["duration_days"] == 45
    assert p["customer_name"] == "XYZ Ltd"
    assert p["expiry_date"] == "2026-03-18"


def test_delete_product(svc):
    pid = svc.add_product("YSoft SafeQ 6", date(2026, 1, 1), 30)
    svc.delete_product(pid)
    assert svc.get_product(pid) is None


def test_delete_expired_products(svc):
    svc.add_product("Expired A", date(2020, 1, 1), 30)
    svc.add_product("Expired B", date(2021, 1, 1), 30)
    svc.add_product("Active", date(2030, 1, 1), 30)
    count = svc.delete_expired_products()
    assert count == 2
    products = svc.get_all_products()
    assert len(products) == 1
    assert products[0]["name"] == "Active"


def test_duplicate_name_raises(svc):
    svc.add_product("Equitrac 6", date(2026, 1, 1), 30)
    with pytest.raises(Exception):
        svc.add_product("Equitrac 6", date(2026, 2, 1), 30)


def test_notification_sent_false_initially(svc):
    pid = svc.add_product("AWMS 2", date(2026, 1, 1), 30)
    assert svc.notification_sent(pid, "15_days") is False


def test_log_and_check_notification(svc):
    pid = svc.add_product("PaperCut Hive", date(2026, 1, 1), 30)
    svc.log_notification(pid, "5_days")
    assert svc.notification_sent(pid, "5_days") is True
    assert svc.notification_sent(pid, "10_days") is False


def test_log_notification_duplicate_is_safe(svc):
    pid = svc.add_product("SafeQ", date(2026, 1, 1), 30)
    svc.log_notification(pid, "15_days")
    svc.log_notification(pid, "15_days")  # must not raise


def test_delete_product_cascades_notifications(svc):
    pid = svc.add_product("ToDelete", date(2026, 1, 1), 30)
    svc.log_notification(pid, "5_days")
    svc.delete_product(pid)
    # No exception — cascade handled by DB
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_database_service.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: Create `services/database_service.py`**

```python
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
                pass  # UNIQUE constraint hit — already logged, safe to ignore
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_database_service.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add services/database_service.py tests/test_database_service.py
git commit -m "feat: database service with full product CRUD and notification log"
```

---

## Task 5: Notification Service

**Files:**
- Create: `services/notification_service.py`
- Create: `tests/test_notification_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_notification_service.py
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import pytest
from services.notification_service import NotificationService
from services.database_service import DatabaseService


@pytest.fixture
def svc(tmp_path):
    cfg_path = tmp_path / "email_config.json"
    return NotificationService(config_path=cfg_path)


@pytest.fixture
def db(tmp_db):
    return DatabaseService(db_path=tmp_db)


def test_check_and_send_skips_expired_products(svc, db):
    """Expired products should never trigger a notification."""
    pid = db.add_product("Old App", date(2020, 1, 1), 30)
    products = db.get_all_products()
    with patch.object(svc, 'send_email') as mock_send:
        svc.check_and_send(products, db)
        mock_send.assert_not_called()


def test_check_and_send_sends_at_threshold(svc, db):
    """A product at exactly 5 days should trigger the 5_days alert."""
    expiry = date.today() + timedelta(days=5)
    start = expiry - timedelta(days=30)
    pid = db.add_product("Threshold App", start, 30)
    products = db.get_all_products()
    with patch.object(svc, '_send_in_thread', return_value=True) as mock_send:
        svc.check_and_send(products, db)
        # Should have triggered at least the 5_days threshold
        calls = [c.args[1] for c in mock_send.call_args_list]
        assert 5 in calls


def test_check_and_send_no_duplicate(svc, db):
    """Already-logged notifications must not be re-sent."""
    expiry = date.today() + timedelta(days=5)
    start = expiry - timedelta(days=30)
    pid = db.add_product("No Dup App", start, 30)
    db.log_notification(pid, "5_days")
    products = db.get_all_products()
    with patch.object(svc, '_send_in_thread', return_value=True) as mock_send:
        svc.check_and_send(products, db)
        calls = [c.args[1] for c in mock_send.call_args_list]
        assert 5 not in calls


def test_send_email_returns_false_when_not_configured(svc):
    ok, msg = svc.send_email(
        {"name": "X", "customer_name": "", "order_number": "",
         "start_date": "2026-01-01", "expiry_date": "2026-01-31"},
        threshold=5,
    )
    assert ok is False
    assert msg  # error message present


def test_test_connection_returns_false_when_not_configured(svc):
    ok, msg = svc.test_connection()
    assert ok is False
    assert "not configured" in msg.lower() or msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_notification_service.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: Create `services/notification_service.py`**

```python
"""
Email alert logic with threshold checking and duplicate prevention.
Single responsibility: decide when to send alerts and dispatch emails.
"""
from __future__ import annotations
import json
import smtplib
import threading
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Tuple

from utils.date_utils import days_remaining

CONFIG_PATH = Path(__file__).parent.parent / "config" / "email_config.json"
THRESHOLDS = [15, 10, 5]  # days — checked in descending order


class NotificationService:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        with open(self.config_path) as f:
            return json.load(f)

    def check_and_send(self, products: List[dict], db_service) -> None:
        """
        For each product, check all thresholds.
        Sends an email and logs it if the threshold is met and not yet logged.
        Skips expired products entirely.
        """
        for product in products:
            expiry = date.fromisoformat(product["expiry_date"])
            days_left = days_remaining(expiry)
            if days_left < 0:
                continue  # expired — no more alerts
            for threshold in THRESHOLDS:
                ntype = f"{threshold}_days"
                if days_left <= threshold and not db_service.notification_sent(product["id"], ntype):
                    sent = self._send_in_thread(product, threshold)
                    if sent:
                        db_service.log_notification(product["id"], ntype)

    def _send_in_thread(self, product: dict, threshold: int) -> bool:
        """Send email in a background thread; block until done (max 15s)."""
        result = [False]

        def _send():
            result[0], _ = self.send_email(product, threshold)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        t.join(timeout=15)
        return result[0]

    def send_email(self, product: dict, threshold: int) -> Tuple[bool, str]:
        """
        Send a single threshold alert email.
        Returns (success: bool, error_message: str).
        """
        cfg = self._load_config()
        if not cfg.get("smtp_user"):
            return False, "SMTP username not configured"
        if not cfg.get("recipients"):
            return False, "No recipients configured"
        try:
            msg = MIMEMultipart()
            msg["Subject"] = (
                f"\u26a0 Trial Expiry Alert \u2014 {product['name']} ({threshold} days remaining)"
            )
            msg["From"] = (
                f"{cfg.get('sender_name', 'License Tracker')} <{cfg['smtp_user']}>"
            )
            msg["To"] = ", ".join(cfg["recipients"])
            body = (
                f"Product Name  : {product['name']}\n"
                f"Customer      : {product.get('customer_name', '')}\n"
                f"Order Number  : {product.get('order_number', '')}\n"
                f"Start Date    : {product['start_date']}\n"
                f"Expiry Date   : {product['expiry_date']}\n"
                f"Days Remaining: {threshold}\n"
                f"Threshold     : {threshold}-day warning\n\n"
                f"Please renew or arrange a replacement license before the expiry date."
            )
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as server:
                server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], cfg["recipients"], msg.as_string())
            return True, ""
        except Exception as e:
            print(f"[NotificationService] Email send failed: {e}")
            return False, str(e)

    def test_connection(self) -> Tuple[bool, str]:
        """Send a test email to the first recipient. Returns (success, message)."""
        cfg = self._load_config()
        if not cfg.get("smtp_user"):
            return False, "SMTP username not configured"
        if not cfg.get("recipients"):
            return False, "No recipients configured"
        try:
            msg = MIMEText("This is a test email from Product License Timer.", "plain")
            msg["Subject"] = "License Tracker \u2014 Test Connection"
            msg["From"] = cfg["smtp_user"]
            msg["To"] = cfg["recipients"][0]
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as server:
                server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], [cfg["recipients"][0]], msg.as_string())
            return True, "Test email sent successfully"
        except Exception as e:
            return False, str(e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_notification_service.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add services/notification_service.py tests/test_notification_service.py
git commit -m "feat: notification service with threshold checks and duplicate guard"
```

---

## Task 6: Timer Service

**Files:**
- Create: `services/timer_service.py`
- Create: `tests/test_timer_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_timer_service.py
import pytest
from PyQt6.QtWidgets import QApplication
import sys

# QApplication required for QTimer
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


from services.timer_service import TimerService


def test_default_interval(qapp):
    svc = TimerService()
    assert svc.interval_seconds == 300


def test_set_interval_valid(qapp):
    svc = TimerService()
    svc.set_interval(600)
    assert svc.interval_seconds == 600


def test_set_interval_clamps_to_min(qapp):
    svc = TimerService()
    svc.set_interval(10)  # below min of 300
    assert svc.interval_seconds == svc.min_seconds


def test_set_interval_clamps_to_max(qapp):
    svc = TimerService()
    svc.set_interval(999999)  # above max of 432000
    assert svc.interval_seconds == svc.max_seconds


def test_force_tick_emits_signal(qapp, qtbot):
    svc = TimerService()
    with qtbot.waitSignal(svc.tick, timeout=1000):
        svc.force_tick()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_timer_service.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: Create `services/timer_service.py`**

```python
"""
QTimer-based tick engine. Emits a tick signal on a configurable interval.
Single responsibility: schedule management only — no business logic.
"""
from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

CONFIG_PATH = Path(__file__).parent.parent / "config" / "app_config.json"
DEFAULT_INTERVAL = 300
DEFAULT_MIN = 300
DEFAULT_MAX = 432000


class TimerService(QObject):
    """Emits tick every N seconds. Interval is live-adjustable."""

    tick = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = self._load_config()
        self._min = cfg.get("timer_min_seconds", DEFAULT_MIN)
        self._max = cfg.get("timer_max_seconds", DEFAULT_MAX)
        self._interval = max(self._min, min(self._max, cfg.get("timer_interval_seconds", DEFAULT_INTERVAL)))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return {}

    def start(self) -> None:
        """Start the timer with the current interval."""
        self._timer.start(self._interval * 1000)

    def stop(self) -> None:
        """Stop the timer."""
        self._timer.stop()

    def set_interval(self, seconds: int) -> None:
        """
        Change the interval. Clamps to [min, max].
        If timer is running, the new interval takes effect immediately.
        """
        seconds = max(self._min, min(self._max, seconds))
        self._interval = seconds
        if self._timer.isActive():
            self._timer.setInterval(seconds * 1000)

    def force_tick(self) -> None:
        """Emit tick immediately without resetting the current schedule."""
        self.tick.emit()

    @property
    def interval_seconds(self) -> int:
        return self._interval

    @property
    def min_seconds(self) -> int:
        return self._min

    @property
    def max_seconds(self) -> int:
        return self._max
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_timer_service.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add services/timer_service.py tests/test_timer_service.py
git commit -m "feat: timer service with configurable interval and force-tick"
```

---

## Task 7: CSV Exporter

**Files:**
- Create: `utils/csv_exporter.py`

*(No isolated unit test — file dialog requires live Qt interaction. Covered by integration.)*

- [ ] **Step 1: Create `utils/csv_exporter.py`**

```python
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
```

- [ ] **Step 2: Verify import is clean**

```bash
python -c "from utils.csv_exporter import export_to_csv; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add utils/csv_exporter.py
git commit -m "feat: CSV export utility"
```

---

## Task 8: Product Table Widget

**Files:**
- Create: `ui/product_table.py`

- [ ] **Step 1: Create `ui/product_table.py`**

```python
"""
QTableWidget displaying all tracked products with live countdowns.
Single responsibility: render and filter the product list — no DB access.
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

from utils.date_utils import days_remaining, format_countdown, get_row_color, remaining_seconds

# Column index constants
COL_ID       = 0
COL_NAME     = 1
COL_CUSTOMER = 2
COL_ORDER    = 3
COL_START    = 4
COL_DURATION = 5
COL_EXPIRY   = 6
COL_DAYS     = 7
COL_REMAINING = 8
COL_STATUS   = 9

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
        self.setColumnHidden(COL_ID, True)   # ID hidden — used only for lookups
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
```

- [ ] **Step 2: Smoke-test the widget**

```bash
python -c "
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from ui.product_table import ProductTable
t = ProductTable()
t.refresh([{
    'id': 1, 'name': 'Equitrac 6', 'customer_name': 'ABC',
    'order_number': 'ORD-001', 'start_date': '2026-01-01',
    'duration_days': 30, 'expiry_date': '2026-01-31', 'notes': ''
}])
print(f'Rows: {t.rowCount()}')
assert t.rowCount() == 1
print('OK')
"
```

Expected: `Rows: 1` then `OK`

- [ ] **Step 3: Commit**

```bash
git add ui/product_table.py
git commit -m "feat: product table widget with colour coding and filter"
```

---

## Task 9: Product Form Dialog

**Files:**
- Create: `ui/product_form.py`

- [ ] **Step 1: Create `ui/product_form.py`**

```python
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
```

- [ ] **Step 2: Smoke-test the dialog**

```bash
python -c "
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from ui.product_form import ProductForm
dlg = ProductForm()
data = dlg.get_data()
assert 'name' in data
assert 'start_date' in data
assert 'duration_days' in data
print('ProductForm OK')
"
```

Expected: `ProductForm OK`

- [ ] **Step 3: Commit**

```bash
git add ui/product_form.py
git commit -m "feat: add/edit product dialog with live expiry preview"
```

---

## Task 10: Settings Dialog

**Files:**
- Create: `ui/settings_dialog.py`

- [ ] **Step 1: Create `ui/settings_dialog.py`**

```python
"""
Tabbed settings dialog. Saves to app_config.json and email_config.json.
Single responsibility: edit and persist all application configuration.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QWidget,
    QFormLayout, QSpinBox, QLineEdit, QCheckBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QLabel, QMessageBox,
)

APP_CONFIG_PATH = Path(__file__).parent.parent / "config" / "app_config.json"
EMAIL_CONFIG_PATH = Path(__file__).parent.parent / "config" / "email_config.json"

_APP_DEFAULTS = {
    "timer_interval_seconds": 300,
    "timer_min_seconds": 300,
    "timer_max_seconds": 432000,
}
_EMAIL_DEFAULTS = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "sender_name": "License Tracker",
    "recipients": [],
}


def _load(path: Path, defaults: dict) -> dict:
    if path.exists():
        with open(path) as f:
            return {**defaults, **json.load(f)}
    return dict(defaults)


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._app_cfg = _load(APP_CONFIG_PATH, _APP_DEFAULTS)
        self._email_cfg = _load(EMAIL_CONFIG_PATH, _EMAIL_DEFAULTS)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_timer_tab(), "Timer")
        self._tabs.addTab(self._build_email_tab(), "Email / SMTP")
        self._tabs.addTab(self._build_system_tab(), "System")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    # ----------------------------------------------------------------- Timer tab
    def _build_timer_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 2592000)
        self.interval_spin.setValue(self._app_cfg["timer_interval_seconds"])
        self.interval_spin.setSuffix(" seconds")

        self.min_spin = QSpinBox()
        self.min_spin.setRange(1, 2592000)
        self.min_spin.setValue(self._app_cfg["timer_min_seconds"])
        self.min_spin.setSuffix(" seconds")

        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 2592000)
        self.max_spin.setValue(self._app_cfg["timer_max_seconds"])
        self.max_spin.setSuffix(" seconds")

        form.addRow("Check Interval", self.interval_spin)
        form.addRow("Minimum Allowed", self.min_spin)
        form.addRow("Maximum Allowed", self.max_spin)
        form.addRow(QLabel("Changes take effect immediately without restart."))
        return w

    # ----------------------------------------------------------------- Email tab
    def _build_email_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.smtp_host = QLineEdit(self._email_cfg.get("smtp_host", ""))
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(int(self._email_cfg.get("smtp_port", 587)))
        self.smtp_user = QLineEdit(self._email_cfg.get("smtp_user", ""))
        self.smtp_pass = QLineEdit(self._email_cfg.get("smtp_password", ""))
        self.smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)

        show_btn = QPushButton("Show")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda on: self.smtp_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        pass_row = QHBoxLayout()
        pass_row.addWidget(self.smtp_pass)
        pass_row.addWidget(show_btn)

        self.sender_name = QLineEdit(self._email_cfg.get("sender_name", "License Tracker"))

        self.recipient_list = QListWidget()
        self.recipient_list.setMaximumHeight(100)
        for r in self._email_cfg.get("recipients", []):
            self.recipient_list.addItem(r)

        self.new_recipient = QLineEdit()
        self.new_recipient.setPlaceholderText("admin@company.com")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_recipient)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_recipient)
        add_row = QHBoxLayout()
        add_row.addWidget(self.new_recipient)
        add_row.addWidget(add_btn)
        add_row.addWidget(remove_btn)

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)

        form.addRow("SMTP Host", self.smtp_host)
        form.addRow("SMTP Port", self.smtp_port)
        form.addRow("Username", self.smtp_user)
        form.addRow("Password", pass_row)
        form.addRow("Sender Name", self.sender_name)
        form.addRow("Recipients", self.recipient_list)
        form.addRow("Add Recipient", add_row)
        form.addRow("", test_btn)
        return w

    def _add_recipient(self) -> None:
        email = self.new_recipient.text().strip()
        if email and "@" in email:
            self.recipient_list.addItem(email)
            self.new_recipient.clear()

    def _remove_recipient(self) -> None:
        for item in self.recipient_list.selectedItems():
            self.recipient_list.takeItem(self.recipient_list.row(item))

    def _test_connection(self) -> None:
        self._persist()  # save current values before testing
        from services.notification_service import NotificationService
        ok, msg = NotificationService().test_connection()
        if ok:
            QMessageBox.information(self, "Test Connection", msg)
        else:
            QMessageBox.warning(self, "Test Connection Failed", msg)

    # ----------------------------------------------------------------- System tab
    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.autostart_check = QCheckBox("Start with Windows (minimized to tray)")
        self.autostart_check.setChecked(self._autostart_enabled())
        layout.addWidget(self.autostart_check)
        layout.addStretch()
        return w

    def _autostart_enabled(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, "ProductLicenseTimer")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _set_autostart(self, enable: bool) -> None:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            pythonw = Path(sys.executable).parent / "pythonw.exe"
            main_py = Path(__file__).parent.parent / "main.py"
            cmd = f'"{pythonw}" "{main_py}" --minimized'
            winreg.SetValueEx(key, "ProductLicenseTimer", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "ProductLicenseTimer")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)

    # ----------------------------------------------------------------- Save
    def _persist(self) -> None:
        """Write current field values to config files."""
        min_v = self.min_spin.value()
        max_v = self.max_spin.value()
        interval = max(min_v, min(max_v, self.interval_spin.value()))

        _save(APP_CONFIG_PATH, {
            "timer_interval_seconds": interval,
            "timer_min_seconds": min_v,
            "timer_max_seconds": max_v,
        })
        _save(EMAIL_CONFIG_PATH, {
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": self.smtp_port.value(),
            "smtp_user": self.smtp_user.text().strip(),
            "smtp_password": self.smtp_pass.text(),
            "sender_name": self.sender_name.text().strip(),
            "recipients": [
                self.recipient_list.item(i).text()
                for i in range(self.recipient_list.count())
            ],
        })

    def _on_save(self) -> None:
        min_v = self.min_spin.value()
        max_v = self.max_spin.value()
        interval = self.interval_spin.value()
        if min_v > max_v:
            QMessageBox.warning(self, "Invalid", "Minimum interval cannot exceed maximum.")
            return
        if not (min_v <= interval <= max_v):
            QMessageBox.warning(
                self, "Invalid",
                f"Interval must be between {min_v} and {max_v} seconds."
            )
            return
        self._persist()
        self._set_autostart(self.autostart_check.isChecked())
        self.accept()

    def get_app_config(self) -> dict:
        """Return the saved app config (reads from file)."""
        return _load(APP_CONFIG_PATH, _APP_DEFAULTS)

    def get_email_config(self) -> dict:
        """Return the saved email config (reads from file)."""
        return _load(EMAIL_CONFIG_PATH, _EMAIL_DEFAULTS)
```

- [ ] **Step 2: Smoke-test the import**

```bash
python -c "from ui.settings_dialog import SettingsDialog; print('SettingsDialog OK')"
```

Expected: `SettingsDialog OK`

- [ ] **Step 3: Commit**

```bash
git add ui/settings_dialog.py
git commit -m "feat: settings dialog with timer, SMTP, and auto-start tabs"
```

---

## Task 11: Main Window

**Files:**
- Create: `ui/main_window.py`

- [ ] **Step 1: Create `ui/main_window.py`**

```python
"""
Main application window. Wires all components together.
Single responsibility: application shell — layout, menus, toolbar, tray, event routing.
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QMessageBox, QToolBar,
    QSystemTrayIcon, QMenu, QFileDialog,
    QLabel, QStatusBar,
)

from models.database import DB_PATH
from services.database_service import DatabaseService
from services.notification_service import NotificationService
from services.timer_service import TimerService
from ui.product_form import ProductForm
from ui.product_table import ProductTable
from ui.settings_dialog import SettingsDialog
from utils.csv_exporter import export_to_csv


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Product License Timer")
        self.setMinimumSize(1100, 620)

        self._db = DatabaseService()
        self._notifier = NotificationService()
        self._timer = TimerService(self)
        self._timer.tick.connect(self._on_tick)

        self._build_ui()
        self._build_tray()
        self._on_tick()       # populate immediately on launch
        self._timer.start()

    # ---------------------------------------------------------------- Build UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        self.addToolBar(self._build_toolbar())

        self._table = ProductTable()
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

        self._status_label = QLabel()
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        self.setStatusBar(status_bar)

        self._build_menu()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar("Main")
        tb.setMovable(False)

        def act(label, slot):
            a = QAction(label, self)
            a.triggered.connect(slot)
            return a

        tb.addAction(act("+ Add", self._add_product))
        tb.addAction(act("✏ Edit", self._edit_product))
        tb.addAction(act("🗑 Delete", self._delete_product))
        tb.addSeparator()
        tb.addAction(act("Clear Expired", self._clear_expired))
        tb.addAction(act("⟳ Check Now", self._timer.force_tick))
        tb.addSeparator()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name / customer / order...")
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._table.apply_filter)
        tb.addWidget(self._search)
        return tb

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_m = mb.addMenu("File")
        file_m.addAction("Export CSV", self._export_csv)
        file_m.addAction("Backup Database", self._backup_db)
        file_m.addSeparator()
        file_m.addAction("Exit", self._quit_app)

        edit_m = mb.addMenu("Edit")
        edit_m.addAction("Add Product", self._add_product)
        edit_m.addAction("Edit Product", self._edit_product)
        edit_m.addAction("Delete Product", self._delete_product)
        edit_m.addSeparator()
        edit_m.addAction("Clear Expired", self._clear_expired)

        settings_m = mb.addMenu("Settings")
        settings_m.addAction("Timer / Email / System", self._open_settings)

        help_m = mb.addMenu("Help")
        help_m.addAction("About", self._about)

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        )
        self._tray.setToolTip("Product License Timer")

        menu = QMenu()
        menu.addAction("Open", self._show_window)
        menu.addAction("⟳ Check Now", self._timer.force_tick)
        menu.addSeparator()
        menu.addAction("Exit", self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # --------------------------------------------------------------- Events

    def closeEvent(self, event) -> None:
        """X button → quit the application."""
        self._quit_app()
        event.ignore()

    def changeEvent(self, event) -> None:
        """Minimize button → hide to tray."""
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self._tray.showMessage(
                "Product License Timer",
                "Running in the background. Right-click the tray icon to open.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        super().changeEvent(event)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self._edit_product)
        menu.addAction("Delete", self._delete_product)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self) -> None:
        self._timer.stop()
        self._tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # ------------------------------------------------------------------ Tick

    def _on_tick(self) -> None:
        products = self._db.get_all_products()
        self._table.refresh(products)
        self._notifier.check_and_send(products, self._db)
        self._status_label.setText(
            f"Last checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
            f"{len(products)} product(s) tracked"
        )

    # ------------------------------------------------------------- Product CRUD

    def _add_product(self) -> None:
        dlg = ProductForm(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                self._db.add_product(**data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add product:\n{e}")

    def _edit_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to edit.")
            return
        product = self._db.get_product(pid)
        dlg = ProductForm(self, product=product)
        if dlg.exec():
            data = dlg.get_data()
            try:
                self._db.update_product(pid, **data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update product:\n{e}")

    def _delete_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to delete.")
            return
        product = self._db.get_product(pid)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{product['name']}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_product(pid)
            self._on_tick()

    def _clear_expired(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Expired",
            "Remove all expired products from the database?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self._db.delete_expired_products()
            self._on_tick()
            QMessageBox.information(self, "Done", f"Removed {count} expired product(s).")

    # --------------------------------------------------------------- Extras

    def _export_csv(self) -> None:
        products = self._db.get_all_products()
        export_to_csv(products, self)

    def _backup_db(self) -> None:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default = str(Path.home() / f"licenses_backup_{ts}.db")
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", default, "SQLite DB (*.db)"
        )
        if path:
            shutil.copy2(str(DB_PATH), path)
            QMessageBox.information(self, "Backup Complete", f"Saved to:\n{path}")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            cfg = dlg.get_app_config()
            self._timer.set_interval(cfg["timer_interval_seconds"])

    def _about(self) -> None:
        QMessageBox.about(
            self, "About Product License Timer",
            "Product License Timer\n\n"
            "Tracks trial software license expiry dates.\n"
            "Sends email alerts at 15, 10, and 5 day thresholds.\n\n"
            "Built with Python 3.13 + PyQt6",
        )
```

- [ ] **Step 2: Smoke-test the import**

```bash
python -c "from ui.main_window import MainWindow; print('MainWindow OK')"
```

Expected: `MainWindow OK`

- [ ] **Step 3: Commit**

```bash
git add ui/main_window.py
git commit -m "feat: main window with toolbar, menus, tray, and full product management"
```

---

## Task 12: Entry Point + Full Integration Test

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
"""
Entry point. Handles --minimized flag for Windows auto-start via registry.
"""
import sys
from pathlib import Path

# Ensure project root is importable when launched via pythonw.exe
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Product License Timer")
    app.setQuitOnLastWindowClosed(False)  # Allow tray-only mode

    window = MainWindow()

    if "--minimized" not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all unit tests**

```bash
cd "C:\Claude Projects\Product License Timer"
python -m pytest tests/ -v --ignore=tests/test_timer_service.py
```

Expected: All tests pass (test_timer_service requires a live QApplication — run separately if needed)

- [ ] **Step 3: Launch the app**

```bash
python main.py
```

Expected: Window opens showing the product table. Toolbar and menus are visible. Status bar shows "Last checked: ..."

- [ ] **Step 4: Manual smoke test checklist**
  - [ ] Click `+ Add` — form opens, fill in a product, click Save — row appears in table
  - [ ] Select row, click `✏ Edit` — form opens pre-filled, edit duration, Save — expiry date updated
  - [ ] Select row, click `🗑 Delete` — confirmation dialog, Yes — row removed
  - [ ] Click `⟳ Check Now` — status bar timestamp updates
  - [ ] Click minimize — window hides, tray icon remains
  - [ ] Double-click tray icon — window reappears
  - [ ] Right-click tray icon — menu shows Open / Check Now / Exit
  - [ ] `Settings → Timer / Email / System` — dialog opens, change interval, Save — no crash
  - [ ] `File → Export CSV` — file dialog opens
  - [ ] `File → Backup DB` — file dialog opens
  - [ ] Search box — typing filters table rows in real-time
  - [ ] `Edit → Clear Expired` — confirmation shown

- [ ] **Step 5: Final commit**

```bash
git add main.py
git commit -m "feat: entry point and --minimized auto-start flag"
git tag v1.0.0
```

---

## Post-Implementation Notes

**Running the app:**
```bash
cd "C:\Claude Projects\Product License Timer"
python main.py
```

**Running tests:**
```bash
python -m pytest tests/ -v
```

**To configure email:** Open the app → Settings → Email / SMTP tab. Fill in SMTP host, port, credentials, recipients. Click "Test Connection" to verify before relying on alerts.

**Auto-start:** Settings → System tab → check "Start with Windows". The app will launch minimized to the system tray on next boot.

**Timer interval:** Settings → Timer tab. Default 300 seconds (5 minutes). Min 300s, Max 432000s (5 days). Both bounds are editable.
