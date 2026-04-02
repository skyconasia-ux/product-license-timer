import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base, User, UserRole, Contact, ContactRoleType, Product
from services.auth_service import hash_password, UserSession
from services.product_service import (
    add_product, update_product, delete_product,
    get_product, get_all_products, get_my_products,
    delete_expired_products,
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
def user_caller(session):
    u = User(email="u@co.com", password_hash=hash_password("p"),
             role=UserRole.user, is_verified=True, is_active=True)
    session.add(u)
    session.commit()
    return UserSession(user_id=u.id, email=u.email, role="user")


def test_add_product(session, user_caller):
    p = add_product(session, user_caller,
                    product_name="PaperCut MF",
                    start_date=date(2026, 1, 1),
                    duration_days=90)
    assert p.id is not None
    assert p.expiry_date == date(2026, 4, 1)
    assert p.created_by == user_caller.user_id


def test_add_product_duplicate_name(session, user_caller):
    add_product(session, user_caller, product_name="X",
                start_date=date(2026, 1, 1), duration_days=30)
    with pytest.raises(ValueError, match="already exists"):
        add_product(session, user_caller, product_name="X",
                    start_date=date(2026, 1, 1), duration_days=30)


def test_update_product_ownership(session, user_caller):
    c = Contact(name="Alice", email="a@co.com", role_type=ContactRoleType.consultant)
    session.add(c)
    session.flush()
    p = add_product(session, user_caller, product_name="Y",
                    start_date=date(2026, 1, 1), duration_days=30)
    update_product(session, user_caller, p.id, product_name="Y",
                   start_date=date(2026, 1, 1), duration_days=30,
                   consultant_id=c.id)
    assert session.get(Product, p.id).consultant_id == c.id


def test_get_my_products(session, user_caller):
    add_product(session, user_caller, product_name="Mine",
                start_date=date(2026, 1, 1), duration_days=30)
    other_user = User(email="o@co.com", password_hash="h",
                      role=UserRole.user, is_verified=True, is_active=True)
    session.add(other_user)
    session.flush()
    other_caller = UserSession(user_id=other_user.id, email="o@co.com", role="user")
    add_product(session, other_caller, product_name="Theirs",
                start_date=date(2026, 1, 1), duration_days=30)
    mine = get_my_products(session, user_caller)
    assert len(mine) == 1
    assert mine[0].product_name == "Mine"


def test_delete_expired(session, user_caller):
    add_product(session, user_caller, product_name="Old",
                start_date=date(2020, 1, 1), duration_days=10)
    add_product(session, user_caller, product_name="New",
                start_date=date(2026, 1, 1), duration_days=365)
    count = delete_expired_products(session)
    assert count == 1
    remaining = get_all_products(session)
    assert remaining[0].product_name == "New"
