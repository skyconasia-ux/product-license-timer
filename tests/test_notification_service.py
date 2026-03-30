# tests/test_notification_service.py
from datetime import date, timedelta
from unittest.mock import patch
import pytest
from services.notification_service import NotificationService
from services.database_service import DatabaseService


@pytest.fixture
def svc(tmp_path):
    cfg_path = tmp_path / "email_config.json"
    return NotificationService(config_path=cfg_path)


@pytest.fixture
def db(tmp_db):
    return DatabaseService(db_path=tmp_db)


def test_check_and_send_skips_expired_products(svc, db):
    """Expired products should never trigger a notification."""
    db.add_product("Old App", date(2020, 1, 1), 30)
    products = db.get_all_products()
    with patch.object(svc, 'send_email') as mock_send:
        svc.check_and_send(products, db)
        mock_send.assert_not_called()


def test_check_and_send_sends_at_threshold(svc, db):
    """A product at exactly 5 days should trigger the 5_days alert."""
    expiry = date.today() + timedelta(days=5)
    start = expiry - timedelta(days=30)
    db.add_product("Threshold App", start, 30)
    products = db.get_all_products()
    with patch.object(svc, '_send_in_thread', return_value=True) as mock_send:
        svc.check_and_send(products, db)
        calls = [c.args[1] for c in mock_send.call_args_list]
        assert 5 in calls


def test_check_and_send_no_duplicate(svc, db):
    """Already-logged notifications must not be re-sent."""
    expiry = date.today() + timedelta(days=5)
    start = expiry - timedelta(days=30)
    pid = db.add_product("No Dup App", start, 30)
    db.log_notification(pid, "5_days")
    products = db.get_all_products()
    with patch.object(svc, '_send_in_thread', return_value=True) as mock_send:
        svc.check_and_send(products, db)
        calls = [c.args[1] for c in mock_send.call_args_list]
        assert 5 not in calls


def test_send_email_returns_false_when_not_configured(svc):
    ok, msg = svc.send_email(
        {"name": "X", "customer_name": "", "order_number": "",
         "start_date": "2026-01-01", "expiry_date": "2026-01-31"},
        threshold=5,
    )
    assert ok is False
    assert msg  # error message present


def test_test_connection_returns_false_when_not_configured(svc):
    ok, msg = svc.test_connection()
    assert ok is False
    assert msg
