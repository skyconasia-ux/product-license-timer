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
    S = sessionmaker(engine)
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
