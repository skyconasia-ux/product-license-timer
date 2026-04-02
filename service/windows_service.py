"""
Windows Service wrapper for the notification daemon.

Requirements:
  pip install pywin32

Install:   python service\\windows_service.py install
Start:     python service\\windows_service.py start
  -or-     sc start ProductLicenseTimerDaemon
Stop:      python service\\windows_service.py stop
Remove:    python service\\windows_service.py remove
Debug:     python service\\windows_service.py debug   (runs in foreground, Ctrl+C to stop)

The service runs as the Local System account by default. To use a specific account
with network/DB access, open services.msc → Properties → Log On and set credentials.
"""
from __future__ import annotations
import os
import sys
import time
import threading
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import win32service
    import win32serviceutil
    import win32event
    import servicemanager
except ImportError:
    print("pywin32 is required: pip install pywin32")
    sys.exit(1)


class ProductLicenseTimerDaemon(win32serviceutil.ServiceFramework):
    _svc_name_         = "ProductLicenseTimerDaemon"
    _svc_display_name_ = "Product License Timer — Notification Daemon"
    _svc_description_  = (
        "Monitors product license expiry dates and sends email alerts "
        "at 15, 10, and 5-day thresholds. Part of Product License Timer."
    )

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._running = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._running = False
        win32event.SetEvent(self._stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self._running = True
        self._main()

    def _main(self):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")

        interval = int(os.getenv("DAEMON_INTERVAL", "300"))

        from service.notification_daemon import run_once

        while self._running:
            run_once()
            # Sleep in 1s slices so we can respond to stop events quickly
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Called by SCM without arguments — hand control to ServiceFramework
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ProductLicenseTimerDaemon)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ProductLicenseTimerDaemon)
