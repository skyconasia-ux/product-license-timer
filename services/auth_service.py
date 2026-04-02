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
