"""
Email alert logic with threshold checking and duplicate prevention.
Single responsibility: decide when to send alerts and dispatch emails.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()
import json
import smtplib
import threading
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Tuple

from utils.date_utils import days_remaining

CONFIG_PATH = Path(__file__).parent.parent / "config" / "email_config.json"
THRESHOLDS = [15, 10, 5]  # days -- checked in descending order


class NotificationService:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        with open(self.config_path) as f:
            return json.load(f)

    def check_and_send(self, products: List[dict], db_service) -> None:
        """
        For each product, check all thresholds.
        Sends an email and logs it if the threshold is met and not yet logged.
        Skips expired products entirely.
        """
        for product in products:
            expiry = date.fromisoformat(product["expiry_date"])
            days_left = days_remaining(expiry)
            if days_left < 0:
                continue  # expired -- no more alerts
            for threshold in THRESHOLDS:
                ntype = f"{threshold}_days"
                if days_left <= threshold and not db_service.notification_sent(product["id"], ntype):
                    sent = self._send_in_thread(product, threshold)
                    if sent:
                        db_service.log_notification(product["id"], ntype)

    def _send_in_thread(self, product: dict, threshold: int) -> bool:
        """Send email in a background thread; block until done (max 15s)."""
        result = [False]

        def _send():
            result[0], _ = self.send_email(product, threshold)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        t.join(timeout=15)
        return result[0]

    def send_email(self, product: dict, threshold: int) -> Tuple[bool, str]:
        """
        Send a single threshold alert email.
        Returns (success: bool, error_message: str).
        """
        cfg = self._load_config()
        if not cfg.get("smtp_user"):
            return False, "SMTP username not configured"
        if not cfg.get("recipients"):
            return False, "No recipients configured"
        try:
            msg = MIMEMultipart()
            msg["Subject"] = (
                f"\u26a0 Trial Expiry Alert \u2014 {product['name']} ({threshold} days remaining)"
            )
            msg["From"] = (
                f"{cfg.get('sender_name', 'License Tracker')} <{cfg['smtp_user']}>"
            )
            msg["To"] = ", ".join(cfg["recipients"])
            body = (
                f"Product Name  : {product['name']}\n"
                f"Customer      : {product.get('customer_name', '')}\n"
                f"Order Number  : {product.get('order_number', '')}\n"
                f"Start Date    : {product['start_date']}\n"
                f"Expiry Date   : {product['expiry_date']}\n"
                f"Days Remaining: {threshold}\n"
                f"Threshold     : {threshold}-day warning\n\n"
                f"Please renew or arrange a replacement license before the expiry date."
            )
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as server:
                server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], cfg["recipients"], msg.as_string())
            return True, ""
        except Exception as e:
            print(f"[NotificationService] Email send failed: {e}")
            return False, str(e)

    def test_connection(self) -> Tuple[bool, str]:
        """Send a test email to the first recipient. Returns (success, message)."""
        cfg = self._load_config()
        if not cfg.get("smtp_user"):
            return False, "SMTP username not configured"
        if not cfg.get("recipients"):
            return False, "No recipients configured"
        try:
            msg = MIMEText("This is a test email from Product License Timer.", "plain")
            msg["Subject"] = "License Tracker \u2014 Test Connection"
            msg["From"] = cfg["smtp_user"]
            msg["To"] = cfg["recipients"][0]
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as server:
                server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], [cfg["recipients"][0]], msg.as_string())
            return True, "Test email sent successfully"
        except Exception as e:
            return False, str(e)


def resolve_recipients(session, product) -> list[str]:
    """
    Build deduplicated list of recipient emails for a product alert.
    Combines active system_recipients + product-linked contacts.
    """
    from models.orm import SystemRecipient, Contact
    emails: list[str] = []

    # Active system recipients
    for r in session.query(SystemRecipient).filter_by(is_active=True).all():
        emails.append(r.email)

    # Product-linked contacts
    for fk in ("consultant_id", "account_manager_id", "project_manager_id"):
        cid = getattr(product, fk, None)
        if cid:
            contact = session.get(Contact, cid)
            if contact:
                emails.append(contact.email)

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def _contact_display(session, contact_id) -> str:
    if not contact_id:
        return "—"
    from models.orm import Contact
    c = session.get(Contact, contact_id)
    return f"{c.name} ({c.email})" if c else "—"


def format_email_body(session, product, threshold: int) -> str:
    """Build email body with DD-MM-YYYY dates and ownership info."""
    def fmt(d) -> str:
        if hasattr(d, "strftime"):
            return d.strftime("%d-%m-%Y")
        from datetime import date as _date
        return _date.fromisoformat(str(d)).strftime("%d-%m-%Y")

    return (
        f"Product Name    : {product.product_name}\n"
        f"Customer        : {getattr(product, 'customer_name', '')}\n"
        f"Order Number    : {getattr(product, 'order_number', '')}\n"
        f"Start Date      : {fmt(product.start_date)}\n"
        f"Expiry Date     : {fmt(product.expiry_date)}\n"
        f"Days Remaining  : {threshold}\n"
        f"Threshold       : {threshold}-day warning\n"
        f"Consultant      : {_contact_display(session, getattr(product, 'consultant_id', None))}\n"
        f"Account Manager : {_contact_display(session, getattr(product, 'account_manager_id', None))}\n"
        f"Project Manager : {_contact_display(session, getattr(product, 'project_manager_id', None))}\n\n"
        f"Please renew or arrange a replacement license before the expiry date."
    )


def check_and_send_v2(products: list, session, smtp_cfg: dict) -> None:
    """
    New notification check using ORM products and DB recipients.
    Drop-in replacement for check_and_send once fully migrated.
    """
    from services.product_service import notification_sent, log_notification

    for product in products:
        days_left = days_remaining(product.expiry_date)
        if days_left < 0:
            continue
        for threshold in THRESHOLDS:
            ntype = f"{threshold}_days"
            if days_left <= threshold and not notification_sent(session, product.id, ntype):
                recipients = resolve_recipients(session, product)
                if not recipients:
                    continue
                body = format_email_body(session, product, threshold)
                subject = f"⚠ Trial Expiry Alert — {product.product_name} ({threshold} days remaining)"
                sent = _send_smtp(subject, body, recipients, smtp_cfg)
                if sent:
                    log_notification(session, product.id, ntype)


def _send_smtp(subject: str, body: str, recipients: list[str], cfg: dict) -> bool:
    """Send email via SMTP. Returns True on success."""
    if not cfg.get("smtp_user") or not recipients:
        return False

    result = [False]

    def _send():
        try:
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = f"{cfg.get('sender_name', 'License Tracker')} <{cfg['smtp_user']}>"
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(body, "plain"))
            use_tls = str(cfg.get("smtp_tls", "true")).lower() == "true"
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as server:
                if use_tls:
                    server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], recipients, msg.as_string())
            result[0] = True
        except Exception as e:
            print(f"[NotificationService] Email failed: {e}")

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    t.join(timeout=15)
    return result[0]


def get_smtp_config() -> dict:
    """Read SMTP config from .env. Falls back to email_config.json if .env missing keys."""
    cfg = {
        "smtp_host": os.getenv("SMTP_HOST", ""),
        "smtp_port": os.getenv("SMTP_PORT", "587"),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "smtp_password": os.getenv("SMTP_PASSWORD", ""),
        "smtp_tls": os.getenv("SMTP_TLS", "true"),
        "sender_name": os.getenv("SENDER_NAME", "License Tracker"),
    }
    if not cfg["smtp_host"]:
        # Fallback to legacy email_config.json
        import json
        legacy = Path(__file__).parent.parent / "config" / "email_config.json"
        if legacy.exists():
            with open(legacy) as f:
                old = json.load(f)
            cfg["smtp_host"] = old.get("smtp_host", "")
            cfg["smtp_port"] = old.get("smtp_port", 587)
            cfg["smtp_user"] = old.get("smtp_user", "")
            cfg["smtp_password"] = old.get("smtp_password", "")
            cfg["sender_name"] = old.get("sender_name", "License Tracker")
    return cfg
