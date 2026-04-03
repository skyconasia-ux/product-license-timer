"""
Tabbed settings dialog. Saves to app_config.json and email_config.json.
Single responsibility: edit and persist all application configuration.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QWidget,
    QFormLayout, QSpinBox, QLineEdit, QCheckBox,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QScrollArea, QFrame, QTextBrowser,
)
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)

APP_CONFIG_PATH = Path(__file__).parent.parent / "config" / "app_config.json"
EMAIL_CONFIG_PATH = Path(__file__).parent.parent / "config" / "email_config.json"

_APP_DEFAULTS = {
    "timer_interval_seconds": 300,
    "timer_min_seconds": 300,
    "timer_max_seconds": 432000,
}
_EMAIL_DEFAULTS = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "smtp_tls": True,
    "sender_name": "License Tracker",
}


def _load(path: Path, defaults: dict) -> dict:
    if path.exists():
        with open(path) as f:
            return {**defaults, **json.load(f)}
    return dict(defaults)


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, caller=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._caller = caller
        self._is_admin = (caller is None or caller.role in ("admin", "superadmin"))
        self._app_cfg = _load(APP_CONFIG_PATH, _APP_DEFAULTS)
        self._email_cfg = _load(EMAIL_CONFIG_PATH, _EMAIL_DEFAULTS)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_timer_tab(), "Timer")
        self._tabs.addTab(self._build_email_tab(), "Email / SMTP")
        self._tabs.addTab(self._build_system_tab(), "System")
        if self._is_admin:
            self._tabs.addTab(self._build_verification_tab(), "Verification")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    # ----------------------------------------------------------------- Timer tab
    def _build_timer_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 2592000)
        self.interval_spin.setValue(self._app_cfg["timer_interval_seconds"])
        self.interval_spin.setSuffix(" seconds")

        self.min_spin = QSpinBox()
        self.min_spin.setRange(1, 2592000)
        self.min_spin.setValue(self._app_cfg["timer_min_seconds"])
        self.min_spin.setSuffix(" seconds")

        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 2592000)
        self.max_spin.setValue(self._app_cfg["timer_max_seconds"])
        self.max_spin.setSuffix(" seconds")

        form.addRow("Check Interval", self.interval_spin)
        form.addRow("Minimum Allowed", self.min_spin)
        form.addRow("Maximum Allowed", self.max_spin)
        form.addRow(QLabel("Changes take effect immediately without restart."))
        return w

    # ----------------------------------------------------------------- Email tab
    def _build_email_tab(self) -> QWidget:
        import os
        w = QWidget()
        form = QFormLayout(w)

        self.smtp_host = QLineEdit(os.getenv("SMTP_HOST", "smtp.gmail.com"))
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(int(os.getenv("SMTP_PORT", "587")))
        self.smtp_user = QLineEdit(os.getenv("SMTP_USER", ""))
        self.smtp_pass = QLineEdit(os.getenv("SMTP_PASSWORD", ""))
        self.smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        show_btn = QPushButton("Show")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda on: self.smtp_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        pass_row = QHBoxLayout()
        pass_row.addWidget(self.smtp_pass)
        pass_row.addWidget(show_btn)

        self.smtp_tls = QCheckBox("Use TLS")
        self.smtp_tls.setChecked(os.getenv("SMTP_TLS", "true").lower() == "true")
        self.sender_name = QLineEdit(os.getenv("SENDER_NAME", "License Tracker"))

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)

        if not self._is_admin:
            self.smtp_host.setReadOnly(True)
            self.smtp_port.setReadOnly(True)
            self.smtp_user.setReadOnly(True)
            self.smtp_pass.setReadOnly(True)
            show_btn.setEnabled(False)
            self.smtp_tls.setEnabled(False)
            self.sender_name.setReadOnly(True)
            test_btn.setEnabled(False)
            readonly_note = QLabel("SMTP settings are read-only. Contact an admin to make changes.")
            readonly_note.setStyleSheet("color: #64748b; font-size: 10px;")
            form.addRow(readonly_note)

        form.addRow("SMTP Host", self.smtp_host)
        form.addRow("SMTP Port", self.smtp_port)
        form.addRow("Username", self.smtp_user)
        form.addRow("Password", pass_row)
        form.addRow("", self.smtp_tls)
        form.addRow("Sender Name", self.sender_name)
        form.addRow(QLabel("Recipients are managed in the System Recipients page."))
        form.addRow("", test_btn)
        return w

    def _test_connection(self) -> None:
        self._persist()  # save current values to .env first
        cfg = {
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": self.smtp_port.value(),
            "smtp_user": self.smtp_user.text().strip(),
            "smtp_password": self.smtp_pass.text(),
            "smtp_tls": self.smtp_tls.isChecked(),
            "sender_name": self.sender_name.text().strip(),
        }
        if not cfg["smtp_host"]:
            QMessageBox.warning(self, "Test Connection Failed", "SMTP Host is not configured.")
            return
        if not cfg["smtp_user"]:
            QMessageBox.warning(self, "Test Connection Failed", "SMTP Username is not configured.")
            return
        error_holder = [None]

        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        try:
            msg = MIMEMultipart()
            msg["Subject"] = "Test — Product License Timer"
            msg["From"] = f"{cfg.get('sender_name', 'License Tracker')} <{cfg['smtp_user']}>"
            msg["To"] = cfg["smtp_user"]
            msg.attach(MIMEText("SMTP connection test from Product License Timer.", "plain"))
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587)), timeout=15) as server:
                if cfg["smtp_tls"]:
                    server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_password"])
                server.sendmail(cfg["smtp_user"], [cfg["smtp_user"]], msg.as_string())
            QMessageBox.information(self, "Test Connection",
                                    f"Test email sent to {cfg['smtp_user']}.")
        except Exception as e:
            QMessageBox.warning(self, "Test Connection Failed",
                                f"Could not send email:\n\n{e}")

    # ----------------------------------------------------------------- System tab
    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.autostart_check = QCheckBox("Start with Windows (minimized to tray)")
        self.autostart_check.setChecked(self._autostart_enabled())
        layout.addWidget(self.autostart_check)
        layout.addStretch()
        return w

    # --------------------------------------------------------- Verification tab
    def _build_verification_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ---- Current URL badge ----
        from services.verification_server import get_base_url
        self._current_url_label = QLabel(f"Current link base URL: {get_base_url()}")
        self._current_url_label.setStyleSheet(
            "color: #16a34a; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(self._current_url_label)

        # ---- Fields ----
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.verify_url = QLineEdit(self._app_cfg.get("verification_server_url", ""))
        self.verify_url.setPlaceholderText("https://verify.yourdomain.com  (leave blank for hostname auto-detect)")

        self.verify_port = QSpinBox()
        self.verify_port.setRange(1024, 65535)
        self.verify_port.setValue(self._app_cfg.get("verification_server_port", 8765))

        form.addRow("Public Verification URL", self.verify_url)
        form.addRow("Local Server Port", self.verify_port)
        layout.addLayout(form)

        # ---- Test button ----
        test_row = QHBoxLayout()
        test_btn = QPushButton("Test Public URL")
        test_btn.setFixedWidth(150)
        test_btn.clicked.connect(self._test_public_url)
        test_row.addWidget(test_btn)
        test_row.addStretch()
        layout.addLayout(test_row)

        # ---- Setup guide ----
        layout.addSpacing(8)
        guide_title = QLabel("Setup Guide")
        guide_title.setStyleSheet("font-weight: bold; color: #1e293b;")
        layout.addWidget(guide_title)

        guide = QTextBrowser()
        guide.setOpenExternalLinks(False)
        guide.setMinimumHeight(220)
        guide.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; "
            "border-radius: 6px; font-size: 12px; color: #334155;"
        )
        guide.setPlainText(
            "The verification server runs inside this app on the Local Server Port "
            "(default 8765). Emailed links point to the Public Verification URL so "
            "users can click them from anywhere.\n\n"
            "Option A — Cloudflare Tunnel (recommended for production):\n"
            "  1. Install cloudflared on this machine.\n"
            "  2. Run: cloudflared tunnel login\n"
            "  3. Run: cloudflared tunnel create <name>\n"
            "  4. Create a CNAME record in your DNS dashboard:\n"
            "         verify.yourdomain.com  →  <tunnel-uuid>.cfargotunnel.com\n"
            "  5. Create config.yml:\n"
            "         tunnel: <uuid>\n"
            "         credentials-file: C:\\Users\\...\\<uuid>.json\n"
            "         ingress:\n"
            "           - hostname: verify.yourdomain.com\n"
            "             service: http://localhost:8765\n"
            "           - service: http_status:404\n"
            "  6. Run: cloudflared tunnel run <name>\n"
            "  7. Set Public Verification URL to https://verify.yourdomain.com\n\n"
            "Option B — Local network only (no public internet):\n"
            "  Leave Public Verification URL blank. Links will use this machine's\n"
            "  hostname automatically. Users must be on the same network.\n\n"
            "Option C — Reverse proxy / VPN:\n"
            "  Point your reverse proxy to http://localhost:<port> and set the\n"
            "  Public Verification URL to the public-facing HTTPS address.\n\n"
            "Changes take effect immediately for new tokens (no restart needed)."
        )
        layout.addWidget(guide)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return w

    def _test_public_url(self) -> None:
        import urllib.request
        port = self.verify_port.value()
        public_url = self.verify_url.text().strip()

        # Step 1: test the local embedded server (always works if the app is running)
        local_ok = False
        local_error = ""
        try:
            with urllib.request.urlopen(
                f"http://localhost:{port}/verify", timeout=5
            ) as resp:
                local_ok = resp.status in (200, 400)
        except Exception as e:
            local_error = str(e)

        # Step 2: attempt the public URL using /health — always returns 200 with no token needed.
        # May fail on this machine if internal AD DNS can't resolve the Cloudflare hostname.
        public_status = ""
        health_url = ""
        if public_url:
            health_url = public_url.rstrip("/") + "/health"
            try:
                with urllib.request.urlopen(health_url, timeout=8) as resp:
                    public_status = "reachable" if resp.status == 200 else f"HTTP {resp.status}"
            except Exception as e:
                err = str(e)
                if "getaddrinfo" in err or "Name or service" in err or "11001" in err:
                    public_status = "dns_internal"
                else:
                    public_status = f"error: {err}"

        # Build result message
        lines = []
        if local_ok:
            lines.append(f"Local server (port {port}):  RUNNING")
        else:
            lines.append(
                f"Local server (port {port}):  NOT REACHABLE\n"
                f"  {local_error}\n"
                f"  The embedded verification server may not have started.\n"
                f"  Restart the app and check for port conflicts."
            )

        if public_url:
            lines.append("")
            if public_status == "reachable":
                lines.append(f"Public URL ({public_url}):  REACHABLE\n"
                             f"  Tunnel is working correctly.")
                self._current_url_label.setText(f"Current link base URL: {public_url}")
            elif public_status == "dns_internal":
                lines.append(
                    f"Public URL — DNS not resolved from this server.\n\n"
                    f"This is normal: your server's internal AD DNS cannot look up\n"
                    f"the Cloudflare hostname. This does NOT mean the tunnel is broken.\n\n"
                    f"To confirm the tunnel is working, open this URL in a browser\n"
                    f"on your phone or any machine outside this network:\n\n"
                    f"  {health_url}\n\n"
                    f"You should see a green 'Verification Server is Running' page.\n"
                    f"If you get DNS_PROBE_FINISHED_NXDOMAIN there too, the Cloudflare\n"
                    f"DNS CNAME record for {public_url.split('//')[-1]} has not been\n"
                    f"created yet — add it in your Cloudflare DNS dashboard."
                )
            else:
                lines.append(f"Public URL ({public_url}):  {public_status}")

        msg = "\n".join(lines)
        if local_ok:
            QMessageBox.information(self, "Server Status", msg)
        else:
            QMessageBox.warning(self, "Server Status", msg)

    def _autostart_enabled(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, "ProductLicenseTimer")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _set_autostart(self, enable: bool) -> None:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            pythonw = Path(sys.executable).parent / "pythonw.exe"
            main_py = Path(__file__).parent.parent / "main.py"
            cmd = f'"{pythonw}" "{main_py}" --minimized'
            winreg.SetValueEx(key, "ProductLicenseTimer", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "ProductLicenseTimer")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)

    # ----------------------------------------------------------------- Save
    def _persist_smtp(self) -> None:
        pairs = [
            ("SMTP_HOST", self.smtp_host.text().strip()),
            ("SMTP_PORT", str(self.smtp_port.value())),
            ("SMTP_USER", self.smtp_user.text().strip()),
            ("SMTP_PASSWORD", self.smtp_pass.text()),
            ("SMTP_TLS", "true" if self.smtp_tls.isChecked() else "false"),
            ("SENDER_NAME", self.sender_name.text().strip()),
        ]
        ENV_PATH.touch()
        for key, val in pairs:
            set_key(str(ENV_PATH), key, val)

    def _persist(self) -> None:
        """Write current field values to config files and .env."""
        min_v = self.min_spin.value()
        max_v = self.max_spin.value()
        interval = max(min_v, min(max_v, self.interval_spin.value()))

        app_cfg: dict = {
            "timer_interval_seconds": interval,
            "timer_min_seconds": min_v,
            "timer_max_seconds": max_v,
            "verification_server_port": (
                self.verify_port.value() if self._is_admin
                else self._app_cfg.get("verification_server_port", 8765)
            ),
            "verification_server_url": (
                self.verify_url.text().strip() if self._is_admin
                else self._app_cfg.get("verification_server_url", "")
            ),
        }
        _save(APP_CONFIG_PATH, app_cfg)
        if self._is_admin:
            self._persist_smtp()

    def _on_save(self) -> None:
        min_v = self.min_spin.value()
        max_v = self.max_spin.value()
        interval = self.interval_spin.value()
        if min_v > max_v:
            QMessageBox.warning(self, "Invalid", "Minimum interval cannot exceed maximum.")
            return
        if not (min_v <= interval <= max_v):
            QMessageBox.warning(
                self, "Invalid",
                f"Interval must be between {min_v} and {max_v} seconds."
            )
            return
        self._persist()
        self._set_autostart(self.autostart_check.isChecked())
        self.accept()

    def get_app_config(self) -> dict:
        """Return the saved app config (reads from file)."""
        return _load(APP_CONFIG_PATH, _APP_DEFAULTS)

    def get_email_config(self) -> dict:
        """Return the saved email config (reads from file)."""
        return _load(EMAIL_CONFIG_PATH, _EMAIL_DEFAULTS)
