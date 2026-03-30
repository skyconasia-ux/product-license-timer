"""
Email alert logic with threshold checking and duplicate prevention.
Single responsibility: decide when to send alerts and dispatch emails.
"""
from __future__ import annotations
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
