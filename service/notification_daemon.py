"""
Headless notification daemon.

Runs check_and_send_v2 on a schedule without the GUI. Designed to run as:
  - Windows Service (via windows_service.py)
  - Linux systemd service (via product-license-timer.service unit file)
  - Or directly: python -m service.notification_daemon

Environment variables (from .env):
  DATABASE_URL      — SQLAlchemy connection string
  DAEMON_INTERVAL   — Check interval in seconds (default: 300)
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_TLS / SENDER_NAME
"""
from __future__ import annotations
import logging
import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when run as a module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daemon] %(levelname)s %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_once() -> None:
    """Run a single notification check cycle."""
    from services.db_session import get_engine, get_session
    from services.notification_service import check_and_send_v2, get_smtp_config
    from services.product_service import get_all_products

    session_factory = get_session()
    session = session_factory()
    try:
        products = get_all_products(session)
        smtp_cfg = get_smtp_config()
        check_and_send_v2(products, session, smtp_cfg)
        log.info("Check complete — %d product(s) evaluated.", len(products))
    except Exception:
        log.exception("Error during notification check.")
    finally:
        session.close()


def run_loop(interval: int = 300) -> None:
    """Run the notification check in a loop, sleeping `interval` seconds between runs."""
    log.info("Notification daemon started. Check interval: %ds.", interval)
    while True:
        run_once()
        time.sleep(interval)


if __name__ == "__main__":
    interval = int(os.getenv("DAEMON_INTERVAL", "300"))
    run_loop(interval)
