# tests/test_date_utils.py
from datetime import date, timedelta
from utils.date_utils import (
    calculate_expiry_date,
    remaining_seconds,
    format_countdown,
    days_remaining,
    get_row_color,
)


def test_calculate_expiry_date():
    start = date(2026, 1, 1)
    assert calculate_expiry_date(start, 30) == date(2026, 1, 31)


def test_calculate_expiry_date_45_days():
    start = date(2026, 3, 1)
    assert calculate_expiry_date(start, 45) == date(2026, 4, 15)


def test_days_remaining_future():
    future = date.today() + timedelta(days=10)
    assert days_remaining(future) == 10


def test_days_remaining_past():
    past = date.today() - timedelta(days=5)
    assert days_remaining(past) == -5


def test_format_countdown_active():
    total = 1 * 86400 + 2 * 3600 + 3 * 60 + 4  # 1d 2h 3m 4s
    result, expired = format_countdown(total)
    assert result == "1d 2h 3m 4s"
    assert expired is False


def test_format_countdown_expired():
    total = -(1 * 86400 + 0 * 3600 + 0 * 60 + 0)
    result, expired = format_countdown(total)
    assert result == "Expired for: 1d 0h 0m 0s"
    assert expired is True


def test_format_countdown_zero():
    result, expired = format_countdown(0)
    assert result == "0d 0h 0m 0s"
    assert expired is False


def test_get_row_color_green():
    assert get_row_color(20) == "#d4edda"


def test_get_row_color_yellow():
    assert get_row_color(15) == "#fff3cd"


def test_get_row_color_orange():
    assert get_row_color(10) == "#ffe0b2"


def test_get_row_color_red():
    assert get_row_color(5) == "#f8d7da"


def test_get_row_color_expired():
    assert get_row_color(-1) == "#e0e0e0"


def test_remaining_seconds_future():
    future = date.today() + timedelta(days=100)
    secs = remaining_seconds(future)
    assert secs > 0


def test_remaining_seconds_past():
    past = date.today() - timedelta(days=1)
    secs = remaining_seconds(past)
    assert secs < 0
