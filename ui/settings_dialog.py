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
    QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QLabel, QMessageBox,
)

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
    "sender_name": "License Tracker",
    "recipients": [],
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._app_cfg = _load(APP_CONFIG_PATH, _APP_DEFAULTS)
        self._email_cfg = _load(EMAIL_CONFIG_PATH, _EMAIL_DEFAULTS)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_timer_tab(), "Timer")
        self._tabs.addTab(self._build_email_tab(), "Email / SMTP")
        self._tabs.addTab(self._build_system_tab(), "System")

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
        w = QWidget()
        form = QFormLayout(w)

        self.smtp_host = QLineEdit(self._email_cfg.get("smtp_host", ""))
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(int(self._email_cfg.get("smtp_port", 587)))
        self.smtp_user = QLineEdit(self._email_cfg.get("smtp_user", ""))
        self.smtp_pass = QLineEdit(self._email_cfg.get("smtp_password", ""))
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

        self.sender_name = QLineEdit(self._email_cfg.get("sender_name", "License Tracker"))

        self.recipient_list = QListWidget()
        self.recipient_list.setMaximumHeight(100)
        for r in self._email_cfg.get("recipients", []):
            self.recipient_list.addItem(r)

        self.new_recipient = QLineEdit()
        self.new_recipient.setPlaceholderText("admin@company.com")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_recipient)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_recipient)
        add_row = QHBoxLayout()
        add_row.addWidget(self.new_recipient)
        add_row.addWidget(add_btn)
        add_row.addWidget(remove_btn)

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)

        form.addRow("SMTP Host", self.smtp_host)
        form.addRow("SMTP Port", self.smtp_port)
        form.addRow("Username", self.smtp_user)
        form.addRow("Password", pass_row)
        form.addRow("Sender Name", self.sender_name)
        form.addRow("Recipients", self.recipient_list)
        form.addRow("Add Recipient", add_row)
        form.addRow("", test_btn)
        return w

    def _add_recipient(self) -> None:
        email = self.new_recipient.text().strip()
        if email and "@" in email:
            self.recipient_list.addItem(email)
            self.new_recipient.clear()

    def _remove_recipient(self) -> None:
        for item in self.recipient_list.selectedItems():
            self.recipient_list.takeItem(self.recipient_list.row(item))

    def _test_connection(self) -> None:
        self._persist()  # save current values before testing
        from services.notification_service import NotificationService
        ok, msg = NotificationService().test_connection()
        if ok:
            QMessageBox.information(self, "Test Connection", msg)
        else:
            QMessageBox.warning(self, "Test Connection Failed", msg)

    # ----------------------------------------------------------------- System tab
    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.autostart_check = QCheckBox("Start with Windows (minimized to tray)")
        self.autostart_check.setChecked(self._autostart_enabled())
        layout.addWidget(self.autostart_check)
        layout.addStretch()
        return w

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
    def _persist(self) -> None:
        """Write current field values to config files."""
        min_v = self.min_spin.value()
        max_v = self.max_spin.value()
        interval = max(min_v, min(max_v, self.interval_spin.value()))

        _save(APP_CONFIG_PATH, {
            "timer_interval_seconds": interval,
            "timer_min_seconds": min_v,
            "timer_max_seconds": max_v,
        })
        _save(EMAIL_CONFIG_PATH, {
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": self.smtp_port.value(),
            "smtp_user": self.smtp_user.text().strip(),
            "smtp_password": self.smtp_pass.text(),
            "sender_name": self.sender_name.text().strip(),
            "recipients": [
                self.recipient_list.item(i).text()
                for i in range(self.recipient_list.count())
            ],
        })

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
