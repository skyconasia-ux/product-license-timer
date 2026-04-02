"""SQLAlchemy ORM models for Phase 2. Replaces raw sqlite3 schema."""
from __future__ import annotations
import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRole(enum.Enum):
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class ContactRoleType(enum.Enum):
    consultant = "Consultant"
    account_manager = "Account Manager"
    project_manager = "Project Manager"


class RecipientRoleType(enum.Enum):
    solutions_team = "Solutions Team"
    admin = "Admin"
    support = "Support"


class NotificationType(enum.Enum):
    days_15 = "15_days"
    days_10 = "10_days"
    days_5 = "5_days"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_type: Mapped[ContactRoleType] = mapped_column(Enum(ContactRoleType))


class SystemRecipient(Base):
    __tablename__ = "system_recipients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_type: Mapped[RecipientRoleType] = mapped_column(Enum(RecipientRoleType))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    order_number: Mapped[str] = mapped_column(String(100), default="")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), default="")
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True)
    consultant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=True)
    account_manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=True)
    project_manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=True)


class NotificationLog(Base):
    __tablename__ = "notifications_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"))
    notification_type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    __table_args__ = (UniqueConstraint("product_id", "notification_type"),)


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
