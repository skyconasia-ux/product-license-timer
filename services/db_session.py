"""SQLAlchemy engine and session factory. Reads DATABASE_URL from .env."""
from __future__ import annotations
import os
from sqlalchemy import create_engine, Engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

_engine: Engine | None = None
_SessionLocal = None


def _apply_schema_migrations(engine: Engine) -> None:
    """Create missing tables and add missing columns without dropping existing data."""
    from models.orm import Base
    Base.metadata.create_all(engine)  # creates new tables (no-op for existing ones)

    insp = inspect(engine)
    with engine.connect() as conn:
        # Add full_name to users if missing
        if "users" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("users")}
            if "full_name" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)"))
                conn.commit()

        if "products" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("products")}
            if "technical_consultant_id" not in existing:
                conn.execute(text(
                    "ALTER TABLE products ADD COLUMN technical_consultant_id INTEGER "
                    "REFERENCES contacts(id) ON DELETE SET NULL"
                ))
                conn.commit()

        if "account_secure_tokens" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("account_secure_tokens")}
            if "triggered_from_email" not in existing:
                conn.execute(text(
                    "ALTER TABLE account_secure_tokens "
                    "ADD COLUMN triggered_from_email VARCHAR(255) NOT NULL DEFAULT ''"
                ))
                conn.commit()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL not set in .env")
        _engine = create_engine(url, pool_pre_ping=True)
        _apply_schema_migrations(_engine)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(get_engine())
    return _SessionLocal()
