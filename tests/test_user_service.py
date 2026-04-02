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
    S = sessionmaker(engine)
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
    change_email(session, caller, caller.user_id, "new@co.com")
    assert session.get(User, caller.user_id).email == "new@co.com"
