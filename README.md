# Product License Timer

A desktop application for tracking trial software license expiry dates — with real-time countdowns, colour-coded alerts, email notifications, and Windows system tray support.

![Python](https://img.shields.io/badge/Python-3.13-blue) ![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## Download (Windows)

**No Python required** — download the pre-built executable from the [Releases](../../releases/latest) page:

1. Download `ProductLicenseTimer.zip` from the latest release
2. Extract the zip
3. Run `ProductLicenseTimer.exe`

---

## Features

- Track trial licenses for software products (Equitrac, PaperCut, YSoft SafeQ, AWMS, etc.)
- Real-time countdown per product (days, hours, minutes, seconds)
- Colour-coded rows: 🟢 OK → 🟡 Monitor → 🟠 Warning → 🔴 Critical → ⬛ Expired
- Email alerts at **15, 10, and 5 day** thresholds (no duplicate sends)
- "Expired for: Xd Xh Xm Xs" counter on expired entries
- Add / Edit / Delete products with a form dialog
- Clear all expired entries in one click
- Search and filter by product name, customer, or order number
- Sort by any column
- Export to CSV
- Backup database
- Configurable check interval (default 5 minutes, range 5 min – 5 days)
- Windows system tray support (minimize to tray, double-click to restore)
- Auto-start on Windows boot (optional, via Settings)

---

## Run from Source

### Requirements

- Python 3.10+
- Windows (for system tray and auto-start features)

### Setup

```bash
git clone https://github.com/skyconasia-ux/product-license-timer.git
cd product-license-timer
pip install -r requirements.txt
python main.py
```

### Run tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

---

## Configuration

### Email / SMTP

Open the app → **Settings → Email / SMTP** tab. Fill in:

| Field | Example |
|---|---|
| SMTP Host | `smtp.gmail.com` or `smtp.office365.com` |
| SMTP Port | `587` (TLS) |
| Username | `yourname@gmail.com` |
| Password | App password (not your login password) |
| Recipients | Add one or more alert recipients |

Click **Test Connection** to verify before relying on alerts.

> **Gmail users:** Generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) — do not use your regular Gmail password.

### Timer Interval

Settings → Timer tab. Default: **300 seconds (5 minutes)**. Accepted range: 300s – 432000s (5 days). Changes apply immediately without restart.

---

## Project Structure

```
product-license-timer/
├── main.py                    # Entry point
├── config/
│   ├── app_config.json        # Timer settings
│   └── email_config.json      # SMTP credentials (fill in)
├── models/database.py         # SQLite schema
├── services/
│   ├── database_service.py    # Product CRUD
│   ├── notification_service.py# Email alerts
│   └── timer_service.py       # QTimer engine
├── ui/
│   ├── main_window.py         # Main window
│   ├── product_table.py       # Countdown table
│   ├── product_form.py        # Add/Edit dialog
│   └── settings_dialog.py     # Settings
└── utils/
    ├── date_utils.py          # Date math
    └── csv_exporter.py        # CSV export
```

---

## License

MIT
