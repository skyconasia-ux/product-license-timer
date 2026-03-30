# tests/test_timer_service.py
import pytest
from PyQt6.QtWidgets import QApplication
import sys

# QApplication required for QTimer
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


from services.timer_service import TimerService


def test_default_interval(qapp):
    svc = TimerService()
    assert svc.interval_seconds == 300


def test_set_interval_valid(qapp):
    svc = TimerService()
    svc.set_interval(600)
    assert svc.interval_seconds == 600


def test_set_interval_clamps_to_min(qapp):
    svc = TimerService()
    svc.set_interval(10)  # below min of 300
    assert svc.interval_seconds == svc.min_seconds


def test_set_interval_clamps_to_max(qapp):
    svc = TimerService()
    svc.set_interval(999999)  # above max of 432000
    assert svc.interval_seconds == svc.max_seconds


def test_force_tick_emits_signal(qapp, qtbot):
    svc = TimerService()
    with qtbot.waitSignal(svc.tick, timeout=1000):
        svc.force_tick()
