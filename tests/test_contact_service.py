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
    S = sessionmaker(engine)
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
