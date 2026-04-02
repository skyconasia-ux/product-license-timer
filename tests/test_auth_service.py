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
    S = sessionmaker(engine)
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
