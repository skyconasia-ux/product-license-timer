# Product License Timer — Phase 2 Multi-User Upgrade
**Date:** 2026-04-02
**Status:** Approved
**Location:** `C:\Claude Projects\Product License Timer\`
**Approach:** Option A — Incremental Layering (extend existing codebase, no rebuild from scratch)

---

## 1. Overview

Upgrade the existing single-user SQLite desktop app into a centralized multi-user system with:
- Microsoft SQL Server Express as the shared database (network-accessible)
- SQLAlchemy ORM replacing raw sqlite3
- User authentication with login screen, roles, email verification
- Contacts address book and system recipients managed from the DB
- Product ownership assignment (Consultant / Account Manager / Project Manager)
- Modular service architecture ready for future FastAPI/web migration
- All dates displayed in Singapore format: `DD-MM-YYYY`

---

## 2. Folder Structure

```
C:\Claude Projects\Product License Timer\
├── main.py                          # Extended: shows LoginDialog before MainWindow
├── .env                             # NEW: DB connection string + SMTP settings
├── requirements.txt                 # Updated: sqlalchemy, pyodbc, bcrypt, python-dotenv
├── models/
│   ├── database.py                  # KEEP as-is (SQLite — migration source only)
│   └── orm.py                       # NEW: SQLAlchemy Base + all ORM models
├── services/
│   ├── database_service.py          # KEEP (deprecated after migration, not deleted)
│   ├── notification_service.py      # UPDATED: recipients from DB, SMTP from .env
│   ├── timer_service.py             # KEEP as-is
│   ├── auth_service.py              # NEW: login, bcrypt, session, user management
│   ├── user_service.py              # NEW: user CRUD (admin/superadmin only)
│   ├── product_service.py           # NEW: replaces database_service product CRUD
│   ├── contact_service.py           # NEW: contacts + system_recipients CRUD
│   └── db_session.py                # NEW: SQLAlchemy engine + session factory
├── ui/
│   ├── main_window.py               # UPDATED: left sidebar, user context, filter toggle
│   ├── login_dialog.py              # NEW: light centered card login screen
│   ├── product_table.py             # UPDATED: compact Assigned To column, DD-MM-YYYY
│   ├── product_form.py              # UPDATED: ownership dropdowns, notes, DD-MM-YYYY
│   ├── contacts_page.py             # NEW: address book management (admin+)
│   ├── recipients_page.py           # NEW: system recipients management (admin+)
│   └── settings_dialog.py          # UPDATED: SMTP only, recipients removed
├── utils/
│   ├── date_utils.py                # KEEP as-is
│   └── csv_exporter.py             # KEEP as-is
└── migrations/
    ├── init_schema.py               # NEW: fresh DB setup + superadmin seed
    └── migrate_sqlite.py            # NEW: SQLite → SQL Server data migration
```

---

## 3. Database Schema (SQLAlchemy ORM)

### 3.1 `users`
```python
id              Integer PK
email           String, unique, not null
password_hash   String, not null
role            Enum('user', 'admin', 'superadmin')
is_verified     Boolean, default False
is_active       Boolean, default True
totp_secret     String, nullable          # Phase 3 placeholder
totp_enabled    Boolean, default False    # Phase 3 placeholder
created_at      DateTime, default now()
```

### 3.2 `contacts` (Address Book)
```python
id          Integer PK
name        String, not null
email       String, not null
role_type   Enum('Consultant', 'Account Manager', 'Project Manager')
```

### 3.3 `system_recipients`
```python
id          Integer PK
name        String, not null
email       String, not null
role_type   Enum('Solutions Team', 'Admin', 'Support')
is_active   Boolean, default True
```

### 3.4 `products` (extended)
```python
id                   Integer PK
product_name         String, not null, unique   # renamed from 'name'
customer_name        String, default ''
order_number         String, default ''
start_date           Date, not null
duration_days        Integer, not null, check > 0
expiry_date          Date, not null
notes                String, default ''
created_by           FK → users.id
consultant_id        FK → contacts.id, nullable
account_manager_id   FK → contacts.id, nullable
project_manager_id   FK → contacts.id, nullable
```

### 3.5 `notifications_log` (unchanged logic)
```python
id                  Integer PK
product_id          FK → products.id, CASCADE delete
notification_type   Enum('15_days', '10_days', '5_days')
sent_at             DateTime
UNIQUE(product_id, notification_type)
```

### 3.6 `email_verifications`
```python
id          Integer PK
user_id     FK → users.id, CASCADE delete
token       String, unique
expires_at  DateTime
```

### 3.7 Connection
`db_session.py` reads `DATABASE_URL` from `.env`:
```
DATABASE_URL=mssql+pyodbc://user:pass@server/dbname?driver=ODBC+Driver+17+for+SQL+Server
```
SQLAlchemy engine created once at startup. Sessions scoped per operation.

---

## 4. Authentication & Session

### 4.1 Roles

| Role | Products | Contacts / Recipients | Manage Users | Promote user→admin | Demote/remove admins |
|---|---|---|---|---|---|
| `user` | ✅ | ✗ | ✗ | ✗ | ✗ |
| `admin` | ✅ | ✅ | ✅ | ✅ | ✗ |
| `superadmin` | ✅ | ✅ | ✅ | ✅ | ✅ only |

Only one superadmin exists (the bootstrapped default account). Promoting a user to admin does not make them superadmin.

### 4.2 Default Superadmin (seeded by `init_schema.py`)
- Email: prompted at first run (corporate email recommended)
- Password: `FujiFilm_11111` (forced change on first login)
- Role: `superadmin`, `is_verified: True`
- A one-time recovery code is generated and printed to console at seed time — store it securely

### 4.3 Login Flow
1. `main.py` shows `LoginDialog` before `MainWindow`
2. On success → `UserSession` dataclass passed into `MainWindow`
3. If login cancelled/closed → app exits
4. Default password detected on login → mandatory password-change dialog shown

### 4.4 `UserSession` (in-memory, not persisted)
```python
@dataclass
class UserSession:
    user_id: int
    email:   str
    role:    str    # 'user' | 'admin' | 'superadmin'
```

### 4.5 `auth_service.py`
```python
def login(email, password) -> UserSession | None
def create_user(email, password, role) -> User        # admin + superadmin
def promote_to_admin(user_id) -> None                 # admin + superadmin
def demote_admin(user_id) -> None                     # superadmin only
def delete_user(user_id) -> None                      # superadmin only
def change_password(user_id, old_pw, new_pw) -> None  # any logged-in user
def change_email(user_id, new_email) -> None          # superadmin (own account)
```

### 4.6 Email Verification
- New user created → `is_verified = False`, verification email sent with unique token
- User cannot log in until verified
- Token stored in `email_verifications` table, expires 24 hours
- Admin/superadmin can resend verification from user management screen

### 4.7 Recovery
| Layer | Description |
|---|---|
| Recovery code | One-time token printed at `init_schema.py` run. Used via `reset_superadmin.py --token <code>` |
| CLI reset | `reset_superadmin.py` — runs on server with DB access, no token required |
| Force-change | Default password triggers mandatory change dialog on first login |

### 4.8 2FA — Phase 3 Placeholder
`totp_secret` and `totp_enabled` columns exist but are unused in Phase 2. Architecture designed for TOTP drop-in during web migration.

---

## 5. Notification Logic

### 5.1 Recipients Resolution (replaces `email_config.json` recipients)
```
For each product at threshold (15 / 10 / 5 days):
  1. Fetch all active system_recipients from DB
  2. If product.consultant_id → add consultant email
  3. If product.account_manager_id → add account manager email
  4. If product.project_manager_id → add project manager email
  5. Deduplicate combined list
  6. Send one email to all resolved recipients
  7. Log to notifications_log
```

### 5.2 Email Body (extended)
```
Subject: ⚠ Trial Expiry Alert — [Product Name] ([N] days remaining)

Product Name    : PaperCut MF
Customer        : Acme Corp
Order Number    : ORD-1234
Start Date      : 01-01-2026
Expiry Date     : 01-04-2026
Days Remaining  : 10
Threshold       : 10-day warning
Consultant      : Alice K. (alice@company.com)
Account Manager : Carol M. (carol@company.com)
Project Manager : —

Please renew or arrange a replacement license before the expiry date.
```

### 5.3 SMTP Config
- Moved from `email_config.json` to `.env`
- `email_config.json` kept for backward compatibility but ignored once `.env` is present
- Settings dialog (Email/SMTP tab) writes to `.env`

---

## 6. UI Design Decisions

### 6.1 Login Screen
- Style: Light centered card (white card, app icon, subtle shadow)
- Fields: Email, Password, Sign In button
- Shows "No users exist — run init_schema.py" if DB has no users
- Mandatory password-change dialog on first login with default password

### 6.2 Main Window — Left Sidebar Navigation
```
[📋 Products      ]  ← highlighted when active
[👤 Contacts      ]  ← admin + superadmin only
[📧 Recipients    ]  ← admin + superadmin only
─────────────────
[⚙  Settings      ]
[👤 user@email.com]  ← logged-in user shown at bottom
```

### 6.3 Product Table
- New compact "Assigned To" column with colour-coded pills:
  - `C: Name` → blue pill (Consultant)
  - `AM: Name` → green pill (Account Manager)
  - `PM: Name` → purple pill (Project Manager)
  - Unassigned roles omitted; if none assigned → `—`
- "My Products" / "All Products" filter toggle
- All dates: `DD-MM-YYYY`
- Existing colour coding preserved (green/yellow/orange/red/grey)

### 6.4 Add/Edit Product Form
Fields (top section):
- Product Name (required)
- Customer Name, Order Number (2-column row)
- Start Date, Duration in days (2-column row)
- Expiry Date (read-only, auto-calculated)
- Notes (multiline)

Ownership section (below divider, labelled "OWNERSHIP (OPTIONAL)"):
- Consultant dropdown → filtered from contacts where role_type = 'Consultant'
- Account Manager dropdown → filtered from contacts where role_type = 'Account Manager'
- Project Manager dropdown → filtered from contacts where role_type = 'Project Manager'
- Default option: `— Unassigned —` → stores NULL

### 6.5 Contacts Page (admin+)
- Table columns: Name, Email, Role Type
- Toolbar: Add, Edit, Delete

### 6.6 Recipients Page (admin+)
- Table columns: Name, Email, Role Type, Active
- Toolbar: Add, Edit, Delete, Toggle Active

### 6.7 Settings Dialog — SMTP Tab (stripped)
Kept: SMTP Host, Port, Username, Password, TLS/SSL toggle, Sender Name, Test Email button
Removed: Recipients list (now managed in Recipients page)

---

## 7. Configuration

### 7.1 `.env`
```env
# Database
DATABASE_URL=mssql+pyodbc://user:pass@server/dbname?driver=ODBC+Driver+17+for+SQL+Server

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_TLS=true
SENDER_NAME=License Tracker
```

### 7.2 `requirements.txt` additions
```
sqlalchemy>=2.0
pyodbc>=5.0
bcrypt>=4.0
python-dotenv>=1.0
```

---

## 8. Migration Scripts

### 8.1 `migrations/init_schema.py` (fresh install)
1. Read `DATABASE_URL` from `.env`
2. Create all tables via SQLAlchemy metadata
3. Prompt for superadmin email
4. Seed superadmin: `role=superadmin`, `password=FujiFilm_11111`, `is_verified=True`
5. Generate + print one-time recovery code (store securely)
6. Print "First login will require a password change"

### 8.2 `migrations/migrate_sqlite.py` (existing data)
1. Read SQLite source path + `DATABASE_URL` from `.env`
2. For each product in SQLite → insert into SQL Server:
   - Maps `name` → `product_name`
   - Sets `created_by` = superadmin id
   - Sets `consultant_id`, `account_manager_id`, `project_manager_id` = NULL
3. Copy `notifications_log` rows (product_id remapped)
4. Print summary: X products migrated, Y notification logs migrated

---

## 9. Security
- Passwords hashed with bcrypt (cost factor 12)
- ORM only — no raw SQL anywhere
- Email format validated on registration
- `.env` excluded from git (add to `.gitignore`)
- Session in-memory only — no tokens written to disk in Phase 2

---

## 10. Future Compatibility (Phase 3)
- All services are framework-agnostic (no PyQt imports in service layer)
- SQLAlchemy models can be reused directly with FastAPI
- `UserSession` dataclass maps cleanly to a JWT payload
- `totp_secret` / `totp_enabled` columns ready for TOTP 2FA
- Left sidebar navigation mirrors a future web sidebar layout

---

## 11. What Is NOT Changing
- Timer service logic (QTimer, tick interval, Check Now)
- Colour coding on the product table
- CSV export and database backup
- System tray behaviour
- Auto-start on Windows boot (registry key)
- Existing test suite (kept, new services get their own tests)
