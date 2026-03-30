# tests/test_database_service.py
from datetime import date
import pytest
from services.database_service import DatabaseService


@pytest.fixture
def svc(tmp_db):
    return DatabaseService(db_path=tmp_db)


def test_add_and_get_product(svc):
    pid = svc.add_product(
        name="Equitrac 6",
        start_date=date(2026, 1, 1),
        duration_days=30,
        customer_name="ABC Corp",
        order_number="ORD-001",
    )
    assert pid is not None
    p = svc.get_product(pid)
    assert p["name"] == "Equitrac 6"
    assert p["customer_name"] == "ABC Corp"
    assert p["expiry_date"] == "2026-01-31"


def test_get_all_products_sorted_by_expiry(svc):
    svc.add_product("B Product", date(2026, 3, 1), 30)
    svc.add_product("A Product", date(2026, 1, 1), 30)
    products = svc.get_all_products()
    assert products[0]["name"] == "A Product"  # earlier expiry first
    assert products[1]["name"] == "B Product"


def test_update_product(svc):
    pid = svc.add_product("PaperCut MF", date(2026, 1, 1), 30)
    svc.update_product(pid, "PaperCut MF", date(2026, 2, 1), 45, customer_name="XYZ Ltd")
    p = svc.get_product(pid)
    assert p["duration_days"] == 45
    assert p["customer_name"] == "XYZ Ltd"
    assert p["expiry_date"] == "2026-03-18"


def test_delete_product(svc):
    pid = svc.add_product("YSoft SafeQ 6", date(2026, 1, 1), 30)
    svc.delete_product(pid)
    assert svc.get_product(pid) is None


def test_delete_expired_products(svc):
    svc.add_product("Expired A", date(2020, 1, 1), 30)
    svc.add_product("Expired B", date(2021, 1, 1), 30)
    svc.add_product("Active", date(2030, 1, 1), 30)
    count = svc.delete_expired_products()
    assert count == 2
    products = svc.get_all_products()
    assert len(products) == 1
    assert products[0]["name"] == "Active"


def test_duplicate_name_raises(svc):
    svc.add_product("Equitrac 6", date(2026, 1, 1), 30)
    with pytest.raises(Exception):
        svc.add_product("Equitrac 6", date(2026, 2, 1), 30)


def test_notification_sent_false_initially(svc):
    pid = svc.add_product("AWMS 2", date(2026, 1, 1), 30)
    assert svc.notification_sent(pid, "15_days") is False


def test_log_and_check_notification(svc):
    pid = svc.add_product("PaperCut Hive", date(2026, 1, 1), 30)
    svc.log_notification(pid, "5_days")
    assert svc.notification_sent(pid, "5_days") is True
    assert svc.notification_sent(pid, "10_days") is False


def test_log_notification_duplicate_is_safe(svc):
    pid = svc.add_product("SafeQ", date(2026, 1, 1), 30)
    svc.log_notification(pid, "15_days")
    svc.log_notification(pid, "15_days")  # must not raise


def test_delete_product_cascades_notifications(svc):
    pid = svc.add_product("ToDelete", date(2026, 1, 1), 30)
    svc.log_notification(pid, "5_days")
    svc.delete_product(pid)
    # No exception -- cascade handled by DB
