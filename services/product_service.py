"""Product CRUD using SQLAlchemy. Replaces database_service for product operations."""
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from models.orm import Product
from services.auth_service import UserSession
from utils.date_utils import calculate_expiry_date


def add_product(
    session: Session,
    caller: UserSession,
    product_name: str,
    start_date: date,
    duration_days: int,
    customer_name: str = "",
    order_number: str = "",
    notes: str = "",
    consultant_id: int | None = None,
    technical_consultant_id: int | None = None,
    account_manager_id: int | None = None,
    project_manager_id: int | None = None,
) -> Product:
    if session.query(Product).filter_by(product_name=product_name).first():
        raise ValueError(f"Product already exists: {product_name}")
    expiry = calculate_expiry_date(start_date, duration_days)
    p = Product(
        product_name=product_name,
        customer_name=customer_name,
        order_number=order_number,
        start_date=start_date,
        duration_days=duration_days,
        expiry_date=expiry,
        notes=notes,
        created_by=caller.user_id,
        consultant_id=consultant_id,
        technical_consultant_id=technical_consultant_id,
        account_manager_id=account_manager_id,
        project_manager_id=project_manager_id,
    )
    session.add(p)
    session.commit()
    return p


def update_product(
    session: Session,
    caller: UserSession,
    product_id: int,
    product_name: str,
    start_date: date,
    duration_days: int,
    customer_name: str = "",
    order_number: str = "",
    notes: str = "",
    consultant_id: int | None = None,
    technical_consultant_id: int | None = None,
    account_manager_id: int | None = None,
    project_manager_id: int | None = None,
) -> None:
    p = session.get(Product, product_id)
    if not p:
        raise ValueError(f"Product {product_id} not found")
    existing = session.query(Product).filter_by(product_name=product_name).first()
    if existing and existing.id != product_id:
        raise ValueError(f"Product name already exists: {product_name}")
    expiry = calculate_expiry_date(start_date, duration_days)
    p.product_name = product_name
    p.customer_name = customer_name
    p.order_number = order_number
    p.start_date = start_date
    p.duration_days = duration_days
    p.expiry_date = expiry
    p.notes = notes
    p.consultant_id = consultant_id
    p.technical_consultant_id = technical_consultant_id
    p.account_manager_id = account_manager_id
    p.project_manager_id = project_manager_id
    session.commit()


def delete_product(session: Session, product_id: int) -> None:
    p = session.get(Product, product_id)
    if p:
        session.delete(p)
        session.commit()


def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)


def get_all_products(session: Session) -> list[Product]:
    return session.query(Product).order_by(Product.expiry_date).all()


def get_my_products(session: Session, caller: UserSession) -> list[Product]:
    return (session.query(Product)
            .filter_by(created_by=caller.user_id)
            .order_by(Product.expiry_date)
            .all())


def delete_expired_products(session: Session) -> int:
    today = date.today()
    expired = session.query(Product).filter(Product.expiry_date < today).all()
    count = len(expired)
    for p in expired:
        session.delete(p)
    session.commit()
    return count


def notification_sent(session: Session, product_id: int, notification_type: str) -> bool:
    from models.orm import NotificationLog, NotificationType
    ntype = NotificationType[f"days_{notification_type.replace('_days', '')}"]
    return session.query(NotificationLog).filter_by(
        product_id=product_id, notification_type=ntype
    ).first() is not None


def log_notification(session: Session, product_id: int, notification_type: str) -> None:
    from models.orm import NotificationLog, NotificationType
    from datetime import datetime
    from sqlalchemy.exc import IntegrityError
    ntype = NotificationType[f"days_{notification_type.replace('_days', '')}"]
    try:
        session.add(NotificationLog(product_id=product_id, notification_type=ntype,
                                    sent_at=datetime.now()))
        session.commit()
    except IntegrityError:
        session.rollback()
