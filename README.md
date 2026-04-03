# Product License Timer

A desktop application for tracking trial software license expiry dates — with real-time countdowns, colour-coded alerts, email notifications, multi-user authentication, and Windows system tray support.

![Python](https://img.shields.io/badge/Python-3.13-blue) ![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## Versions

| Version | Description |
|---|---|
| **v2.0** (current) | Multi-user, SQL Server / SQLite, role-based access, email verification, self-service profiles |
| [v1.0](../../releases/tag/v1.0) | Single-user, SQLite only, no authentication |

---

## Features

### Core
- Track trial licenses for software products (Equitrac, PaperCut, YSoft SafeQ, AWMS, etc.)
- Real-time countdown per product (days, hours, minutes, seconds)
- Colour-coded rows: OK → Monitor → Warning → Critical → Expired
- Email alerts at **15, 10, and 5 day** thresholds (no duplicate sends)
- "Expired for: Xd Xh Xm Xs" counter on expired entries
- Add / Edit / Delete products with a form dialog
- Search and filter by product name, customer, or order number
- Sort and resize any column
- Export to CSV
- Windows system tray support (minimize to tray, double-click to restore)
- Auto-start on Windows boot (optional, via Settings)

### Multi-user (Phase 2)
- Role-based access control: **User**, **Admin**, **Superadmin**
- Email verification — new users set their own password via a secure web link
- Self-service **My Profile** page: update name, change email, change password
- **Forgot Password** flow with time-limited reset tokens
- **User Management** page (admin+): create, edit, disable, promote/demote users
- **Contacts** address book with roles: Consultant, Technical Consultant, Account Manager, Project Manager
- Product ownership — assign contacts per product; Assigned To column shows all owners
- **Created By** column tracks which user added each product
- Security email notifications: password changes and email changes trigger confirmation emails with a **Secure My Account** link — clicking it locks the account instantly and alerts all superadmins

### Settings
- **Timer** — configurable check interval (default 5 min, range 5 min – 5 days)
- **Email / SMTP** — configure outbound email; read-only for non-admins
- **System** — Windows autostart toggle
- **Verification** (admin+) — configure public verification URL and local port, with setup guide for Cloudflare Tunnel or reverse proxy; Test Public URL button

---

## Run from Source

### Requirements

- Python 3.13
- Windows (for system tray and autostart features)
- SQL Server (production) **or** SQLite (local/development)

### Setup

```bash
git clone https://github.com/skyconasia-ux/product-license-timer.git
cd product-license-timer
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL and SMTP settings
python -m migrations.init_schema
python main.py
```

### `.env` configuration

```env
# SQLite (local/dev):
DATABASE_URL=sqlite:///data/licenses.db

# SQL Server (production):
DATABASE_URL=mssql+pyodbc://user:pass@server/dbname?driver=ODBC+Driver+17+for+SQL+Server

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourname@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_TLS=true
SENDER_NAME=License Tracker
```

> **Gmail users:** Generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

### First login

Default superadmin credentials (forced password change on first login):
- **Email:** set during `init_schema` (prompted at setup)
- **Password:** `FujiFilm_11111`

### Run tests

```bash
pytest tests/ -k "not test_force_tick_emits_signal"
```

Expected: **76 passed**.

---

## Email Verification (Cloudflare Tunnel)

New users activate their accounts via a browser link. The app runs an embedded HTTP server (default port **8765**) that must be publicly reachable.

**Recommended: Cloudflare Tunnel**

```bash
cloudflared tunnel login
cloudflared tunnel create plt-verify
# Add CNAME in Cloudflare DNS: verify.yourdomain.com → <uuid>.cfargotunnel.com
# Create config.yml (see Settings → Verification tab for the full guide)
cloudflared service install
```

Then set **Public Verification URL** to `https://verify.yourdomain.com` in Settings → Verification.

To confirm the tunnel is working, open `https://verify.yourdomain.com/health` in any browser — you should see a green status page.

---

## Project Structure

```
product-license-timer/
├── main.py                         Entry point
├── config/
│   └── app_config.json             Timer + verification server settings
├── .env                            Database + SMTP credentials (gitignored)
├── models/
│   └── orm.py                      SQLAlchemy ORM models
├── services/
│   ├── auth_service.py             Login, tokens, password flows
│   ├── user_service.py             User CRUD
│   ├── contact_service.py          Contacts + system recipients
│   ├── product_service.py          Product CRUD
│   ├── notification_service.py     Email alerts
│   ├── db_session.py               Engine + auto schema migration
│   ├── timer_service.py            QTimer engine
│   └── verification_server.py      Embedded HTTP server (port 8765)
├── ui/
│   ├── login_dialog.py             Login + forgot password
│   ├── main_window.py              Shell + sidebar navigation
│   ├── product_table.py            Countdown table
│   ├── product_form.py             Add/Edit product dialog
│   ├── contacts_page.py            Address book
│   ├── recipients_page.py          System recipients
│   ├── users_page.py               User management (admin+)
│   ├── profile_page.py             My Profile (all users)
│   └── settings_dialog.py          Settings (Timer/SMTP/System/Verification)
├── migrations/
│   ├── init_schema.py              Fresh DB setup + superadmin seed
│   └── migrate_sqlite.py           Phase 1 → Phase 2 data migration
├── service/
│   ├── notification_daemon.py      Headless alert checker
│   └── windows_service.py          Windows Service wrapper
└── utils/
    ├── date_utils.py               Date helpers (DD-MM-YYYY)
    └── csv_exporter.py             CSV export
```

---

## Migrating from v1.0 (Phase 1)

If you have an existing Phase 1 SQLite database:

```bash
python -m migrations.migrate_sqlite --sqlite path/to/old/licenses.db
```

This copies all products and notification history into the Phase 2 database without data loss.

---

## License

MIT
