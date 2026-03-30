# Trial License Tracker — Design Spec
**Date:** 2026-03-30
**Status:** Approved
**Location:** `C:\Claude Projects\Product License Timer\`

---

## 1. Overview

A desktop GUI application for tracking trial software license expiry dates. Displays real-time countdowns per product, sends email alerts at configurable thresholds, and runs in the Windows system tray. Built with Python 3.13 + PyQt6.

Target products (pre-loaded as examples): Equitrac 6, PaperCut MF, PaperCut Hive, YSoft SafeQ 6, AWMS 2.

---

## 2. Folder Structure

```
C:\Claude Projects\Product License Timer\
├── main.py
├── requirements.txt
├── config/
│   ├── app_config.json          # Timer interval + bounds
│   └── email_config.json        # SMTP credentials + recipients
├── data/
│   └── licenses.db              # SQLite database (auto-created on first run)
├── models/
│   └── database.py              # Schema + raw SQLite connection
├── services/
│   ├── database_service.py      # CRUD for products + notification log
│   ├── notification_service.py  # Email alert logic + duplicate guard
│   └── timer_service.py         # QTimer driver — countdown + notification checks
├── ui/
│   ├── main_window.py           # QMainWindow, menu bar, system tray
│   ├── product_table.py         # QTableWidget with live countdown rows
│   ├── product_form.py          # Add/Edit QDialog
│   └── settings_dialog.py       # Timer config, SMTP, auto-start
└── utils/
    ├── date_utils.py            # Expiry calculation, time formatting
    └── csv_exporter.py          # CSV export via file dialog
```

---

## 3. Database Schema

```sql
CREATE TABLE products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    customer_name   TEXT DEFAULT '',
    order_number    TEXT DEFAULT '',
    start_date      DATE NOT NULL,
    duration_days   INTEGER NOT NULL CHECK(duration_days > 0),
    expiry_date     DATE NOT NULL,
    notes           TEXT DEFAULT ''
);

CREATE TABLE notifications_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    notification_type   TEXT NOT NULL CHECK(notification_type IN ('15_days','10_days','5_days')),
    sent_at             DATETIME NOT NULL,
    UNIQUE(product_id, notification_type)
);
```

**Key decisions:**
- `expiry_date` stored (not always computed) — faster queries, survives duration edits
- `UNIQUE(product_id, notification_type)` is a DB-level constraint — hard guarantee against duplicate emails
- `ON DELETE CASCADE` — deleting a product removes its notification history

---

## 4. UI Layout

### Main Window
- **Menu bar:**
  - `File` → Export CSV, Backup DB, Exit
  - `Edit` → Add Product, Edit Product, Delete Product, Clear Expired
  - `Settings` → Timer & Notifications, Email / SMTP, Auto-start
  - `Help` → About
- **Toolbar:** `+ Add`, `✏ Edit`, `🗑 Delete`, `Clear Expired`, `Check Now`, search bar
- **Product table** — sortable columns, default sort by expiry date ascending:

| # | Product Name | Customer | Order # | Start Date | Duration | Expiry Date | Days Left | Remaining Time | Status |
|---|---|---|---|---|---|---|---|---|---|

### Row Colour Coding
| Condition | Colour |
|---|---|
| > 15 days remaining | Green |
| ≤ 15 days remaining | Yellow |
| ≤ 10 days remaining | Orange |
| ≤ 5 days remaining | Red |
| Expired | Grey (italic) |

### Remaining Time Column Behaviour
- **Active:** `Xd Xh Xm Xs` counting down
- **Expired:** `Expired for: Xd Xh Xm Xs` counting up from expiry moment, grey italic

### Days Left Column Behaviour
- **Active:** positive integer (e.g. `14`)
- **Expired:** negative integer (e.g. `-58`) — indicates days since expiry

### Add/Edit Dialog (QDialog, modal)
Fields:
- Product Name (required)
- Customer Name (optional)
- Order Number (optional)
- Start Date (`QDateEdit` with calendar popup, defaults to today)
- Duration in days (spinbox, 1–3650)
- Notes (optional multiline)
- Expiry Date (read-only, auto-calculated preview)

Buttons: `Save` | `Cancel`

### Settings Dialog (tabbed)
- **Timer tab:** Interval seconds (validated min/max), min limit, max limit
- **Email tab:** SMTP host, port, username, password (masked + show/hide), sender name, recipients list (add/remove), Test Connection button
- **System tab:** Auto-start on Windows boot (checkbox)

### System Tray
- Right-click menu: `Open`, `Check Now`, `Exit`
- Minimize button → hides window to tray
- X button → exits application fully

---

## 5. Timer Service

- Powered by `QTimer` (built-in PyQt6, no extra dependency)
- Interval configured in `app_config.json`:

```json
{
  "timer_interval_seconds": 300,
  "timer_min_seconds": 300,
  "timer_max_seconds": 432000
}
```

- Changing interval in Settings calls `timer.setInterval(new_ms)` immediately — no restart required
- Each tick:
  1. Fetch all products from DB
  2. Recalculate remaining/elapsed time
  3. Emit signal → `product_table` refreshes rows + colours
  4. Pass products to `notification_service` for threshold checks
- `Check Now` button (toolbar + tray menu) forces immediate tick

---

## 6. Notification & Email System

**Thresholds:** 15 days, 10 days, 5 days remaining

**Duplicate guard:** Before sending, query `notifications_log` for existing `(product_id, threshold)` row. If found, skip. DB `UNIQUE` constraint is a second-layer hard guard.

**Email format:**
```
Subject: ⚠ Trial Expiry Alert — [Product Name] ([N] days remaining)

Product Name  : [name]
Customer      : [customer_name]
Order Number  : [order_number]
Start Date    : [start_date]
Expiry Date   : [expiry_date]
Days Remaining: [N]
Threshold     : [N]-day warning

Please renew or arrange a replacement license before the expiry date.
```

**SMTP:** `smtplib` with TLS (port 587 default). Runs in a background thread — UI never blocks. Failed sends are logged to console; no automatic retry (next timer tick will retry naturally for in-threshold products since no log row was written on failure).

**Config file** (`config/email_config.json`) — user fills in:
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

SMTP settings are fully editable via the Settings dialog (Email tab). Supports Gmail, Office 365, or any SMTP provider.

---

## 7. Expired Entry Management

- `Edit → Clear Expired` removes all expired products (confirmation dialog required)
- Individual rows: delete via toolbar button or right-click context menu
- Expired rows display grey italic with `Expired for: Xd Xh Xm Xs` counter (counting up)
- No notifications sent for expired products

---

## 8. Extra Features

| Feature | Implementation |
|---|---|
| Search/filter | Real-time filter on Name, Customer, Order# via toolbar search bar |
| Sort | Click any column header; default: expiry date ascending |
| Export CSV | `File → Export CSV` → save file dialog, all columns + computed days remaining |
| Backup DB | `File → Backup DB` → save file dialog, copies `licenses.db` with timestamp |

---

## 9. Auto-start on Windows Boot

- Settings → System tab: "Start with Windows" checkbox
- Enabled: writes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `pythonw.exe "C:\Claude Projects\Product License Timer\main.py" --minimized`
- Disabled: removes registry key
- Uses `winreg` (Python stdlib) — no admin privileges required
- `--minimized` flag in `sys.argv` → app starts hidden in system tray

---

## 10. Dependencies (requirements.txt)

```
PyQt6>=6.6.0
pystray>=0.19.5
Pillow>=10.0.0
```

All other functionality uses Python stdlib (`sqlite3`, `smtplib`, `winreg`, `csv`, `json`, `threading`, `datetime`).

---

## 11. Edge Cases

| Case | Handling |
|---|---|
| Duration = 0 | Blocked by spinbox minimum (1 day) |
| Start date in future | Allowed; days remaining counts from start date |
| Duplicate product name | DB `UNIQUE` constraint raises error → user-friendly dialog |
| SMTP failure | Logged to console, no log row written, retried next tick |
| DB missing on launch | `database.py` auto-creates schema on first connection |
| Timer interval out of bounds | Settings dialog clamps + shows validation message |
| App launched with `--minimized` | Window never shown; starts directly in tray |
