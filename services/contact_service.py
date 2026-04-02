"""CRUD for contacts (address book) and system_recipients."""
from __future__ import annotations
from sqlalchemy.orm import Session
from models.orm import Contact, SystemRecipient, ContactRoleType, RecipientRoleType
from services.auth_service import UserSession


def _require_admin(caller: UserSession) -> None:
    if caller.role not in ("admin", "superadmin"):
        raise PermissionError("Requires admin or superadmin role.")


# ---------------------------------------------------------------- Contacts

def add_contact(
    session: Session, caller: UserSession,
    name: str, email: str, role_type: str,
) -> Contact:
    _require_admin(caller)
    c = Contact(name=name, email=email, role_type=ContactRoleType[role_type.lower().replace(" ", "_")])
    session.add(c)
    session.commit()
    return c


def update_contact(
    session: Session, caller: UserSession, contact_id: int,
    name: str | None = None, email: str | None = None, role_type: str | None = None,
) -> None:
    _require_admin(caller)
    c = session.get(Contact, contact_id)
    if not c:
        raise ValueError(f"Contact {contact_id} not found")
    if name is not None:
        c.name = name
    if email is not None:
        c.email = email
    if role_type is not None:
        c.role_type = ContactRoleType[role_type.lower().replace(" ", "_")]
    session.commit()


def delete_contact(session: Session, caller: UserSession, contact_id: int) -> None:
    _require_admin(caller)
    c = session.get(Contact, contact_id)
    if c:
        session.delete(c)
        session.commit()


def list_contacts(session: Session) -> list[Contact]:
    return session.query(Contact).order_by(Contact.name).all()


def list_contacts_by_role(session: Session, role_type: str) -> list[Contact]:
    rt = ContactRoleType[role_type.lower().replace(" ", "_")]
    return session.query(Contact).filter_by(role_type=rt).order_by(Contact.name).all()


# -------------------------------------------------------- System Recipients

def add_recipient(
    session: Session, caller: UserSession,
    name: str, email: str, role_type: str,
) -> SystemRecipient:
    _require_admin(caller)
    rt = RecipientRoleType[role_type.lower().replace(" ", "_")]
    r = SystemRecipient(name=name, email=email, role_type=rt, is_active=True)
    session.add(r)
    session.commit()
    return r


def update_recipient(
    session: Session, caller: UserSession, recipient_id: int,
    name: str | None = None, email: str | None = None, role_type: str | None = None,
) -> None:
    _require_admin(caller)
    r = session.get(SystemRecipient, recipient_id)
    if not r:
        raise ValueError(f"Recipient {recipient_id} not found")
    if name is not None:
        r.name = name
    if email is not None:
        r.email = email
    if role_type is not None:
        r.role_type = RecipientRoleType[role_type.lower().replace(" ", "_")]
    session.commit()


def delete_recipient(session: Session, caller: UserSession, recipient_id: int) -> None:
    _require_admin(caller)
    r = session.get(SystemRecipient, recipient_id)
    if r:
        session.delete(r)
        session.commit()


def list_recipients(session: Session) -> list[SystemRecipient]:
    return session.query(SystemRecipient).order_by(SystemRecipient.name).all()


def toggle_recipient(session: Session, caller: UserSession, recipient_id: int) -> None:
    _require_admin(caller)
    r = session.get(SystemRecipient, recipient_id)
    if not r:
        raise ValueError(f"Recipient {recipient_id} not found")
    r.is_active = not r.is_active
    session.commit()
