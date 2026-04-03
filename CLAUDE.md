# Product License Timer — CLAUDE.md

Project instructions for Claude Code. These override default assistant behaviour.

---

## Project Overview

Desktop app (PyQt6) that tracks software trial license expiry dates and sends email alerts at 15, 10, and 5-day thresholds.

- **Phase 1** — Single-user SQLite app with a product table, timer, system tray, and SMTP notifications.
- **Phase 2** — Multi-user upgrade: SQLAlchemy ORM, user authentication (login / roles / email verification), contacts address book, system recipients, product ownership (Consultant / Account Manager / Project Manager), left sidebar navigation, user management UI.

**GitHub:** `skyconasia-ux/product-license-timer`
**Python:** 3.12 — DO NOT use 3.13 or 3.14 (PyQt6 DLL load failure on Windows)
**UI:** PyQt6  |  **ORM:** SQLAlchemy 2.0

---

## Branch and Worktree Conventions

- `main` — stable, released code (Phase 1 baseline)
- `feature/phase2-multi-user` — Phase 2 active work branch
- Always work on `feature/phase2-multi-user`

---

## Architecture

```
main.py                       Entry point — Fusion light theme, login loop, launches MainWindow
models/
  orm.py                      SQLAlchemy ORM (Phase 2 canonical models)
  database.py                 Legacy SQLite schema (Phase 1, kept as migration source)
services/
  auth_service.py             Login, bcrypt, UserSession dataclass, email verification tokens
  user_service.py             User CRUD — role-gated (admin / superadmin)
                              Functions: create_user, promote_to_admin, demote_admin,
                              delete_user, list_users, reset_password, set_active, change_email
  contact_service.py          Contacts + SystemRecipients CRUD
  product_service.py          Product CRUD with ownership FK support
  notification_service.py     resolve_recipients, format_email_body, check_and_send_v2,
                              _send_smtp, get_smtp_config (reloads .env on every call)
  db_session.py               SQLAlchemy engine + session factory singleton
  timer_service.py            QTimer wrapper (unchanged from Phase 1)
  database_service.py         Legacy SQLite service (Phase 1 only, not used in Phase 2)
ui/
  login_dialog.py             Login card + ChangePasswordDialog + _VerifyAccountDialog
  main_window.py              Shell: sidebar nav, product page, tray, timer wiring
  product_table.py            ProductTable widget — ORM + legacy dict compatible
  product_form.py             Add/Edit dialog — ownership dropdowns, DD-MM-YYYY
  contacts_page.py            Address book management (admin+)
  recipients_page.py          System recipients management (admin+)
  users_page.py               User management (admin+): add/edit/verify/promote/delete
                              Right-click context menu + double-click to edit
                              _EditUserDialog: email, role, active, verified, password reset
  settings_dialog.py          Timer + SMTP (writes to .env) + autostart
                              SMTP tab hidden for role=user (admin/superadmin only)
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
- Email verification required before login — token created via `create_verification_token()`
- `verify_email_token()` marks user verified and deletes the token (24hr TTL)

### Service layer rules
- **No PyQt imports in any service file** — services must be framework-agnostic
- Services accept `session: Session` and `caller: UserSession` as parameters
- Permission checks via `_require_role(caller, *roles)`

### UI layer rules
- All mutating operations wrapped in `try/except` with `QMessageBox.critical`
- `QAction` imports always at module level (never inside loops)
- `ROLES.index(...)` always wrapped in `try/except ValueError` with fallback to 0

### SMTP
- Settings saved to `.env` via `python-dotenv` `set_key()`
- `get_smtp_config()` calls `load_dotenv(override=True)` on every call — no restart needed after saving
- Gmail requires an App Password (not the account password) — account → Security → App Passwords
- SMTP tab in Settings is hidden for `role=user`; only admin/superadmin can configure

### User Management
- Admin can: create users, edit users (not superadmin), verify, promote to admin, reset passwords
- Superadmin can: all of the above + demote admins, delete users, change emails, edit any user
- When creating a user: verification token is generated and emailed if SMTP is configured
  - If email send fails or SMTP not configured: token is shown in the dialog for manual sharing
  - Admin can also use the toolbar "Verify" button to manually verify without a token

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

---

## First-Time Setup (Windows Server)

```powershell
# Requires Python 3.12 — NOT 3.13 or 3.14 (PyQt6 DLL fails)
# Install Python 3.12 from python.org, then:

git clone https://github.com/skyconasia-ux/product-license-timer.git
cd product-license-timer
git checkout feature/phase2-multi-user

py -3.12 -m pip install -r requirements.txt

# Create .env (PowerShell):
Copy-Item .env.example .env
# Edit .env — set DATABASE_URL and SMTP settings

py -3.12 -m migrations.init_schema
py -3.12 main.py
```

### Updating from GitHub (after new commits)
```powershell
git pull origin feature/phase2-multi-user
py -3.12 main.py
```

---

## Running Tests
```bash
pytest tests/ -k "not test_force_tick_emits_signal"
```
The excluded test (`test_force_tick_emits_signal`) requires `pytest-qt` — harmless to skip.

Expected: **76 passed** (as of latest Phase 2 build).

---

## Notification Daemon (Service)

### Windows Service
```bat
py -3.12 -m pip install pywin32
py -3.12 service\windows_service.py install
py -3.12 service\windows_service.py start
```
Or run headless: `py -3.12 -m service.notification_daemon`

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
py -3.12 -m migrations.migrate_sqlite --sqlite path/to/licenses.db
```
Maps `name` → `product_name`, sets `created_by` = superadmin id, migrates notification logs.

---

## Email Verification Flow (Desktop App)

Since this is a desktop app with no web server, verification works via token entry:

1. Admin creates a user → token generated + emailed (or shown in dialog if SMTP fails)
2. User launches app → clicks **"Verify Account"** on the login screen
3. User pastes their token → account is verified → they can now log in

Admin can also bypass this by clicking **"Verify"** on the Users page toolbar (manual verification).

---

## Pending: Login Behaviour Investigation

**Next session:** Claude Code will be opened directly on the Windows Server test environment.

The user will provide specific instructions on how login should behave — including changes to
the login flow, session handling, or user experience on the login screen.

When investigating, start by reading:
- `ui/login_dialog.py` — LoginDialog, ChangePasswordDialog, _VerifyAccountDialog
- `main.py` — login loop (`while True`), `logout_requested` flag, `_apply_light_theme()`
- `services/auth_service.py` — `login()`, `is_default_password()`, `verify_email_token()`

Current login flow:
1. `LoginDialog` shown — email + password fields + "Verify Account" link
2. On Sign In: checks `is_active=True, is_verified=True` in DB
3. If default password → `ChangePasswordDialog` (forced change)
4. On success → `MainWindow` launched with `UserSession` + `db_session`
5. On logout → `logout_requested = True` → app quits → `main.py` while loop re-shows login
6. On window close/Exit → `logout_requested = False` → app fully exits

---

## Known Deferred Items (Phase 3)
- **Login behaviour** — user will specify changes when testing on server (see above)
- Colour-coded pills in Assigned To column (blue/green/purple) — needs custom delegate — TODO comment in `product_table.py`
- 2FA / TOTP — columns `totp_secret`, `totp_enabled` already in ORM, unused
- FastAPI web migration — services are framework-agnostic and ready
- `test_force_tick_emits_signal` — needs `pytest-qt` installed

---

## Bugs Fixed During Phase 2 Testing

| Bug | Fix |
|-----|-----|
| White text on Windows 11 dark mode | Forced Fusion style + explicit QPalette in `main.py` |
| Python 3.14 PyQt6 DLL load failure | Use Python 3.12 (`py -3.12`) |
| SMTP test showed generic error | Now shows actual exception message |
| "Verification email sent" even when send failed | `_send_smtp()` return value now checked |
| SMTP settings not picked up without restart | `get_smtp_config()` calls `load_dotenv(override=True)` |
| No password field when creating users | `users_page.py` `_UserForm` dialog built with password + confirm |
| Auto-verify on user creation | Removed — users now get a verification token via email |
| QAction imported inside for-loop | Moved to module level in all page files |
| `ROLES.index()` crash on unknown role | Wrapped in `try/except ValueError` with fallback to 0 |
| `_export_csv` ignored My Products filter | Now respects `self._show_my_products` |
