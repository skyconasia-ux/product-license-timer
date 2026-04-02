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
        _SessionLocal = sessionmaker(get_engine())
    return _SessionLocal()
