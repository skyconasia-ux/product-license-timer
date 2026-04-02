# Product License Timer — CLAUDE.md

Project instructions for Claude Code. These override default assistant behaviour.

---

## Project Overview

Desktop app (PyQt6) that tracks software trial license expiry dates and sends email alerts at 15, 10, and 5-day thresholds.

- **Phase 1** — Single-user SQLite app with a product table, timer, system tray, and SMTP notifications.
- **Phase 2** — Multi-user upgrade: SQL Server / SQLAlchemy ORM, user authentication (login / roles / email verification), contacts address book, system recipients, product ownership (Consultant / Account Manager / Project Manager), left sidebar navigation.

**Location:** `C:\Claude Projects\Product License Timer\`
**GitHub:** `skyconasia-ux/product-license-timer`
**Python:** 3.13  |  **UI:** PyQt6  |  **ORM:** SQLAlchemy 2.0

---

## Branch and Worktree Conventions

- `main` — stable, released code (Phase 1 baseline)
- `feature/phase2-multi-user` — Phase 2 work, lives in `.worktrees/phase2`
- Active Phase 2 worktree: `C:\Claude Projects\Product License Timer\.worktrees\phase2`
- Always work in the worktree for Phase 2, not in the root directory.

---

## Architecture

```
main.py                       Entry point — light theme, login loop, launches MainWindow
models/
  orm.py                      SQLAlchemy ORM (Phase 2 canonical models)
  database.py                 Legacy SQLite schema (Phase 1, kept as migration source)
services/
  auth_service.py             Login, bcrypt, UserSession dataclass, email verification
  user_service.py             User CRUD — role-gated (admin / superadmin)
  contact_service.py          Contacts + SystemRecipients CRUD
  product_service.py          Product CRUD with ownership FK support
  notification_service.py     resolve_recipients, format_email_body, check_and_send_v2
  db_session.py               SQLAlchemy engine + session factory singleton
  timer_service.py            QTimer wrapper (unchanged from Phase 1)
  database_service.py         Legacy SQLite service (Phase 1 only, not used in Phase 2)
ui/
  login_dialog.py             Login card + forced password-change dialog
  main_window.py              Shell: sidebar nav, product page, tray, timer wiring
  product_table.py            ProductTable widget — ORM + legacy dict compatible
  product_form.py             Add/Edit dialog — ownership dropdowns, DD-MM-YYYY
  contacts_page.py            Address book management (admin+)
  recipients_page.py          System recipients management (admin+)
  settings_dialog.py          Timer + SMTP (writes to .env) + autostart
migrations/
  init_schema.py              Fresh DB setup — creates tables, seeds superadmin
  migrate_sqlite.py           Copies Phase 1 SQLite data into Phase 2 DB
service/
  notification_daemon.py      Headless notification checker (no GUI)
  windows_service.py          Windows Service wrapper using pywin32
  product-license-timer.service  Linux systemd unit file
utils/
  date_utils.py               DD-MM-YYYY helpers, days_remaining, get_row_color
  csv_exporter.py             CSV export
```

---

## Key Conventions

### Dates
- **All dates displayed as DD-MM-YYYY** (Singapore format) — use `strftime("%d-%m-%Y")`
- Internal storage: Python `date` objects or ISO strings `YYYY-MM-DD`
- QDateEdit display format: `"dd-MM-yyyy"`

### Database
- Phase 2 uses SQLAlchemy 2.0 ORM — **no raw SQL anywhere**
- Tests always use SQLite in-memory (`sqlite:///:memory:`) — no SQL Server needed
- `sessionmaker(engine)` — NOT `sessionmaker(bind=engine)` (deprecated in SA 2.0)
- All sessions are caller-managed (passed in, closed by the caller)

### Authentication
- Passwords hashed with bcrypt, cost factor 12
- `UserSession` dataclass is in-memory only — never persisted to disk
- Three roles: `user` | `admin` | `superadmin`
- Default password: `FujiFilm_11111` — forced change on first login
- Only one superadmin (seeded by `init_schema.py`)

### Service layer rules
- **No PyQt imports in any service file** — services must be framework-agnostic
- Services accept `session: Session` and `caller: UserSession` as parameters
- Permission checks via `_require_admin(caller)` or `_require_role(caller, *roles)`

### UI layer rules
- All mutating operations wrapped in `try/except` with `QMessageBox.critical`
- `QAction` imports always at module level (never inside loops)
- `ROLES.index(...)` always wrapped in `try/except ValueError` with fallback to 0

---

## Configuration

### `.env` (gitignored)
```env
DATABASE_URL=mssql+pyodbc://user:pass@server/dbname?driver=ODBC+Driver+17+for+SQL+Server
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_TLS=true
SENDER_NAME=License Tracker
DAEMON_INTERVAL=300
```

For local/test use: `DATABASE_URL=sqlite:///data/licenses_test.db`

### First-time setup (Phase 2)
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL and SMTP settings
python -m migrations.init_schema
python main.py
```

---

## Running Tests
```bash
pytest tests/ -k "not test_force_tick_emits_signal"
```
The excluded test (`test_force_tick_emits_signal`) requires `pytest-qt` which is not installed — this is a pre-existing Phase 1 test that is harmless to skip.

Expected: **76 passed** (as of Phase 2 completion).

---

## Notification Daemon (Service)

The daemon runs independently of the GUI, checking for expiring licenses and sending emails.

### Windows Service
```bat
pip install pywin32
python service\windows_service.py install
python service\windows_service.py start
```
Or run headless in a terminal: `python -m service.notification_daemon`

### Linux (systemd)
```bash
sudo cp service/product-license-timer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable product-license-timer
sudo systemctl start product-license-timer
sudo journalctl -u product-license-timer -f
```

---

## Phase 1 → Phase 2 Migration
```bash
python -m migrations.migrate_sqlite --sqlite path/to/licenses.db
```
Maps `name` → `product_name`, sets `created_by` = superadmin id, migrates notification logs.

---

## Known Deferred Items (Phase 3)
- Colour-coded pills in Assigned To column (blue/green/purple) — needs custom delegate — TODO comment in `product_table.py`
- 2FA / TOTP — columns `totp_secret`, `totp_enabled` already in ORM, unused
- FastAPI web migration — services are framework-agnostic and ready
- `test_force_tick_emits_signal` — needs `pytest-qt` installed
