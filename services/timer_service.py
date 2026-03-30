"""
QTimer-based tick engine. Emits a tick signal on a configurable interval.
Single responsibility: schedule management only -- no business logic.
"""
from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

CONFIG_PATH = Path(__file__).parent.parent / "config" / "app_config.json"
DEFAULT_INTERVAL = 300
DEFAULT_MIN = 300
DEFAULT_MAX = 432000


class TimerService(QObject):
    """Emits tick every N seconds. Interval is live-adjustable."""

    tick = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = self._load_config()
        self._min = cfg.get("timer_min_seconds", DEFAULT_MIN)
        self._max = cfg.get("timer_max_seconds", DEFAULT_MAX)
        self._interval = max(self._min, min(self._max, cfg.get("timer_interval_seconds", DEFAULT_INTERVAL)))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return {}

    def start(self) -> None:
        """Start the timer with the current interval."""
        self._timer.start(self._interval * 1000)

    def stop(self) -> None:
        """Stop the timer."""
        self._timer.stop()

    def set_interval(self, seconds: int) -> None:
        """
        Change the interval. Clamps to [min, max].
        If timer is running, the new interval takes effect immediately.
        """
        seconds = max(self._min, min(self._max, seconds))
        self._interval = seconds
        if self._timer.isActive():
            self._timer.setInterval(seconds * 1000)

    def force_tick(self) -> None:
        """Emit tick immediately without resetting the current schedule."""
        self.tick.emit()

    @property
    def interval_seconds(self) -> int:
        return self._interval

    @property
    def min_seconds(self) -> int:
        return self._min

    @property
    def max_seconds(self) -> int:
        return self._max
