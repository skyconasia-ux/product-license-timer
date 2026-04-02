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
    S = sessionmaker(engine)
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
