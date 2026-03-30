"""
Date calculation and countdown formatting utilities.
Single responsibility: all datetime math for license countdowns.
"""
from datetime import date, datetime, timedelta
from typing import Tuple


def calculate_expiry_date(start_date: date, duration_days: int) -> date:
    """Return expiry_date = start_date + duration_days."""
    return start_date + timedelta(days=duration_days)


def remaining_seconds(expiry_date: date) -> int:
    """
    Return seconds until end of expiry_date.
    Negative if expiry_date is in the past.
    """
    deadline = datetime.combine(expiry_date, datetime.max.time()).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    delta = deadline - datetime.now()
    return int(delta.total_seconds())


def format_countdown(total_seconds: int) -> Tuple[str, bool]:
    """
    Format total_seconds as 'Xd Xh Xm Xs'.
    Returns (formatted_string, is_expired).
    Negative input -> 'Expired for: Xd Xh Xm Xs', is_expired=True.
    """
    expired = total_seconds < 0
    abs_sec = abs(int(total_seconds))
    days = abs_sec // 86400
    hours = (abs_sec % 86400) // 3600
    minutes = (abs_sec % 3600) // 60
    seconds = abs_sec % 60
    time_str = f"{days}d {hours}h {minutes}m {seconds}s"
    if expired:
        return f"Expired for: {time_str}", True
    return time_str, False


def days_remaining(expiry_date: date) -> int:
    """Return whole days remaining. Negative if expired."""
    return (expiry_date - date.today()).days


def get_row_color(days_left: int) -> str:
    """Return background hex colour for a given days_remaining value."""
    if days_left > 15:
        return "#d4edda"   # green
    if days_left > 10:
        return "#fff3cd"   # yellow
    if days_left > 5:
        return "#ffe0b2"   # orange
    if days_left >= 0:
        return "#f8d7da"   # red
    return "#e0e0e0"       # grey -- expired
