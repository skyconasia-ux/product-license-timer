"""Authentication: login, password hashing, session, email verification."""
from __future__ import annotations
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy.orm import Session

from models.orm import (
    AccountSecureToken, EmailChangeToken, EmailVerification,
    PasswordResetToken, User, UserRole,
)

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


def verify_and_set_password(
    session: Session, token: str, new_password: str
) -> tuple[bool, str]:
    """
    Validate an email-verification token, mark the account verified, and set
    the user's password in one atomic step.  Used by the web verification page.
    Returns (True, email) on success, (False, '') on invalid/expired token.
    """
    ev = session.query(EmailVerification).filter_by(token=token).first()
    if not ev or ev.expires_at < datetime.now():
        return False, ""
    user = session.get(User, ev.user_id)
    if not user:
        return False, ""
    user.is_verified = True
    user.password_hash = hash_password(new_password)
    email = user.email
    session.delete(ev)
    session.commit()
    return True, email


def create_password_reset_token(session: Session, email: str) -> str | None:
    """Generate a 20-minute single-use reset token. Returns token if email exists, else None."""
    user = session.query(User).filter_by(email=email, is_active=True).first()
    if not user:
        return None
    token = secrets.token_urlsafe(32)
    prt = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now() + timedelta(minutes=20),
    )
    session.add(prt)
    session.commit()
    return token


def reset_password_with_token(session: Session, token: str, new_password: str) -> bool:
    """Validate token, update password, mark token used. Returns True on success."""
    prt = session.query(PasswordResetToken).filter_by(token=token, used=False).first()
    if not prt or prt.expires_at < datetime.now():
        return False
    user = session.get(User, prt.user_id)
    if not user:
        return False
    user.password_hash = hash_password(new_password)
    prt.used = True
    session.commit()
    return True


def create_email_change_token(
    session: Session, user_id: int, new_email: str, current_password: str
) -> str | None:
    """
    Validate current password, check new_email is not taken, create a 24h token.
    Returns the token on success, None if current password is wrong.
    Raises ValueError if the new email is already in use.
    """
    import re
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", new_email):
        raise ValueError("Invalid email address.")
    user = session.get(User, user_id)
    if not user:
        raise ValueError("User not found.")
    if not bcrypt.checkpw(current_password.encode(), user.password_hash.encode()):
        return None  # wrong password — caller shows appropriate error
    if session.query(User).filter_by(email=new_email).first():
        raise ValueError("This email address is already in use.")
    token = secrets.token_urlsafe(32)
    ect = EmailChangeToken(
        user_id=user_id,
        new_email=new_email,
        token=token,
        expires_at=datetime.now() + timedelta(hours=24),
    )
    session.add(ect)
    session.commit()
    return token


def confirm_email_change_and_set_password(
    session: Session, token: str, new_password: str
) -> tuple[bool, str, str]:
    """
    Confirm an email-change token and atomically update both the email and password.
    Returns (True, old_email, new_email) on success, (False, '', '') otherwise.
    """
    ect = session.query(EmailChangeToken).filter_by(token=token, used=False).first()
    if not ect or ect.expires_at < datetime.now():
        return False, "", ""
    user = session.get(User, ect.user_id)
    if not user:
        return False, "", ""
    old_email = user.email
    new_email = ect.new_email
    user.email = new_email
    user.password_hash = hash_password(new_password)
    ect.used = True
    session.commit()
    return True, old_email, new_email


def create_account_secure_token(
    session: Session, user_id: int, triggered_from_email: str
) -> str:
    """
    Generate a 72-hour single-use token embedded in security notification emails.
    triggered_from_email is the address the notification was sent to — for password
    changes this is the current email; for email changes this is the OLD email.
    If clicked, the account is locked and superadmins are alerted.
    """
    token = secrets.token_urlsafe(32)
    ast = AccountSecureToken(
        user_id=user_id,
        token=token,
        triggered_from_email=triggered_from_email,
        expires_at=datetime.now() + timedelta(hours=72),
    )
    session.add(ast)
    session.commit()
    return token


def trigger_account_secure(
    session: Session, token: str
) -> tuple[bool, str, str]:
    """
    Validate the secure token, disable the account.
    Returns (True, current_email, triggered_from_email) on success.
    Returns (False, '', '') if token is invalid or already used.
    Does NOT send emails — caller (verification server) handles notifications.
    """
    ast = session.query(AccountSecureToken).filter_by(token=token, used=False).first()
    if not ast or ast.expires_at < datetime.now():
        return False, "", ""
    user = session.get(User, ast.user_id)
    if not user:
        return False, "", ""
    user.is_active = False
    ast.used = True
    triggered_from = ast.triggered_from_email
    session.commit()
    return True, user.email, triggered_from
