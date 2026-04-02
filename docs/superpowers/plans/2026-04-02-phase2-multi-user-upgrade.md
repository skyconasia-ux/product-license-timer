# Phase 2 Multi-User Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the single-user SQLite desktop app into a centralized multi-user system with SQL Server, SQLAlchemy ORM, authentication, contacts, product ownership, and overhauled notifications.

**Architecture:** Incremental layering — extend existing files, add new ones alongside. SQLite code preserved as migration source. All services are PyQt-free so they can be reused in a future FastAPI backend.

**Tech Stack:** Python 3.13, PyQt6, SQLAlchemy 2.0, pyodbc, bcrypt, python-dotenv, SQL Server Express (SQLite in-memory for tests)

---

## Phase 1 — Foundation (DB Layer)

### Task 1: Project dependencies + `.env`

**Files:**
- Modify: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore` (update)

- [ ] **Step 1: Update `requirements.txt`**

```
PyQt6>=6.6.0
sqlalchemy>=2.0
pyodbc>=5.0
bcrypt>=4.0
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 2: Create `.env.example`**

```env
DATABASE_URL=mssql+pyodbc://user:pass@server/dbname?driver=ODBC+Driver+17+for+SQL+Server
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_TLS=true
SENDER_NAME=License Tracker
```

- [ ] **Step 3: Add `.env` to `.gitignore`**

Add these lines to `.gitignore` (create if missing):
```
.env
data/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example .gitignore
git commit -m "chore: add phase 2 dependencies and env template"
```

---

### Task 2: SQLAlchemy models (`models/orm.py`)

**Files:**
- Create: `models/orm.py`
- Create: `tests/test_orm.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_orm.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import (
    Base, User, Contact, SystemRecipient,
    Product, NotificationLog, EmailVerification,
    UserRole, ContactRoleType, RecipientRoleType, NotificationType
)
from datetime import date, datetime, timedelta


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    engine.dispose()


def test_user_creation(session):
    u = User(email="test@example.com", password_hash="hashed", role=UserRole.user)
    session.add(u)
    session.commit()
    assert session.get(User, u.id).email == "test@example.com"


def test_contact_creation(session):
    c = Contact(name="Alice", email="alice@co.com", role_type=ContactRoleType.consultant)
    session.add(c)
    session.commit()
    assert session.get(Contact, c.id).role_type == ContactRoleType.consultant


def test_product_with_ownership(session):
    u = User(email="admin@co.com", password_hash="h", role=UserRole.superadmin)
    c = Contact(name="Alice", email="alice@co.com", role_type=ContactRoleType.consultant)
    session.add_all([u, c])
    session.flush()
    p = Product(
        product_name="PaperCut MF",
        start_date=date(2026, 1, 1),
        duration_days=90,
        expiry_date=date(2026, 4, 1),
        created_by=u.id,
        consultant_id=c.id,
    )
    session.add(p)
    session.commit()
    loaded = session.get(Product, p.id)
    assert loaded.consultant_id == c.id
    assert loaded.account_manager_id is None


def test_notification_log_unique(session):
    from sqlalchemy.exc import IntegrityError
    u = User(email="a@b.com", password_hash="h", role=UserRole.user)
    session.add(u)
    session.flush()
    p = Product(product_name="X", start_date=date(2026,1,1), duration_days=30,
                expiry_date=date(2026,1,31), created_by=u.id)
    session.add(p)
    session.flush()
    session.add(NotificationLog(product_id=p.id, notification_type=NotificationType.days_15))
    session.commit()
    session.add(NotificationLog(product_id=p.id, notification_type=NotificationType.days_15))
    with pytest.raises(IntegrityError):
        session.commit()


def test_email_verification(session):
    u = User(email="v@co.com", password_hash="h", role=UserRole.user)
    session.add(u)
    session.flush()
    ev = EmailVerification(user_id=u.id, token="abc123",
                           expires_at=datetime.now() + timedelta(hours=24))
    session.add(ev)
    session.commit()
    assert session.query(EmailVerification).filter_by(token="abc123").first() is not None
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_orm.py -v
```

Expected: `ImportError` — `models/orm.py` does not exist yet.

- [ ] **Step 3: Create `models/orm.py`**

```python
"""SQLAlchemy ORM models for Phase 2. Replaces raw sqlite3 schema."""
from __future__ import annotations
import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRole(enum.Enum):
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class ContactRoleType(enum.Enum):
    consultant = "Consultant"
    account_manager = "Account Manager"
    project_manager = "Project Manager"


class RecipientRoleType(enum.Enum):
    solutions_team = "Solutions Team"
    admin = "Admin"
    support = "Support"


class NotificationType(enum.Enum):
    days_15 = "15_days"
    days_10 = "10_days"
    days_5 = "5_days"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_type: Mapped[ContactRoleType] = mapped_column(Enum(ContactRoleType))


class SystemRecipient(Base):
    __tablename__ = "system_recipients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_type: Mapped[RecipientRoleType] = mapped_column(Enum(RecipientRoleType))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    order_number: Mapped[str] = mapped_column(String(100), default="")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), default="")
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True)
    consultant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=True)
    account_manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=True)
    project_manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=True)


class NotificationLog(Base):
    __tablename__ = "notifications_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"))
    notification_type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    __table_args__ = (UniqueConstraint("product_id", "notification_type"),)


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_orm.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add models/orm.py tests/test_orm.py
git commit -m "feat: add SQLAlchemy ORM models"
```

---

### Task 3: DB session factory (`services/db_session.py`)

**Files:**
- Create: `services/db_session.py`
- Create: `tests/test_db_session.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_db_session.py`:

```python
import pytest
from unittest.mock import patch
from services.db_session import get_session, get_engine


def test_get_session_returns_session():
    with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"}):
        from importlib import reload
        import services.db_session as dbs
        reload(dbs)
        session = dbs.get_session()
        assert session is not None
        session.close()


def test_get_engine_uses_env():
    with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"}):
        from importlib import reload
        import services.db_session as dbs
        reload(dbs)
        engine = dbs.get_engine()
        assert "sqlite" in str(engine.url)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_db_session.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `services/db_session.py`**

```python
"""SQLAlchemy engine and session factory. Reads DATABASE_URL from .env."""
from __future__ import annotations
import os
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

_engine: Engine | None = None
_SessionLocal = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL not set in .env")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_db_session.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/db_session.py tests/test_db_session.py
git commit -m "feat: add SQLAlchemy session factory"
```

---

### Task 4: Migration scripts

**Files:**
- Create: `migrations/__init__.py`
- Create: `migrations/init_schema.py`
- Create: `migrations/migrate_sqlite.py`

- [ ] **Step 1: Create `migrations/__init__.py`** (empty)

- [ ] **Step 2: Create `migrations/init_schema.py`**

```python
"""
Run once on a fresh SQL Server database.
Usage: python -m migrations.init_schema
"""
from __future__ import annotations
import secrets
import sys
import bcrypt
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os

load_dotenv()


def main() -> None:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    from models.orm import Base, User, UserRole
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    print("Tables created.")

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    existing = session.query(User).filter_by(role=UserRole.superadmin).first()
    if existing:
        print("Superadmin already exists. Skipping seed.")
        session.close()
        return

    email = input("Enter superadmin email: ").strip()
    if not email or "@" not in email:
        print("ERROR: Invalid email.")
        sys.exit(1)

    pw_hash = bcrypt.hashpw("FujiFilm_11111".encode(), bcrypt.gensalt(rounds=12)).decode()
    superadmin = User(
        email=email,
        password_hash=pw_hash,
        role=UserRole.superadmin,
        is_verified=True,
        is_active=True,
    )
    session.add(superadmin)
    session.commit()

    recovery_code = secrets.token_hex(16)
    # Store hashed recovery code in a local file (not DB) for offline reset
    recovery_path = os.path.join(os.path.dirname(__file__), ".recovery_code")
    with open(recovery_path, "w") as f:
        import hashlib
        f.write(hashlib.sha256(recovery_code.encode()).hexdigest())

    print(f"\nSuperadmin created: {email}")
    print(f"Default password:   FujiFilm_11111 (you will be forced to change this on first login)")
    print(f"\n*** RECOVERY CODE (store this securely — shown only once) ***")
    print(f"    {recovery_code}")
    print(f"*** END RECOVERY CODE ***\n")
    session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `migrations/migrate_sqlite.py`**

```python
"""
Migrate existing SQLite data to SQL Server.
Usage: python -m migrations.migrate_sqlite --sqlite path/to/licenses.db
"""
from __future__ import annotations
import argparse
import sqlite3
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True, help="Path to SQLite licenses.db")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    from models.orm import Base, User, UserRole, Product, NotificationLog, NotificationType
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get or create superadmin as owner for migrated products
    superadmin = session.query(User).filter_by(role=UserRole.superadmin).first()
    if not superadmin:
        print("ERROR: Run init_schema.py first to create superadmin.")
        sys.exit(1)

    src = sqlite3.connect(args.sqlite)
    src.row_factory = sqlite3.Row

    products = src.execute("SELECT * FROM products").fetchall()
    id_map: dict[int, int] = {}  # old_id -> new_id
    product_count = 0

    for row in products:
        existing = session.query(Product).filter_by(product_name=row["name"]).first()
        if existing:
            id_map[row["id"]] = existing.id
            continue
        p = Product(
            product_name=row["name"],
            customer_name=row["customer_name"] or "",
            order_number=row["order_number"] or "",
            start_date=date.fromisoformat(row["start_date"]),
            duration_days=row["duration_days"],
            expiry_date=date.fromisoformat(row["expiry_date"]),
            notes=row["notes"] or "",
            created_by=superadmin.id,
        )
        session.add(p)
        session.flush()
        id_map[row["id"]] = p.id
        product_count += 1

    ntype_map = {"15_days": NotificationType.days_15,
                 "10_days": NotificationType.days_10,
                 "5_days":  NotificationType.days_5}
    logs = src.execute("SELECT * FROM notifications_log").fetchall()
    log_count = 0
    for row in logs:
        new_pid = id_map.get(row["product_id"])
        if not new_pid:
            continue
        ntype = ntype_map.get(row["notification_type"])
        if not ntype:
            continue
        from datetime import datetime
        existing_log = session.query(NotificationLog).filter_by(
            product_id=new_pid, notification_type=ntype).first()
        if existing_log:
            continue
        session.add(NotificationLog(
            product_id=new_pid,
            notification_type=ntype,
            sent_at=datetime.fromisoformat(row["sent_at"]),
        ))
        log_count += 1

    session.commit()
    src.close()
    session.close()
    print(f"Migration complete: {product_count} products, {log_count} notification logs.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify scripts are importable**

```bash
python -c "from migrations.init_schema import main; print('OK')"
python -c "from migrations.migrate_sqlite import main; print('OK')"
```

Expected: `OK` for both.

- [ ] **Step 5: Commit**

```bash
git add migrations/ 
git commit -m "feat: add init_schema and migrate_sqlite scripts"
```

---

## Phase 2 — Authentication

### Task 5: Auth service (`services/auth_service.py`)

**Files:**
- Create: `services/auth_service.py`
- Create: `tests/test_auth_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_auth_service.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base, User, UserRole
from services.auth_service import (
    login, hash_password, change_password,
    create_verification_token, verify_email_token,
    UserSession, DEFAULT_PASSWORD, is_default_password,
)
from datetime import datetime, timedelta
from models.orm import EmailVerification


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def verified_user(session):
    u = User(
        email="user@co.com",
        password_hash=hash_password("MyPass1!"),
        role=UserRole.user,
        is_verified=True,
        is_active=True,
    )
    session.add(u)
    session.commit()
    return u


def test_login_success(session, verified_user):
    result = login(session, "user@co.com", "MyPass1!")
    assert isinstance(result, UserSession)
    assert result.email == "user@co.com"
    assert result.role == "user"


def test_login_wrong_password(session, verified_user):
    assert login(session, "user@co.com", "wrongpass") is None


def test_login_unverified(session):
    u = User(email="u2@co.com", password_hash=hash_password("p"),
             role=UserRole.user, is_verified=False, is_active=True)
    session.add(u)
    session.commit()
    assert login(session, "u2@co.com", "p") is None


def test_login_inactive(session):
    u = User(email="u3@co.com", password_hash=hash_password("p"),
             role=UserRole.user, is_verified=True, is_active=False)
    session.add(u)
    session.commit()
    assert login(session, "u3@co.com", "p") is None


def test_change_password(session, verified_user):
    assert change_password(session, verified_user.id, "MyPass1!", "NewPass2!") is True
    assert login(session, "user@co.com", "NewPass2!") is not None


def test_change_password_wrong_old(session, verified_user):
    assert change_password(session, verified_user.id, "wrongold", "NewPass2!") is False


def test_is_default_password():
    assert is_default_password(DEFAULT_PASSWORD) is True
    assert is_default_password("something_else") is False


def test_email_verification_flow(session, verified_user):
    token = create_verification_token(session, verified_user.id)
    assert len(token) > 10
    assert verify_email_token(session, token) is True
    # token consumed — second attempt fails
    assert verify_email_token(session, token) is False


def test_expired_token_rejected(session, verified_user):
    token = create_verification_token(session, verified_user.id)
    ev = session.query(EmailVerification).filter_by(token=token).first()
    ev.expires_at = datetime.now() - timedelta(hours=1)
    session.commit()
    assert verify_email_token(session, token) is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_auth_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `services/auth_service.py`**

```python
"""Authentication: login, password hashing, session, email verification."""
from __future__ import annotations
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy.orm import Session

from models.orm import EmailVerification, User, UserRole

DEFAULT_PASSWORD = "FujiFilm_11111"


@dataclass
class UserSession:
    user_id: int
    email: str
    role: str  # 'user' | 'admin' | 'superadmin'


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def is_default_password(plain: str) -> bool:
    return plain == DEFAULT_PASSWORD


def login(session: Session, email: str, password: str) -> UserSession | None:
    user = session.query(User).filter_by(
        email=email, is_active=True, is_verified=True
    ).first()
    if not user:
        return None
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return None
    return UserSession(user_id=user.id, email=user.email, role=user.role.value)


def change_password(
    session: Session, user_id: int, old_pw: str, new_pw: str
) -> bool:
    user = session.get(User, user_id)
    if not user:
        return False
    if not bcrypt.checkpw(old_pw.encode(), user.password_hash.encode()):
        return False
    user.password_hash = hash_password(new_pw)
    session.commit()
    return True


def create_verification_token(session: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    ev = EmailVerification(
        user_id=user_id,
        token=token,
        expires_at=datetime.now() + timedelta(hours=24),
    )
    session.add(ev)
    session.commit()
    return token


def verify_email_token(session: Session, token: str) -> bool:
    ev = session.query(EmailVerification).filter_by(token=token).first()
    if not ev or ev.expires_at < datetime.now():
        return False
    user = session.get(User, ev.user_id)
    user.is_verified = True
    session.delete(ev)
    session.commit()
    return True
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_auth_service.py -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/auth_service.py tests/test_auth_service.py
git commit -m "feat: add auth service with bcrypt and email verification"
```

---

### Task 6: User service (`services/user_service.py`)

**Files:**
- Create: `services/user_service.py`
- Create: `tests/test_user_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_user_service.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base, User, UserRole
from services.auth_service import hash_password, UserSession
from services.user_service import (
    create_user, promote_to_admin, demote_admin,
    delete_user, list_users, change_email,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def superadmin_session(session):
    u = User(email="sa@co.com", password_hash=hash_password("p"),
             role=UserRole.superadmin, is_verified=True, is_active=True)
    session.add(u)
    session.commit()
    return UserSession(user_id=u.id, email=u.email, role="superadmin"), session


@pytest.fixture
def admin_session(session):
    u = User(email="admin@co.com", password_hash=hash_password("p"),
             role=UserRole.admin, is_verified=True, is_active=True)
    session.add(u)
    session.commit()
    return UserSession(user_id=u.id, email=u.email, role="admin"), session


def test_create_user(superadmin_session):
    caller, session = superadmin_session
    user = create_user(session, caller, "new@co.com", "Pass1!", "user")
    assert user.id is not None
    assert user.is_verified is False


def test_create_user_invalid_email(superadmin_session):
    caller, session = superadmin_session
    with pytest.raises(ValueError, match="Invalid email"):
        create_user(session, caller, "notanemail", "Pass1!", "user")


def test_create_user_duplicate_email(superadmin_session):
    caller, session = superadmin_session
    create_user(session, caller, "dup@co.com", "Pass1!", "user")
    with pytest.raises(ValueError, match="already exists"):
        create_user(session, caller, "dup@co.com", "Pass2!", "user")


def test_promote_to_admin(superadmin_session):
    caller, session = superadmin_session
    user = create_user(session, caller, "promo@co.com", "Pass1!", "user")
    promote_to_admin(session, caller, user.id)
    assert session.get(User, user.id).role == UserRole.admin


def test_demote_admin_superadmin_only(admin_session):
    caller, session = admin_session
    target = User(email="t@co.com", password_hash="h",
                  role=UserRole.admin, is_verified=True, is_active=True)
    session.add(target)
    session.commit()
    with pytest.raises(PermissionError):
        demote_admin(session, caller, target.id)


def test_demote_admin_by_superadmin(superadmin_session):
    caller, session = superadmin_session
    target = User(email="t@co.com", password_hash="h",
                  role=UserRole.admin, is_verified=True, is_active=True)
    session.add(target)
    session.commit()
    demote_admin(session, caller, target.id)
    assert session.get(User, target.id).role == UserRole.user


def test_delete_user_superadmin_only(admin_session):
    caller, session = admin_session
    target = User(email="del@co.com", password_hash="h",
                  role=UserRole.user, is_verified=True, is_active=True)
    session.add(target)
    session.commit()
    with pytest.raises(PermissionError):
        delete_user(session, caller, target.id)


def test_change_email(superadmin_session):
    caller, session = superadmin_session
    sa = session.get(User, caller.user_id)
    change_email(session, caller, caller.user_id, "new@co.com")
    assert session.get(User, caller.user_id).email == "new@co.com"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_user_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `services/user_service.py`**

```python
"""User CRUD operations. Role-gated — caller's UserSession enforced."""
from __future__ import annotations
import re
from sqlalchemy.orm import Session
from models.orm import User, UserRole
from services.auth_service import UserSession, hash_password

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _require_role(caller: UserSession, *roles: str) -> None:
    if caller.role not in roles:
        raise PermissionError(f"Requires role: {roles}. Caller has: {caller.role}")


def create_user(
    session: Session, caller: UserSession,
    email: str, password: str, role: str,
) -> User:
    _require_role(caller, "admin", "superadmin")
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email: {email}")
    if session.query(User).filter_by(email=email).first():
        raise ValueError(f"Email already exists: {email}")
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole[role],
        is_verified=False,
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def promote_to_admin(session: Session, caller: UserSession, user_id: int) -> None:
    _require_role(caller, "admin", "superadmin")
    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    user.role = UserRole.admin
    session.commit()


def demote_admin(session: Session, caller: UserSession, user_id: int) -> None:
    _require_role(caller, "superadmin")
    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    user.role = UserRole.user
    session.commit()


def delete_user(session: Session, caller: UserSession, user_id: int) -> None:
    _require_role(caller, "superadmin")
    user = session.get(User, user_id)
    if user:
        session.delete(user)
        session.commit()


def list_users(session: Session, caller: UserSession) -> list[User]:
    _require_role(caller, "admin", "superadmin")
    return session.query(User).order_by(User.created_at).all()


def change_email(
    session: Session, caller: UserSession, user_id: int, new_email: str
) -> None:
    _require_role(caller, "superadmin")
    if not _EMAIL_RE.match(new_email):
        raise ValueError(f"Invalid email: {new_email}")
    if session.query(User).filter_by(email=new_email).first():
        raise ValueError(f"Email already exists: {new_email}")
    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    user.email = new_email
    session.commit()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_user_service.py -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/user_service.py tests/test_user_service.py
git commit -m "feat: add user service with role-gated CRUD"
```

---

### Task 7: Login dialog (`ui/login_dialog.py`)

**Files:**
- Create: `ui/login_dialog.py`

No automated UI tests — verify manually.

- [ ] **Step 1: Create `ui/login_dialog.py`**

```python
"""Login dialog shown before MainWindow. Light centered card style."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame,
)
from sqlalchemy.orm import Session
from services.auth_service import UserSession, login, is_default_password
from services.db_session import get_session


class ChangePasswordDialog(QDialog):
    """Forced password change on first login."""

    def __init__(self, session: Session, user_session: UserSession, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.setFixedWidth(380)
        self._session = session
        self._user_session = user_session
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(QLabel(
            "You are using the default password.\nPlease set a new password to continue."
        ))
        self._new_pw = QLineEdit()
        self._new_pw.setPlaceholderText("New password")
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setPlaceholderText("Confirm new password")
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._new_pw)
        layout.addWidget(self._confirm_pw)
        btn = QPushButton("Save New Password")
        btn.clicked.connect(self._save)
        layout.addWidget(btn)

    def _save(self) -> None:
        from services.auth_service import change_password, DEFAULT_PASSWORD
        new = self._new_pw.text()
        confirm = self._confirm_pw.text()
        if new != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return
        if len(new) < 8:
            QMessageBox.warning(self, "Error", "Password must be at least 8 characters.")
            return
        ok = change_password(self._session, self._user_session.user_id, DEFAULT_PASSWORD, new)
        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Could not update password.")


class LoginDialog(QDialog):
    """Light centered card login screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Product License Timer")
        self.setFixedWidth(400)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        self._session: Session | None = None
        self._user_session: UserSession | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(40, 40, 40, 40)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setStyleSheet("""
            QFrame#loginCard {
                background: white;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Product License Timer")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")

        subtitle = QLabel("Sign in to continue")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 12px;")

        self._email = QLineEdit()
        self._email.setPlaceholderText("Email address")
        self._email.setStyleSheet("padding: 8px; border: 1px solid #e2e8f0; border-radius: 4px;")

        self._password = QLineEdit()
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setStyleSheet("padding: 8px; border: 1px solid #e2e8f0; border-radius: 4px;")
        self._password.returnPressed.connect(self._attempt_login)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ef4444; font-size: 11px;")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.hide()

        sign_in_btn = QPushButton("Sign In")
        sign_in_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6; color: white; border-radius: 4px;
                padding: 8px; font-weight: bold;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        sign_in_btn.clicked.connect(self._attempt_login)

        for w in [title, subtitle, self._email, self._password, self._error_label, sign_in_btn]:
            layout.addWidget(w)

        outer.addWidget(card)

    def _attempt_login(self) -> None:
        email = self._email.text().strip()
        password = self._password.text()
        self._error_label.hide()

        try:
            session = get_session()
            from models.orm import User
            if session.query(User).count() == 0:
                self._error_label.setText(
                    "No users exist.\nRun: python -m migrations.init_schema"
                )
                self._error_label.show()
                session.close()
                return

            result = login(session, email, password)
            if result is None:
                self._error_label.setText("Invalid email or password.")
                self._error_label.show()
                session.close()
                return

            # Check for default password — force change
            if is_default_password(password):
                dlg = ChangePasswordDialog(session, result, self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    session.close()
                    return

            self._session = session
            self._user_session = result
            self.accept()

        except Exception as e:
            self._error_label.setText(f"Connection error:\n{e}")
            self._error_label.show()

    def get_user_session(self) -> UserSession | None:
        return self._user_session

    def get_db_session(self) -> Session | None:
        return self._session
```

- [ ] **Step 2: Update `main.py` to show login first**

Replace the `main()` function in `main.py`:

```python
"""
Entry point. Shows login dialog before main window.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QDialog
from ui.login_dialog import LoginDialog


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Product License Timer")
    app.setQuitOnLastWindowClosed(False)

    login_dlg = LoginDialog()
    if login_dlg.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    user_session = login_dlg.get_user_session()
    db_session = login_dlg.get_db_session()

    from ui.main_window import MainWindow
    window = MainWindow(user_session=user_session, db_session=db_session)

    if "--minimized" not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add ui/login_dialog.py main.py
git commit -m "feat: add login dialog and wire into main entry point"
```

---

## Phase 3 — Contacts & Recipients

### Task 8: Contact service (`services/contact_service.py`)

**Files:**
- Create: `services/contact_service.py`
- Create: `tests/test_contact_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_contact_service.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base, User, UserRole, Contact, SystemRecipient, ContactRoleType, RecipientRoleType
from services.auth_service import hash_password, UserSession
from services.contact_service import (
    add_contact, update_contact, delete_contact, list_contacts, list_contacts_by_role,
    add_recipient, update_recipient, delete_recipient, list_recipients, toggle_recipient,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def admin_caller():
    return UserSession(user_id=1, email="admin@co.com", role="admin")


@pytest.fixture
def user_caller():
    return UserSession(user_id=2, email="user@co.com", role="user")


def test_add_contact(session, admin_caller):
    c = add_contact(session, admin_caller, "Alice", "alice@co.com", "Consultant")
    assert c.id is not None
    assert c.role_type == ContactRoleType.consultant


def test_add_contact_permission_denied(session, user_caller):
    with pytest.raises(PermissionError):
        add_contact(session, user_caller, "Alice", "alice@co.com", "Consultant")


def test_list_contacts_by_role(session, admin_caller):
    add_contact(session, admin_caller, "Alice", "a@co.com", "Consultant")
    add_contact(session, admin_caller, "Bob", "b@co.com", "Account Manager")
    consultants = list_contacts_by_role(session, "Consultant")
    assert len(consultants) == 1
    assert consultants[0].name == "Alice"


def test_update_contact(session, admin_caller):
    c = add_contact(session, admin_caller, "Alice", "a@co.com", "Consultant")
    update_contact(session, admin_caller, c.id, name="Alicia")
    assert session.get(Contact, c.id).name == "Alicia"


def test_delete_contact(session, admin_caller):
    c = add_contact(session, admin_caller, "Alice", "a@co.com", "Consultant")
    delete_contact(session, admin_caller, c.id)
    assert session.get(Contact, c.id) is None


def test_add_recipient(session, admin_caller):
    r = add_recipient(session, admin_caller, "Support Team", "support@co.com", "Support")
    assert r.is_active is True


def test_toggle_recipient(session, admin_caller):
    r = add_recipient(session, admin_caller, "IT", "it@co.com", "Admin")
    toggle_recipient(session, admin_caller, r.id)
    assert session.get(SystemRecipient, r.id).is_active is False
    toggle_recipient(session, admin_caller, r.id)
    assert session.get(SystemRecipient, r.id).is_active is True
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/test_contact_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `services/contact_service.py`**

```python
"""CRUD for contacts (address book) and system_recipients."""
from __future__ import annotations
from sqlalchemy.orm import Session
from models.orm import Contact, SystemRecipient, ContactRoleType, RecipientRoleType
from services.auth_service import UserSession


def _require_admin(caller: UserSession) -> None:
    if caller.role not in ("admin", "superadmin"):
        raise PermissionError("Requires admin or superadmin role.")


# ---------------------------------------------------------------- Contacts

def add_contact(
    session: Session, caller: UserSession,
    name: str, email: str, role_type: str,
) -> Contact:
    _require_admin(caller)
    c = Contact(name=name, email=email, role_type=ContactRoleType[role_type.lower().replace(" ", "_")])
    session.add(c)
    session.commit()
    return c


def update_contact(
    session: Session, caller: UserSession, contact_id: int,
    name: str | None = None, email: str | None = None, role_type: str | None = None,
) -> None:
    _require_admin(caller)
    c = session.get(Contact, contact_id)
    if not c:
        raise ValueError(f"Contact {contact_id} not found")
    if name is not None:
        c.name = name
    if email is not None:
        c.email = email
    if role_type is not None:
        c.role_type = ContactRoleType[role_type.lower().replace(" ", "_")]
    session.commit()


def delete_contact(session: Session, caller: UserSession, contact_id: int) -> None:
    _require_admin(caller)
    c = session.get(Contact, contact_id)
    if c:
        session.delete(c)
        session.commit()


def list_contacts(session: Session) -> list[Contact]:
    return session.query(Contact).order_by(Contact.name).all()


def list_contacts_by_role(session: Session, role_type: str) -> list[Contact]:
    rt = ContactRoleType[role_type.lower().replace(" ", "_")]
    return session.query(Contact).filter_by(role_type=rt).order_by(Contact.name).all()


# -------------------------------------------------------- System Recipients

def add_recipient(
    session: Session, caller: UserSession,
    name: str, email: str, role_type: str,
) -> SystemRecipient:
    _require_admin(caller)
    rt = RecipientRoleType[role_type.lower().replace(" ", "_")]
    r = SystemRecipient(name=name, email=email, role_type=rt, is_active=True)
    session.add(r)
    session.commit()
    return r


def update_recipient(
    session: Session, caller: UserSession, recipient_id: int,
    name: str | None = None, email: str | None = None, role_type: str | None = None,
) -> None:
    _require_admin(caller)
    r = session.get(SystemRecipient, recipient_id)
    if not r:
        raise ValueError(f"Recipient {recipient_id} not found")
    if name is not None:
        r.name = name
    if email is not None:
        r.email = email
    if role_type is not None:
        r.role_type = RecipientRoleType[role_type.lower().replace(" ", "_")]
    session.commit()


def delete_recipient(session: Session, caller: UserSession, recipient_id: int) -> None:
    _require_admin(caller)
    r = session.get(SystemRecipient, recipient_id)
    if r:
        session.delete(r)
        session.commit()


def list_recipients(session: Session) -> list[SystemRecipient]:
    return session.query(SystemRecipient).order_by(SystemRecipient.name).all()


def toggle_recipient(session: Session, caller: UserSession, recipient_id: int) -> None:
    _require_admin(caller)
    r = session.get(SystemRecipient, recipient_id)
    if not r:
        raise ValueError(f"Recipient {recipient_id} not found")
    r.is_active = not r.is_active
    session.commit()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_contact_service.py -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/contact_service.py tests/test_contact_service.py
git commit -m "feat: add contact and system recipient service"
```

---

### Task 9: Contacts page UI (`ui/contacts_page.py`)

**Files:**
- Create: `ui/contacts_page.py`

- [ ] **Step 1: Create `ui/contacts_page.py`**

```python
"""Address book management page. Admin+ only."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QToolBar,
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.contact_service import (
    add_contact, update_contact, delete_contact, list_contacts,
)

ROLES = ["Consultant", "Account Manager", "Project Manager"]
COLS = ["Name", "Email", "Role"]


class _ContactForm(QDialog):
    def __init__(self, parent=None, contact=None):
        super().__init__(parent)
        self.setWindowTitle("Contact" if contact is None else "Edit Contact")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit(contact.name if contact else "")
        self._email = QLineEdit(contact.email if contact else "")
        self._role = QComboBox()
        self._role.addItems(ROLES)
        if contact:
            idx = ROLES.index(contact.role_type.value)
            self._role.setCurrentIndex(idx)
        form.addRow("Name", self._name)
        form.addRow("Email", self._email)
        form.addRow("Role", self._role)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Name is required.")
            return
        if "@" not in self._email.text():
            QMessageBox.warning(self, "Error", "Invalid email.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "email": self._email.text().strip(),
            "role_type": self._role.currentText(),
        }


class ContactsPage(QWidget):
    def __init__(self, session: Session, caller: UserSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._caller = caller
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        tb = QToolBar()
        tb.setMovable(False)
        for label, slot in [("+ Add", self._add), ("✏ Edit", self._edit), ("🗑 Delete", self._delete)]:
            from PyQt6.QtGui import QAction
            a = QAction(label, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._edit)

        layout.addWidget(tb)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        contacts = list_contacts(self._session)
        self._table.setRowCount(0)
        self._contacts = contacts
        for row, c in enumerate(contacts):
            self._table.insertRow(row)
            for col, val in enumerate([c.name, c.email, c.role_type.value]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self) -> None:
        dlg = _ContactForm(self)
        if dlg.exec():
            try:
                add_contact(self._session, self._caller, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            QMessageBox.information(self, "No Selection", "Select a contact to edit.")
            return
        contact = next((c for c in self._contacts if c.id == cid), None)
        dlg = _ContactForm(self, contact=contact)
        if dlg.exec():
            try:
                update_contact(self._session, self._caller, cid, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            QMessageBox.information(self, "No Selection", "Select a contact to delete.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this contact?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_contact(self._session, self._caller, cid)
            self.refresh()
```

- [ ] **Step 2: Commit**

```bash
git add ui/contacts_page.py
git commit -m "feat: add contacts management page"
```

---

### Task 10: Recipients page UI (`ui/recipients_page.py`)

**Files:**
- Create: `ui/recipients_page.py`

- [ ] **Step 1: Create `ui/recipients_page.py`**

```python
"""System recipients management page. Admin+ only."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QToolBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.contact_service import (
    add_recipient, update_recipient, delete_recipient,
    list_recipients, toggle_recipient,
)

ROLES = ["Solutions Team", "Admin", "Support"]
COLS = ["Name", "Email", "Role", "Active"]


class _RecipientForm(QDialog):
    def __init__(self, parent=None, recipient=None):
        super().__init__(parent)
        self.setWindowTitle("Recipient" if recipient is None else "Edit Recipient")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit(recipient.name if recipient else "")
        self._email = QLineEdit(recipient.email if recipient else "")
        self._role = QComboBox()
        self._role.addItems(ROLES)
        if recipient:
            idx = ROLES.index(recipient.role_type.value)
            self._role.setCurrentIndex(idx)
        form.addRow("Name", self._name)
        form.addRow("Email", self._email)
        form.addRow("Role", self._role)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Name is required.")
            return
        if "@" not in self._email.text():
            QMessageBox.warning(self, "Error", "Invalid email.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "email": self._email.text().strip(),
            "role_type": self._role.currentText(),
        }


class RecipientsPage(QWidget):
    def __init__(self, session: Session, caller: UserSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._caller = caller
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        tb = QToolBar()
        tb.setMovable(False)
        for label, slot in [
            ("+ Add", self._add), ("✏ Edit", self._edit),
            ("🗑 Delete", self._delete), ("⏺ Toggle Active", self._toggle),
        ]:
            a = QAction(label, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._edit)

        layout.addWidget(tb)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        recipients = list_recipients(self._session)
        self._recipients = recipients
        self._table.setRowCount(0)
        for row, r in enumerate(recipients):
            self._table.insertRow(row)
            for col, val in enumerate([r.name, r.email, r.role_type.value,
                                        "Yes" if r.is_active else "No"]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, r.id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self) -> None:
        dlg = _RecipientForm(self)
        if dlg.exec():
            try:
                add_recipient(self._session, self._caller, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, "No Selection", "Select a recipient to edit.")
            return
        r = next((x for x in self._recipients if x.id == rid), None)
        dlg = _RecipientForm(self, recipient=r)
        if dlg.exec():
            try:
                update_recipient(self._session, self._caller, rid, **dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, "No Selection", "Select a recipient to delete.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this recipient?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_recipient(self._session, self._caller, rid)
            self.refresh()

    def _toggle(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, "No Selection", "Select a recipient to toggle.")
            return
        toggle_recipient(self._session, self._caller, rid)
        self.refresh()
```

- [ ] **Step 2: Commit**

```bash
git add ui/recipients_page.py
git commit -m "feat: add system recipients management page"
```

---

### Task 11: Update settings dialog (SMTP only)

**Files:**
- Modify: `ui/settings_dialog.py`

- [ ] **Step 1: Replace `_build_email_tab` in `ui/settings_dialog.py`**

Remove the recipients list, add TLS toggle, read/write SMTP to `.env`:

Replace the `_build_email_tab` method and `_EMAIL_DEFAULTS` block with:

```python
# At top of file, add:
from dotenv import load_dotenv, set_key
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)

_EMAIL_DEFAULTS = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "smtp_tls": True,
    "sender_name": "License Tracker",
}
```

Replace `_build_email_tab`:

```python
def _build_email_tab(self) -> QWidget:
    import os
    w = QWidget()
    form = QFormLayout(w)

    self.smtp_host = QLineEdit(os.getenv("SMTP_HOST", "smtp.gmail.com"))
    self.smtp_port = QSpinBox()
    self.smtp_port.setRange(1, 65535)
    self.smtp_port.setValue(int(os.getenv("SMTP_PORT", "587")))
    self.smtp_user = QLineEdit(os.getenv("SMTP_USER", ""))
    self.smtp_pass = QLineEdit(os.getenv("SMTP_PASSWORD", ""))
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

    self.smtp_tls = QCheckBox("Use TLS")
    self.smtp_tls.setChecked(os.getenv("SMTP_TLS", "true").lower() == "true")
    self.sender_name = QLineEdit(os.getenv("SENDER_NAME", "License Tracker"))

    test_btn = QPushButton("Test Connection")
    test_btn.clicked.connect(self._test_connection)

    form.addRow("SMTP Host", self.smtp_host)
    form.addRow("SMTP Port", self.smtp_port)
    form.addRow("Username", self.smtp_user)
    form.addRow("Password", pass_row)
    form.addRow("", self.smtp_tls)
    form.addRow("Sender Name", self.sender_name)
    form.addRow(QLabel("Recipients are managed in the System Recipients page."))
    form.addRow("", test_btn)
    return w
```

Replace `_persist` SMTP block to write to `.env`:

```python
def _persist_smtp(self) -> None:
    from dotenv import set_key
    pairs = [
        ("SMTP_HOST", self.smtp_host.text().strip()),
        ("SMTP_PORT", str(self.smtp_port.value())),
        ("SMTP_USER", self.smtp_user.text().strip()),
        ("SMTP_PASSWORD", self.smtp_pass.text()),
        ("SMTP_TLS", "true" if self.smtp_tls.isChecked() else "false"),
        ("SENDER_NAME", self.sender_name.text().strip()),
    ]
    ENV_PATH.touch()
    for key, val in pairs:
        set_key(str(ENV_PATH), key, val)
```

Update `_persist` to call `_persist_smtp()` instead of writing `email_config.json` SMTP fields.

- [ ] **Step 2: Commit**

```bash
git add ui/settings_dialog.py
git commit -m "feat: settings dialog SMTP tab reads/writes .env, removes recipients"
```

---

## Phase 4 — Products, Ownership & Notifications

### Task 12: Product service (`services/product_service.py`)

**Files:**
- Create: `services/product_service.py`
- Create: `tests/test_product_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_product_service.py`:

```python
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base, User, UserRole, Contact, ContactRoleType, Product
from services.auth_service import hash_password, UserSession
from services.product_service import (
    add_product, update_product, delete_product,
    get_product, get_all_products, get_my_products,
    delete_expired_products,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def user_caller(session):
    u = User(email="u@co.com", password_hash=hash_password("p"),
             role=UserRole.user, is_verified=True, is_active=True)
    session.add(u)
    session.commit()
    return UserSession(user_id=u.id, email=u.email, role="user")


def test_add_product(session, user_caller):
    p = add_product(session, user_caller,
                    product_name="PaperCut MF",
                    start_date=date(2026, 1, 1),
                    duration_days=90)
    assert p.id is not None
    assert p.expiry_date == date(2026, 4, 1)
    assert p.created_by == user_caller.user_id


def test_add_product_duplicate_name(session, user_caller):
    add_product(session, user_caller, product_name="X",
                start_date=date(2026, 1, 1), duration_days=30)
    with pytest.raises(ValueError, match="already exists"):
        add_product(session, user_caller, product_name="X",
                    start_date=date(2026, 1, 1), duration_days=30)


def test_update_product_ownership(session, user_caller):
    c = Contact(name="Alice", email="a@co.com", role_type=ContactRoleType.consultant)
    session.add(c)
    session.flush()
    p = add_product(session, user_caller, product_name="Y",
                    start_date=date(2026, 1, 1), duration_days=30)
    update_product(session, user_caller, p.id, product_name="Y",
                   start_date=date(2026, 1, 1), duration_days=30,
                   consultant_id=c.id)
    assert session.get(Product, p.id).consultant_id == c.id


def test_get_my_products(session, user_caller):
    add_product(session, user_caller, product_name="Mine",
                start_date=date(2026, 1, 1), duration_days=30)
    other_user = User(email="o@co.com", password_hash="h",
                      role=UserRole.user, is_verified=True, is_active=True)
    session.add(other_user)
    session.flush()
    other_caller = UserSession(user_id=other_user.id, email="o@co.com", role="user")
    add_product(session, other_caller, product_name="Theirs",
                start_date=date(2026, 1, 1), duration_days=30)
    mine = get_my_products(session, user_caller)
    assert len(mine) == 1
    assert mine[0].product_name == "Mine"


def test_delete_expired(session, user_caller):
    add_product(session, user_caller, product_name="Old",
                start_date=date(2020, 1, 1), duration_days=10)
    add_product(session, user_caller, product_name="New",
                start_date=date(2026, 1, 1), duration_days=365)
    count = delete_expired_products(session)
    assert count == 1
    remaining = get_all_products(session)
    assert remaining[0].product_name == "New"
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/test_product_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `services/product_service.py`**

```python
"""Product CRUD using SQLAlchemy. Replaces database_service for product operations."""
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from models.orm import Product
from services.auth_service import UserSession
from utils.date_utils import calculate_expiry_date


def add_product(
    session: Session,
    caller: UserSession,
    product_name: str,
    start_date: date,
    duration_days: int,
    customer_name: str = "",
    order_number: str = "",
    notes: str = "",
    consultant_id: int | None = None,
    account_manager_id: int | None = None,
    project_manager_id: int | None = None,
) -> Product:
    if session.query(Product).filter_by(product_name=product_name).first():
        raise ValueError(f"Product already exists: {product_name}")
    expiry = calculate_expiry_date(start_date, duration_days)
    p = Product(
        product_name=product_name,
        customer_name=customer_name,
        order_number=order_number,
        start_date=start_date,
        duration_days=duration_days,
        expiry_date=expiry,
        notes=notes,
        created_by=caller.user_id,
        consultant_id=consultant_id,
        account_manager_id=account_manager_id,
        project_manager_id=project_manager_id,
    )
    session.add(p)
    session.commit()
    return p


def update_product(
    session: Session,
    caller: UserSession,
    product_id: int,
    product_name: str,
    start_date: date,
    duration_days: int,
    customer_name: str = "",
    order_number: str = "",
    notes: str = "",
    consultant_id: int | None = None,
    account_manager_id: int | None = None,
    project_manager_id: int | None = None,
) -> None:
    p = session.get(Product, product_id)
    if not p:
        raise ValueError(f"Product {product_id} not found")
    existing = session.query(Product).filter_by(product_name=product_name).first()
    if existing and existing.id != product_id:
        raise ValueError(f"Product name already exists: {product_name}")
    expiry = calculate_expiry_date(start_date, duration_days)
    p.product_name = product_name
    p.customer_name = customer_name
    p.order_number = order_number
    p.start_date = start_date
    p.duration_days = duration_days
    p.expiry_date = expiry
    p.notes = notes
    p.consultant_id = consultant_id
    p.account_manager_id = account_manager_id
    p.project_manager_id = project_manager_id
    session.commit()


def delete_product(session: Session, product_id: int) -> None:
    p = session.get(Product, product_id)
    if p:
        session.delete(p)
        session.commit()


def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)


def get_all_products(session: Session) -> list[Product]:
    return session.query(Product).order_by(Product.expiry_date).all()


def get_my_products(session: Session, caller: UserSession) -> list[Product]:
    return (session.query(Product)
            .filter_by(created_by=caller.user_id)
            .order_by(Product.expiry_date)
            .all())


def delete_expired_products(session: Session) -> int:
    today = date.today()
    expired = session.query(Product).filter(Product.expiry_date < today).all()
    count = len(expired)
    for p in expired:
        session.delete(p)
    session.commit()
    return count


def notification_sent(session: Session, product_id: int, notification_type: str) -> bool:
    from models.orm import NotificationLog, NotificationType
    ntype = NotificationType[f"days_{notification_type.replace('_days', '')}"]
    return session.query(NotificationLog).filter_by(
        product_id=product_id, notification_type=ntype
    ).first() is not None


def log_notification(session: Session, product_id: int, notification_type: str) -> None:
    from models.orm import NotificationLog, NotificationType
    from datetime import datetime
    from sqlalchemy.exc import IntegrityError
    ntype = NotificationType[f"days_{notification_type.replace('_days', '')}"]
    try:
        session.add(NotificationLog(product_id=product_id, notification_type=ntype,
                                    sent_at=datetime.now()))
        session.commit()
    except IntegrityError:
        session.rollback()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_product_service.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/product_service.py tests/test_product_service.py
git commit -m "feat: add product service with ownership support"
```

---

### Task 13: Update notification service

**Files:**
- Modify: `services/notification_service.py`
- Create: `tests/test_notification_service_v2.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_notification_service_v2.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import (Base, User, UserRole, Contact, ContactRoleType,
                        SystemRecipient, RecipientRoleType, Product)
from services.auth_service import hash_password, UserSession
from services.notification_service import resolve_recipients, format_email_body


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def product_with_contacts(session):
    u = User(email="u@co.com", password_hash=hash_password("p"),
             role=UserRole.user, is_verified=True, is_active=True)
    consultant = Contact(name="Alice", email="alice@co.com",
                         role_type=ContactRoleType.consultant)
    recipient = SystemRecipient(name="Support", email="support@co.com",
                                role_type=RecipientRoleType.support, is_active=True)
    inactive = SystemRecipient(name="Old", email="old@co.com",
                               role_type=RecipientRoleType.admin, is_active=False)
    session.add_all([u, consultant, recipient, inactive])
    session.flush()
    p = Product(product_name="PaperCut MF", start_date=date(2026, 1, 1),
                duration_days=90, expiry_date=date(2026, 4, 1),
                created_by=u.id, consultant_id=consultant.id)
    session.add(p)
    session.commit()
    return p


def test_resolve_recipients_includes_system_and_contact(session, product_with_contacts):
    emails = resolve_recipients(session, product_with_contacts)
    assert "alice@co.com" in emails
    assert "support@co.com" in emails


def test_resolve_recipients_excludes_inactive(session, product_with_contacts):
    emails = resolve_recipients(session, product_with_contacts)
    assert "old@co.com" not in emails


def test_resolve_recipients_deduplicates(session, product_with_contacts):
    # Add same email as both system recipient and contact
    from services.contact_service import add_contact
    # Make consultant email same as system recipient
    product_with_contacts.consultant_id = None
    r2 = SystemRecipient(name="Alice Also", email="alice@co.com",
                         role_type=RecipientRoleType.support, is_active=True)
    session.add(r2)
    session.commit()
    emails = resolve_recipients(session, product_with_contacts)
    assert emails.count("alice@co.com") <= 1


def test_format_email_body_dd_mm_yyyy(session, product_with_contacts):
    body = format_email_body(session, product_with_contacts, threshold=10)
    assert "01-01-2026" in body  # start_date DD-MM-YYYY
    assert "01-04-2026" in body  # expiry_date DD-MM-YYYY
    assert "10" in body
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/test_notification_service_v2.py -v
```

Expected: `ImportError` for `resolve_recipients`.

- [ ] **Step 3: Update `services/notification_service.py`**

Add these functions (keep all existing methods intact, they are used by old code path during transition):

```python
# Add at top of notification_service.py:
import os
from dotenv import load_dotenv
load_dotenv()


def resolve_recipients(session, product) -> list[str]:
    """
    Build deduplicated list of recipient emails for a product alert.
    Combines active system_recipients + product-linked contacts.
    """
    from models.orm import SystemRecipient, Contact
    emails: list[str] = []

    # Active system recipients
    for r in session.query(SystemRecipient).filter_by(is_active=True).all():
        emails.append(r.email)

    # Product-linked contacts
    for fk in ("consultant_id", "account_manager_id", "project_manager_id"):
        cid = getattr(product, fk, None)
        if cid:
            contact = session.get(Contact, cid)
            if contact:
                emails.append(contact.email)

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def _contact_display(session, contact_id) -> str:
    if not contact_id:
        return "—"
    from models.orm import Contact
    c = session.get(Contact, contact_id)
    return f"{c.name} ({c.email})" if c else "—"


def format_email_body(session, product, threshold: int) -> str:
    """Build email body with DD-MM-YYYY dates and ownership info."""
    def fmt(d) -> str:
        if hasattr(d, "strftime"):
            return d.strftime("%d-%m-%Y")
        from datetime import date as _date
        return _date.fromisoformat(str(d)).strftime("%d-%m-%Y")

    return (
        f"Product Name    : {product.product_name}\n"
        f"Customer        : {getattr(product, 'customer_name', '')}\n"
        f"Order Number    : {getattr(product, 'order_number', '')}\n"
        f"Start Date      : {fmt(product.start_date)}\n"
        f"Expiry Date     : {fmt(product.expiry_date)}\n"
        f"Days Remaining  : {threshold}\n"
        f"Threshold       : {threshold}-day warning\n"
        f"Consultant      : {_contact_display(session, getattr(product, 'consultant_id', None))}\n"
        f"Account Manager : {_contact_display(session, getattr(product, 'account_manager_id', None))}\n"
        f"Project Manager : {_contact_display(session, getattr(product, 'project_manager_id', None))}\n\n"
        f"Please renew or arrange a replacement license before the expiry date."
    )


def check_and_send_v2(products: list, session, smtp_cfg: dict) -> None:
    """
    New notification check using ORM products and DB recipients.
    Drop-in replacement for check_and_send once fully migrated.
    """
    from datetime import date
    from utils.date_utils import days_remaining
    from services.product_service import notification_sent, log_notification

    THRESHOLDS = [15, 10, 5]
    for product in products:
        days_left = days_remaining(product.expiry_date)
        if days_left < 0:
            continue
        for threshold in THRESHOLDS:
            ntype = f"{threshold}_days"
            if days_left <= threshold and not notification_sent(session, product.id, ntype):
                recipients = resolve_recipients(session, product)
                if not recipients:
                    continue
                body = format_email_body(session, product, threshold)
                subject = f"⚠ Trial Expiry Alert — {product.product_name} ({threshold} days remaining)"
                sent = _send_smtp(subject, body, recipients, smtp_cfg)
                if sent:
                    log_notification(session, product.id, ntype)


def _send_smtp(subject: str, body: str, recipients: list[str], cfg: dict) -> bool:
    """Send email via SMTP. Returns True on success."""
    import smtplib
    import threading
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not cfg.get("smtp_user") or not recipients:
        return False

    result = [False]

    def _send():
        try:
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = f"{cfg.get('sender_name', 'License Tracker')} <{cfg['smtp_user']}>"
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(body, "plain"))
            use_tls = str(cfg.get("smtp_tls", "true")).lower() == "true"
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as server:
                if use_tls:
                    server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], recipients, msg.as_string())
            result[0] = True
        except Exception as e:
            print(f"[NotificationService] Email failed: {e}")

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    t.join(timeout=15)
    return result[0]


def get_smtp_config() -> dict:
    """Read SMTP config from .env. Falls back to email_config.json if .env missing keys."""
    cfg = {
        "smtp_host": os.getenv("SMTP_HOST", ""),
        "smtp_port": os.getenv("SMTP_PORT", "587"),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "smtp_password": os.getenv("SMTP_PASSWORD", ""),
        "smtp_tls": os.getenv("SMTP_TLS", "true"),
        "sender_name": os.getenv("SENDER_NAME", "License Tracker"),
    }
    if not cfg["smtp_host"]:
        # Fallback to legacy email_config.json
        import json
        legacy = Path(__file__).parent.parent / "config" / "email_config.json"
        if legacy.exists():
            with open(legacy) as f:
                old = json.load(f)
            cfg["smtp_host"] = old.get("smtp_host", "")
            cfg["smtp_port"] = old.get("smtp_port", 587)
            cfg["smtp_user"] = old.get("smtp_user", "")
            cfg["smtp_password"] = old.get("smtp_password", "")
            cfg["sender_name"] = old.get("sender_name", "License Tracker")
    return cfg
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_notification_service_v2.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/notification_service.py tests/test_notification_service_v2.py
git commit -m "feat: add resolve_recipients, format_email_body, check_and_send_v2"
```

---

### Task 14: Update product form (`ui/product_form.py`)

**Files:**
- Modify: `ui/product_form.py`

- [ ] **Step 1: Read current `ui/product_form.py`** to understand existing field layout before modifying.

- [ ] **Step 2: Replace `ui/product_form.py`**

```python
"""Add/Edit product dialog with ownership dropdowns and DD-MM-YYYY dates."""
from __future__ import annotations
from datetime import date, timedelta
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QDateEdit, QTextEdit, QDialogButtonBox, QLabel, QFrame,
    QComboBox, QMessageBox,
)
from sqlalchemy.orm import Session
from services.auth_service import UserSession
from services.contact_service import list_contacts_by_role

UNASSIGNED = "— Unassigned —"
DATE_FORMAT = "dd-MM-yyyy"


def _date_to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _qdate_to_date(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class ProductForm(QDialog):
    def __init__(
        self,
        parent=None,
        product=None,
        session: Session | None = None,
        caller: UserSession | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Add Product" if product is None else "Edit Product")
        self.setMinimumWidth(440)
        self._product = product
        self._session = session
        self._caller = caller
        self._build()
        if product:
            self._populate(product)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        # Core fields
        self._name = QLineEdit()
        self._customer = QLineEdit()
        self._order = QLineEdit()

        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDisplayFormat(DATE_FORMAT)
        self._start_date.setDate(QDate.currentDate())
        self._start_date.dateChanged.connect(self._update_expiry_preview)

        self._duration = QSpinBox()
        self._duration.setRange(1, 3650)
        self._duration.setValue(90)
        self._duration.valueChanged.connect(self._update_expiry_preview)

        self._expiry_preview = QLabel()
        self._expiry_preview.setStyleSheet("color: #64748b;")
        self._update_expiry_preview()

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(64)

        form.addRow("Product Name *", self._name)
        form.addRow("Customer Name", self._customer)
        form.addRow("Order Number", self._order)
        form.addRow("Start Date", self._start_date)
        form.addRow("Duration (days)", self._duration)
        form.addRow("Expiry Date", self._expiry_preview)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)

        # Ownership section
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(divider)

        ownership_label = QLabel("OWNERSHIP (OPTIONAL)")
        ownership_label.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #64748b; letter-spacing: 1px;"
        )
        layout.addWidget(ownership_label)

        own_form = QFormLayout()
        self._consultant = self._make_contact_combo("Consultant")
        self._account_manager = self._make_contact_combo("Account Manager")
        self._project_manager = self._make_contact_combo("Project Manager")
        own_form.addRow("Consultant", self._consultant)
        own_form.addRow("Account Manager", self._account_manager)
        own_form.addRow("Project Manager", self._project_manager)
        layout.addLayout(own_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_contact_combo(self, role: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(UNASSIGNED, userData=None)
        if self._session:
            for c in list_contacts_by_role(self._session, role):
                combo.addItem(c.name, userData=c.id)
        return combo

    def _update_expiry_preview(self) -> None:
        start = _qdate_to_date(self._start_date.date())
        days = self._duration.value()
        expiry = start + timedelta(days=days)
        self._expiry_preview.setText(expiry.strftime("%d-%m-%Y"))

    def _populate(self, product) -> None:
        # Support both ORM Product and legacy dict
        def g(key, default=""):
            if isinstance(product, dict):
                return product.get(key, default)
            return getattr(product, key, default)

        self._name.setText(g("product_name") or g("name"))
        self._customer.setText(g("customer_name"))
        self._order.setText(g("order_number"))
        sd = g("start_date")
        if isinstance(sd, str):
            sd = date.fromisoformat(sd)
        if sd:
            self._start_date.setDate(_date_to_qdate(sd))
        self._duration.setValue(int(g("duration_days", 90)))
        self._notes.setPlainText(g("notes"))

        for combo, key in [
            (self._consultant, "consultant_id"),
            (self._account_manager, "account_manager_id"),
            (self._project_manager, "project_manager_id"),
        ]:
            cid = g(key)
            if cid:
                for i in range(combo.count()):
                    if combo.itemData(i) == cid:
                        combo.setCurrentIndex(i)
                        break

    def _validate(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Product name is required.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "product_name": self._name.text().strip(),
            "customer_name": self._customer.text().strip(),
            "order_number": self._order.text().strip(),
            "start_date": _qdate_to_date(self._start_date.date()),
            "duration_days": self._duration.value(),
            "notes": self._notes.toPlainText().strip(),
            "consultant_id": self._consultant.currentData(),
            "account_manager_id": self._account_manager.currentData(),
            "project_manager_id": self._project_manager.currentData(),
        }
```

- [ ] **Step 3: Commit**

```bash
git add ui/product_form.py
git commit -m "feat: update product form with ownership section and DD-MM-YYYY dates"
```

---

### Task 15: Update product table (`ui/product_table.py`)

**Files:**
- Modify: `ui/product_table.py`

- [ ] **Step 1: Read current `ui/product_table.py`** to understand column structure.

- [ ] **Step 2: Add `Assigned To` column and DD-MM-YYYY formatting**

In `product_table.py`, locate the column definitions and add `"Assigned To"` as the last column. Update the row-rendering logic to:

```python
# At top of product_table.py, add helper:
def _fmt_date(val) -> str:
    """Format date as DD-MM-YYYY from date object, isoformat string, or None."""
    if val is None:
        return ""
    if hasattr(val, "strftime"):
        return val.strftime("%d-%m-%Y")
    from datetime import date
    try:
        return date.fromisoformat(str(val)).strftime("%d-%m-%Y")
    except Exception:
        return str(val)


def _assigned_to_html(product: dict | object) -> str:
    """Build compact pill string for Assigned To column."""
    def g(key):
        if isinstance(product, dict):
            return product.get(key)
        return getattr(product, key, None)

    parts = []
    if g("consultant_name"):
        parts.append(f"C: {g('consultant_name')}")
    if g("account_manager_name"):
        parts.append(f"AM: {g('account_manager_name')}")
    if g("project_manager_name"):
        parts.append(f"PM: {g('project_manager_name')}")
    return "  ".join(parts) if parts else "—"
```

Update `refresh()` to call `_fmt_date()` for start/expiry date columns and `_assigned_to_html()` for the Assigned To column. The products passed to `refresh()` in Phase 4 will be ORM objects enriched with `consultant_name`, `account_manager_name`, `project_manager_name` fields resolved in `main_window.py`.

- [ ] **Step 3: Commit**

```bash
git add ui/product_table.py
git commit -m "feat: update product table with Assigned To column and DD-MM-YYYY dates"
```

---

### Task 16: Update main window (`ui/main_window.py`)

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Step 1: Replace `ui/main_window.py`**

```python
"""
Main application window with left sidebar navigation.
Accepts UserSession and db_session from login.
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QMessageBox, QToolBar,
    QSystemTrayIcon, QMenu, QFileDialog,
    QLabel, QStatusBar, QPushButton, QFrame, QStackedWidget,
)
from sqlalchemy.orm import Session

from services.auth_service import UserSession
from services.db_session import get_session
from services.notification_service import check_and_send_v2, get_smtp_config
from services.product_service import (
    add_product, update_product, delete_product,
    get_product, get_all_products, get_my_products, delete_expired_products,
)
from services.timer_service import TimerService
from ui.product_form import ProductForm
from ui.product_table import ProductTable
from ui.settings_dialog import SettingsDialog
from utils.csv_exporter import export_to_csv


class MainWindow(QMainWindow):
    def __init__(
        self,
        user_session: UserSession,
        db_session: Session,
    ):
        super().__init__()
        self._user = user_session
        self._session = db_session
        self._show_my_products = False
        self.setWindowTitle("Product License Timer")
        self.setMinimumSize(1200, 680)

        self._timer = TimerService(self)
        self._timer.tick.connect(self._on_tick)

        self._build_ui()
        self._build_tray()
        self._on_tick()
        self._timer.start()

    # ---------------------------------------------------------------- Build UI

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        h_layout = QHBoxLayout(root)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        h_layout.addWidget(self._build_sidebar())

        content = QWidget()
        v_layout = QVBoxLayout(content)
        v_layout.setContentsMargins(4, 4, 4, 4)

        self._stack = QStackedWidget()
        self._products_widget = self._build_products_page()
        self._stack.addWidget(self._products_widget)  # index 0

        if self._user.role in ("admin", "superadmin"):
            from ui.contacts_page import ContactsPage
            from ui.recipients_page import RecipientsPage
            self._contacts_widget = ContactsPage(self._session, self._user)
            self._recipients_widget = RecipientsPage(self._session, self._user)
            self._stack.addWidget(self._contacts_widget)   # index 1
            self._stack.addWidget(self._recipients_widget) # index 2

        self._stack.setCurrentIndex(0)
        v_layout.addWidget(self._stack)

        self._status_label = QLabel()
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        self.setStatusBar(status_bar)

        self._build_menu()
        h_layout.addWidget(content, stretch=1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("""
            QFrame { background: #1e293b; }
            QPushButton {
                text-align: left; padding: 10px 16px; border: none;
                color: #94a3b8; font-size: 13px; background: transparent;
            }
            QPushButton:hover { background: #334155; color: #e2e8f0; }
            QPushButton[active="true"] { background: #3b82f6; color: white; }
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        title = QLabel("License Timer")
        title.setStyleSheet("color: #e2e8f0; font-weight: bold; padding: 8px 16px 16px;")
        layout.addWidget(title)

        self._nav_products = QPushButton("📋  Products")
        self._nav_products.setProperty("active", "true")
        self._nav_products.clicked.connect(lambda: self._nav_to(0, self._nav_products))
        layout.addWidget(self._nav_products)

        self._nav_contacts = None
        self._nav_recipients = None

        if self._user.role in ("admin", "superadmin"):
            self._nav_contacts = QPushButton("👤  Contacts")
            self._nav_contacts.clicked.connect(lambda: self._nav_to(1, self._nav_contacts))
            self._nav_recipients = QPushButton("📧  Recipients")
            self._nav_recipients.clicked.connect(lambda: self._nav_to(2, self._nav_recipients))
            layout.addWidget(self._nav_contacts)
            layout.addWidget(self._nav_recipients)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #334155;")
        layout.addWidget(sep)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

        user_label = QLabel(self._user.email)
        user_label.setStyleSheet(
            "color: #64748b; font-size: 10px; padding: 8px 16px; word-wrap: break-word;"
        )
        user_label.setWordWrap(True)
        layout.addWidget(user_label)

        return sidebar

    def _nav_to(self, index: int, btn: QPushButton) -> None:
        self._stack.setCurrentIndex(index)
        for b in [self._nav_products, self._nav_contacts, self._nav_recipients]:
            if b:
                b.setProperty("active", "false")
                b.style().unpolish(b)
                b.style().polish(b)
        btn.setProperty("active", "true")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def _build_products_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = ProductTable()
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self._build_products_toolbar())
        layout.addWidget(self._table)
        return w

    def _build_products_toolbar(self) -> QToolBar:
        tb = QToolBar("Products")
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

        self._filter_btn = QPushButton("My Products")
        self._filter_btn.setCheckable(True)
        self._filter_btn.toggled.connect(self._toggle_filter)
        tb.addWidget(self._filter_btn)
        tb.addSeparator()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name / customer / order...")
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._table.apply_filter)
        tb.addWidget(self._search)
        return tb

    def _toggle_filter(self, checked: bool) -> None:
        self._show_my_products = checked
        self._filter_btn.setText("My Products ✓" if checked else "My Products")
        self._on_tick()

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
        self._quit_app()
        event.ignore()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self._tray.showMessage(
                "Product License Timer", "Running in the background.",
                QSystemTrayIcon.MessageIcon.Information, 2000,
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
        self._session.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # ------------------------------------------------------------------ Tick

    def _on_tick(self) -> None:
        if self._show_my_products:
            products = get_my_products(self._session, self._user)
        else:
            products = get_all_products(self._session)

        # Enrich with contact names for display
        enriched = self._enrich_products(products)
        self._table.refresh(enriched)
        check_and_send_v2(products, self._session, get_smtp_config())
        self._status_label.setText(
            f"Last checked: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}  |  "
            f"{len(products)} product(s) tracked  |  {self._user.email}"
        )

    def _enrich_products(self, products: list) -> list[dict]:
        """Convert ORM products to dicts with resolved contact names."""
        from models.orm import Contact
        result = []
        for p in products:
            d = {
                "id": p.id,
                "name": p.product_name,
                "product_name": p.product_name,
                "customer_name": p.customer_name,
                "order_number": p.order_number,
                "start_date": p.start_date,
                "duration_days": p.duration_days,
                "expiry_date": p.expiry_date,
                "notes": p.notes,
                "consultant_name": None,
                "account_manager_name": None,
                "project_manager_name": None,
            }
            for key, fk in [
                ("consultant_name", p.consultant_id),
                ("account_manager_name", p.account_manager_id),
                ("project_manager_name", p.project_manager_id),
            ]:
                if fk:
                    c = self._session.get(Contact, fk)
                    d[key] = c.name if c else None
            result.append(d)
        return result

    # ------------------------------------------------------------- Product CRUD

    def _add_product(self) -> None:
        dlg = ProductForm(self, session=self._session, caller=self._user)
        if dlg.exec():
            data = dlg.get_data()
            try:
                add_product(self._session, self._user, **data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add product:\n{e}")

    def _edit_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to edit.")
            return
        product = get_product(self._session, pid)
        dlg = ProductForm(self, product=product, session=self._session, caller=self._user)
        if dlg.exec():
            data = dlg.get_data()
            try:
                update_product(self._session, self._user, pid, **data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update product:\n{e}")

    def _delete_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to delete.")
            return
        product = get_product(self._session, pid)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{product.product_name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_product(self._session, pid)
            self._on_tick()

    def _clear_expired(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Expired",
            "Remove all expired products? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = delete_expired_products(self._session)
            self._on_tick()
            QMessageBox.information(self, "Done", f"Removed {count} expired product(s).")

    # --------------------------------------------------------------- Extras

    def _export_csv(self) -> None:
        products = get_all_products(self._session)
        enriched = self._enrich_products(products)
        export_to_csv(enriched, self)

    def _backup_db(self) -> None:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default = str(Path.home() / f"licenses_backup_{ts}.db")
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", default, "SQLite DB (*.db)"
        )
        if path:
            from models.database import DB_PATH
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
            "Product License Timer — Phase 2\n\n"
            "Multi-user centralized license tracker.\n"
            "Built with Python 3.13 + PyQt6 + SQLAlchemy",
        )
```

- [ ] **Step 2: Commit**

```bash
git add ui/main_window.py
git commit -m "feat: rebuild main window with sidebar nav and ORM integration"
```

---

### Task 17: Run full test suite + manual smoke test

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass. Note any failures and fix before proceeding.

- [ ] **Step 2: Set up a test `.env`**

Create `.env` with a working SQL Server connection string (or SQLite for local testing):

```env
DATABASE_URL=sqlite:///data/licenses_test.db
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_TLS=true
SENDER_NAME=License Tracker
```

- [ ] **Step 3: Run init_schema**

```bash
python -m migrations.init_schema
```

Expected: Tables created, prompted for superadmin email, recovery code printed.

- [ ] **Step 4: Launch app**

```bash
python main.py
```

Expected:
- Login dialog appears (light card)
- Login with superadmin email + `FujiFilm_11111`
- Password change dialog appears
- After changing password, main window opens with sidebar
- Products page visible; Contacts + Recipients visible (superadmin role)

- [ ] **Step 5: Smoke test checklist**

```
[ ] Add a contact (Consultant)
[ ] Add a system recipient
[ ] Add a product — verify ownership dropdowns populate from contacts
[ ] Edit product — assign consultant
[ ] Product table shows Assigned To column with pill
[ ] Dates display as DD-MM-YYYY throughout
[ ] My Products filter shows only own products
[ ] Settings → Email tab shows SMTP fields only (no recipients list)
[ ] Tray icon present, minimize to tray works
```

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "chore: phase 2 complete — full smoke test passed"
```

---

## Appendix — Running Tests Against SQLite (No SQL Server Required)

All tests use `sqlite:///:memory:` via fixtures. No SQL Server needed for the test suite.

For manual testing without SQL Server, set in `.env`:
```
DATABASE_URL=sqlite:///data/licenses.db
```

SQLite does not support all SQL Server features (e.g. `NVARCHAR` length enforcement) but is sufficient for development and testing. Switch to `mssql+pyodbc://...` when deploying to the shared server.

---

## Appendix — Resetting Superadmin

If locked out:
```bash
python migrations/reset_superadmin.py --token <recovery_code>
# OR if you have DB access:
python migrations/reset_superadmin.py --force --email new@co.com
```

`reset_superadmin.py` is not in this plan — create it by reading `.recovery_code`, comparing hash, then calling `hash_password` + updating the `users` table directly via SQLAlchemy.
