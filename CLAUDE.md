# Product License Timer — CLAUDE.md

Project instructions for Claude Code. These override default assistant behaviour.

---

## Project Overview

Desktop app (PyQt6) that tracks software trial license expiry dates and sends email alerts at 15, 10, and 5-day thresholds.

- **Phase 1** — Single-user SQLite app with a product table, timer, system tray, and SMTP notifications.
- **Phase 2** — Multi-user upgrade: SQL Server / SQLAlchemy ORM, user authentication (login / roles / email verification), contacts address book, system recipients, product ownership, left sidebar navigation, embedded verification web server, self-service profile management.

**Location:** `C:\Users\Administrator\product-license-timer\`
**GitHub:** `skyconasia-ux/product-license-timer`
**Python:** 3.13  |  **UI:** PyQt6  |  **ORM:** SQLAlchemy 2.0

---

## Branch and Worktree Conventions

- `master` — main working branch (Phase 2 active)
- `feature/phase2-multi-user` — Phase 2 feature branch (currently active)
- Working directory: `C:\Users\Administrator\product-license-timer\`

---

## Architecture

```
main.py                       Entry point — light theme, starts verification server,
                              login loop, launches MainWindow
models/
  orm.py                      SQLAlchemy ORM (Phase 2 canonical models)
  database.py                 Legacy SQLite schema (Phase 1, kept as migration source)
services/
  auth_service.py             Login, bcrypt, UserSession dataclass, email verification,
                              password reset, email change tokens, account secure tokens
  user_service.py             User CRUD — role-gated (admin / superadmin)
  contact_service.py          Contacts + SystemRecipients CRUD
  product_service.py          Product CRUD with ownership FK support
  notification_service.py     resolve_recipients, format_email_body, check_and_send_v2
  db_session.py               SQLAlchemy engine + session factory + auto schema migration
  timer_service.py            QTimer wrapper (unchanged from Phase 1)
  verification_server.py      Embedded HTTP server (port 8765) for email verification,
                              email-change confirmation, and account security pages.
                              get_base_url() always reads live from app_config.json —
                              no restart needed after changing the public URL in Settings.
  database_service.py         Legacy SQLite service (Phase 1 only, not used in Phase 2)
ui/
  login_dialog.py             Login card + forced password-change + forgot password flow
  main_window.py              Shell: sidebar nav, product page, tray, timer wiring
  product_table.py            ProductTable widget — ORM + legacy dict compatible;
                              column order: Customer → Order # → Product Name → …;
                              all cells centre-aligned; all columns user-resizable
                              (Interactive mode + resizeColumnsToContents on refresh)
  product_form.py             Add/Edit dialog — ownership dropdowns, DD-MM-YYYY
  contacts_page.py            Address book management (admin+)
  recipients_page.py          System recipients management (admin+)
  users_page.py               User management (admin+) — context menu, User Properties
  profile_page.py             My Profile — self-service name/email/password (all users)
  settings_dialog.py          Four tabs: Timer | Email/SMTP | System | Verification (admin+)
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

## ORM Models (`models/orm.py`)

| Model | Table | Purpose |
|---|---|---|
| `User` | `users` | Accounts — email, full_name, password_hash, role, is_verified, is_active |
| `Contact` | `contacts` | Address book — name, email, role_type |
| `SystemRecipient` | `system_recipients` | Notification recipients |
| `Product` | `products` | License records with ownership FKs |
| `NotificationLog` | `notifications_log` | Deduplication of sent alerts |
| `EmailVerification` | `email_verifications` | 24h token for new account activation |
| `PasswordResetToken` | `password_reset_tokens` | 20-min single-use password reset token |
| `EmailChangeToken` | `email_change_tokens` | 24h token for email address change flow |
| `AccountSecureToken` | `account_secure_tokens` | 72h token embedded in security notification emails; clicking it locks the account and alerts superadmins. Stores `triggered_from_email` for historical tracing — equals current email for password-change alerts, equals OLD email for email-change alerts |

### ContactRoleType enum values
`consultant` | `technical_consultant` | `account_manager` | `project_manager`

### Product ownership FKs
`consultant_id` | `technical_consultant_id` | `account_manager_id` | `project_manager_id`
(all nullable FKs to `contacts.id`, ON DELETE SET NULL)

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
- **Schema auto-migration** runs on every startup in `db_session._apply_schema_migrations()`:
  - Calls `Base.metadata.create_all(engine)` (new tables only)
  - Then uses `inspect()` to `ALTER TABLE` for new columns on existing tables
  - Add any new column migrations there — do NOT require manual SQL from users

### Authentication
- Passwords hashed with bcrypt, cost factor 12
- `UserSession` dataclass is in-memory only — never persisted to disk
- Three roles: `user` | `admin` | `superadmin`
- Default password: `FujiFilm_11111` — forced change on first login
- Only one superadmin (seeded by `init_schema.py`)
- SuperAdmin cannot be modified or deleted by admins — enforced in `user_service`

### Service layer rules
- **No PyQt imports in any service file** — services must be framework-agnostic
- Services accept `session: Session` and `caller: UserSession` as parameters
- Permission checks via `_require_role(caller, *roles)`

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

### `config/app_config.json`
```json
{
  "timer_interval_seconds": 300,
  "timer_min_seconds": 300,
  "timer_max_seconds": 432000,
  "verification_server_port": 8765,
  "verification_server_url": "https://verify.skyconasia.com"
}
```

- `verification_server_port` — local port the embedded HTTP server binds to (`0.0.0.0`)
- `verification_server_url` — public URL used in emailed links (e.g. Cloudflare Tunnel URL);
  leave empty to auto-detect machine hostname.
  Changes saved in Settings take effect immediately for new tokens — no restart needed.

### First-time setup (Phase 2)
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL and SMTP settings
python -m migrations.init_schema
python main.py
```

---

## Verification Server (`services/verification_server.py`)

An embedded HTTP server that starts automatically with the app (daemon thread, port 8765).
Exposed publicly via **Cloudflare Tunnel** → `https://verify.skyconasia.com`.

`get_base_url()` always reads live from `app_config.json` — no module-level cache —
so changing the URL in Settings → Verification tab takes effect for the next token generated.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check — returns green "Server is Running" page. Use this to test tunnel end-to-end from any browser without needing a token. |
| `/verify?token=…` | GET | Show password-set form for new account activation |
| `/verify` | POST | Validate token, mark verified, set password |
| `/change-email?token=…` | GET | Show confirm-email-change form |
| `/change-email` | POST | Swap email + set new password atomically |
| `/secure-account?token=…` | GET | Show confirmation page before locking account |
| `/secure-account` | POST | Disable account + email all superadmins security alert |

### Testing the tunnel
- From the server itself: DNS resolution of the Cloudflare hostname will fail (internal AD DNS).
  This is normal — test locally via `http://localhost:8765/health`.
- From any external device/browser: open `https://verify.skyconasia.com/health`.
  A green page confirms the tunnel is working end-to-end.
- `DNS_PROBE_FINISHED_NXDOMAIN` from an external browser means the Cloudflare DNS CNAME
  record has not been created yet — add it in the Cloudflare dashboard.

### Cloudflare Tunnel (DC02-Main)
- Tunnel name: `plt-verify` (UUID: `f63e3e6b-5c01-4634-9ce9-bae92d4ff1d0`)
- Config: `C:\Users\Administrator\.cloudflared\config.yml`
- Runs as Windows Service (`cloudflared service install`)
- DNS CNAME: `verify.skyconasia.com` → `f63e3e6b-5c01-4634-9ce9-bae92d4ff1d0.cfargotunnel.com`

### User creation flow (admin creates new user)
1. Admin fills Name + Email + Role in Create User dialog (no password field)
2. System generates a random unguessable temp password
3. 24h `EmailVerification` token created → activation link emailed to new user
4. User clicks `https://verify.skyconasia.com/verify?token=…`
5. User sets their own password → account activated → login with new email + password
6. If SMTP not configured → admin sees the link in a copyable dialog

### Email change flow (user changes their own email)
1. User goes to My Profile → enters new email + current password
2. 24h `EmailChangeToken` created → confirmation link emailed to **new** address
3. User clicks `https://verify.skyconasia.com/change-email?token=…`
4. User sets new password → email + password updated atomically
5. Security notification with Secure Account link sent to the **old** email
6. User must log out and log in with new email + new password

### Password reset flow (forgot password on login screen)
1. User clicks "Forgot Password" → enters email
2. 20-min `PasswordResetToken` created → link emailed (or shown if no SMTP)
3. Same dialog transitions to Step 2: enter token + new password
4. Password updated, token invalidated

---

## Settings Dialog (`ui/settings_dialog.py`)

Four tabs — **Timer**, **Email / SMTP**, **System**, **Verification** (admin+ only).

| Tab | Visible to | Contents |
|---|---|---|
| Timer | All | Check interval, min/max bounds |
| Email / SMTP | All (read-only for non-admin) | SMTP host/port/user/pass/TLS, Test Connection button |
| System | All | Windows autostart checkbox |
| Verification | Admin+ only | Public Verification URL, Local Server Port, Test Public URL button, setup guide |

### Verification tab — Test Public URL button
1. Tests `localhost:<port>/health` — confirms embedded server is running
2. Tests `<public_url>/health` — confirms tunnel is reachable from this machine
   - `getaddrinfo failed` / error 11001 → normal (internal AD DNS); test from external device instead
   - Connection refused / timeout → tunnel not running or misconfigured

---

## Product Table (`ui/product_table.py`)

- **Column order:** Customer → Order # → Product Name → Start Date → Duration → Expiry Date → Days Left → Remaining Time → Status → Assigned To → Created By (ID hidden)
- **All cells:** centre-aligned (`Qt.AlignmentFlag.AlignCenter`)
- **Column resizing:** all columns use `Interactive` mode — user can drag any column edge.
  `resizeColumnsToContents()` is called after every data refresh to set sensible initial widths.

---

## User Management (`ui/users_page.py`)

Admin+ only. Features:
- **Table columns:** Name, Email, Role, Verified, Status (Active/Disabled)
- **Right-click context menu** (context-sensitive):
  - Edit → opens User Properties dialog
  - Make Admin / Remove Admin (based on current role)
  - Disable Account / Enable Account (based on is_active)
  - Resend Verification Link (unverified users only)
  - Verify Manually / Delete (superadmin only)
- **Double-click** → User Properties dialog (Full Name, Email read-only, role checkbox, disable checkbox)

---

## My Profile (`ui/profile_page.py`)

Visible to **all users** via sidebar. Three independent sections:

| Section | Fields | Email notification sent |
|---|---|---|
| Personal Information | Full Name | Notification to current email on save |
| Change Email | New email + current password | (1) Verification link to *new* email; (2) after confirmation, security notification with Secure Account link sent to **old** email |
| Change Password | Current + new + confirm | Confirmation email with a **Secure My Account** link (72h) — if clicked, disables account and alerts all superadmins |

### Secure Account link behaviour
When a Secure Account link is clicked (from any security email):
- Account is disabled immediately (`is_active = False`) — the new email cannot log in either
- All superadmins receive a **SECURITY ALERT** email containing:
  - Current account email
  - `triggered_from_email` (the address that received the link) — if different from the current email, the alert flags that the email change itself may have been unauthorized
- Account stays locked until a superadmin re-enables it via Users → right-click → Enable Account
- `triggered_from_email` stored on `AccountSecureToken` provides a permanent audit trail

---

## SMTP Settings

- Tab visible to **all users** in Settings dialog
- Non-admin users: all fields read-only, Test Connection disabled
- Admin+ can edit and save SMTP configuration

---

## Running Tests
```bash
pytest tests/ -k "not test_force_tick_emits_signal"
```
The excluded test (`test_force_tick_emits_signal`) requires `pytest-qt` which is not installed — this is a pre-existing Phase 1 test that is harmless to skip.

Expected: **76 passed**.

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

## Known Deferred Items (Phase 2)
- Colour-coded pills in Assigned To column (blue/green/purple) — needs custom delegate — TODO comment in `product_table.py`
- Audit logging for profile updates and role changes — schema not yet added

## Known Deferred Items (Phase 3)
- 2FA / TOTP — columns `totp_secret`, `totp_enabled` already in ORM, unused
- FastAPI web migration — services are framework-agnostic and ready
- `test_force_tick_emits_signal` — needs `pytest-qt` installed
