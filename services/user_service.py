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
