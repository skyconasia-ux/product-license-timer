"""
Embedded HTTP verification server.

Runs as a daemon thread inside the app. New users click the emailed link,
which opens a browser page where they set their own password. The server
writes directly to the database via SQLAlchemy.

Binds to 0.0.0.0 so it is reachable from other machines on the same network.
Default port: 8765 (configurable via config/app_config.json).
"""
from __future__ import annotations
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_server: HTTPServer | None = None
_port: int = 8765

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "app_config.json"
_DEFAULT_PORT = 8765


def _load_config() -> tuple[int, str]:
    """Returns (port, public_url). public_url is '' if not configured."""
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        port = int(cfg.get("verification_server_port", _DEFAULT_PORT))
        url = cfg.get("verification_server_url", "").rstrip("/")
        return port, url
    except Exception:
        return _DEFAULT_PORT, ""


def get_base_url() -> str:
    """
    Public URL used in emailed links.
    Always reads live from app_config.json so changes in Settings take effect
    without restarting the app.  Falls back to the machine's network hostname.
    """
    _, public_url = _load_config()
    if public_url:
        return public_url
    try:
        host = socket.getfqdn()
    except Exception:
        host = "localhost"
    return f"http://{host}:{_port}"


def make_verify_link(token: str) -> str:
    return f"{get_base_url()}/verify?token={token}"


def make_email_change_link(token: str) -> str:
    return f"{get_base_url()}/change-email?token={token}"


def make_account_secure_link(token: str) -> str:
    return f"{get_base_url()}/secure-account?token={token}"


# ------------------------------------------------------------------ HTML helpers

def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} — Product License Timer</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         background:#f8fafc;display:flex;align-items:center;
         justify-content:center;min-height:100vh;padding:20px}}
    .card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;
           padding:40px;max-width:440px;width:100%}}
    h2{{color:#1e293b;font-size:20px;margin-bottom:8px}}
    .sub{{color:#64748b;font-size:14px;line-height:1.6;margin-bottom:24px}}
    .err{{color:#ef4444;font-size:13px;margin-bottom:14px;
          background:#fef2f2;border:1px solid #fecaca;
          border-radius:6px;padding:10px 14px}}
    .ok{{color:#16a34a;font-size:14px;font-weight:600;margin-bottom:12px}}
    label{{display:block;font-size:13px;color:#374151;
           font-weight:500;margin-bottom:4px}}
    input[type=password]{{width:100%;padding:9px 12px;border:1px solid #e2e8f0;
                          border-radius:6px;font-size:14px;outline:none;
                          margin-bottom:16px;color:#1e293b}}
    input[type=password]:focus{{border-color:#3b82f6;
                                box-shadow:0 0 0 3px rgba(59,130,246,.15)}}
    button{{width:100%;background:#3b82f6;color:#fff;border:none;
            border-radius:6px;padding:10px;font-size:14px;
            font-weight:600;cursor:pointer;margin-top:4px}}
    button:hover{{background:#2563eb}}
    .brand{{color:#94a3b8;font-size:12px;text-align:center;margin-top:24px}}
  </style>
</head>
<body>
  <div class="card">
    {body}
    <p class="brand">Product License Timer</p>
  </div>
</body>
</html>"""


def _form_page(token: str, email: str, error: str = "") -> str:
    err_html = f'<div class="err">{error}</div>' if error else ""
    safe_email = email.replace("<", "&lt;").replace(">", "&gt;")
    safe_token = token.replace('"', "&quot;")
    return _page("Set Your Password", f"""
    <h2>Activate Your Account</h2>
    <p class="sub">
      Welcome! Your account <strong>{safe_email}</strong> has been created.<br>
      Set a password below to complete your registration.
    </p>
    {err_html}
    <form method="POST" action="/verify">
      <input type="hidden" name="token" value="{safe_token}">
      <label>New Password</label>
      <input type="password" name="password" placeholder="Minimum 8 characters" required>
      <label>Confirm Password</label>
      <input type="password" name="confirm" placeholder="Repeat your password" required>
      <button type="submit">Activate Account</button>
    </form>
""")


def _success_page(email: str) -> str:
    safe_email = email.replace("<", "&lt;").replace(">", "&gt;")
    return _page("Account Activated", f"""
    <h2>Account Activated!</h2>
    <p class="ok">&#10003; Your account is ready.</p>
    <p class="sub">
      <strong>{safe_email}</strong> has been verified and your password is set.<br>
      Open the <strong>Product License Timer</strong> app and log in with your
      email address and the password you just created.
    </p>
""")


def _email_change_form_page(token: str, new_email: str, error: str = "") -> str:
    err_html = f'<div class="err">{error}</div>' if error else ""
    safe_email = new_email.replace("<", "&lt;").replace(">", "&gt;")
    safe_token = token.replace('"', "&quot;")
    return _page("Confirm Email Change", f"""
    <h2>Confirm Email Change</h2>
    <p class="sub">
      You are confirming that <strong>{safe_email}</strong> is your new email address.<br>
      For security, please set a new password to complete the change.
    </p>
    {err_html}
    <form method="POST" action="/change-email">
      <input type="hidden" name="token" value="{safe_token}">
      <label>New Password</label>
      <input type="password" name="password" placeholder="Minimum 8 characters" required>
      <label>Confirm Password</label>
      <input type="password" name="confirm" placeholder="Repeat your password" required>
      <button type="submit">Confirm &amp; Activate</button>
    </form>
""")


def _email_change_success_page(old_email: str, new_email: str) -> str:
    safe_new = new_email.replace("<", "&lt;").replace(">", "&gt;")
    return _page("Email Updated", f"""
    <h2>Email Address Updated!</h2>
    <p class="ok">&#10003; Your email has been changed successfully.</p>
    <p class="sub">
      Your account email is now <strong>{safe_new}</strong> and your password has been updated.<br>
      Open the <strong>Product License Timer</strong> app and log in with your new email and password.
    </p>
""")


def _secure_account_confirm_page(token: str, email: str) -> str:
    safe_email = email.replace("<", "&lt;").replace(">", "&gt;")
    safe_token = token.replace('"', "&quot;")
    return _page("Secure My Account", f"""
    <h2>Lock Your Account</h2>
    <p class="sub">
      You are about to lock the account <strong>{safe_email}</strong>.<br>
      Your account will be disabled immediately and your administrator will be
      notified to investigate and re-enable it.
    </p>
    <form method="POST" action="/secure-account">
      <input type="hidden" name="token" value="{safe_token}">
      <button type="submit" style="background:#ef4444;">
        &#128274; Lock My Account Now
      </button>
    </form>
""")


def _secure_account_success_page(email: str) -> str:
    safe_email = email.replace("<", "&lt;").replace(">", "&gt;")
    return _page("Account Locked", f"""
    <h2>Your Account Has Been Secured</h2>
    <p class="ok">&#10003; Account locked successfully.</p>
    <p class="sub">
      The account <strong>{safe_email}</strong> has been disabled and your
      administrator has been notified.<br><br>
      Your administrator will review the situation and contact you to restore access.
    </p>
""")


def _expired_page() -> str:
    return _page("Link Expired", """
    <h2>Link Expired or Invalid</h2>
    <p class="sub">
      This verification link has expired or has already been used.<br>
      Please ask your administrator to resend a new verification link.
    </p>
""")


def _error_page(msg: str) -> str:
    safe = msg.replace("<", "&lt;").replace(">", "&gt;")
    return _page("Error", f"""
    <h2>Something went wrong</h2>
    <p class="sub">{safe}<br>Please contact your administrator.</p>
""")


def _health_page() -> str:
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return _page("Health Check", f"""
    <h2>&#10003; Verification Server is Running</h2>
    <p class="ok">Tunnel and server are reachable.</p>
    <p class="sub">
      Product License Timer verification server is online.<br>
      Server time: {now}
    </p>
""")


# ------------------------------------------------------------------ Request handler

class _Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # suppress default stdout logging
        pass

    # ---- helpers ----

    def _send(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _token_email(self, token: str) -> str:
        """Look up the email for an unexpired EmailVerification token. Returns '' if not found."""
        from datetime import datetime
        from models.orm import EmailVerification, User
        from services.db_session import get_session
        session = get_session()
        try:
            ev = session.query(EmailVerification).filter_by(token=token).first()
            if not ev or ev.expires_at < datetime.now():
                return ""
            u = session.get(User, ev.user_id)
            return u.email if u else ""
        finally:
            session.close()

    def _secure_token_email(self, token: str) -> str:
        """Return the user email for a valid unused AccountSecureToken, else ''."""
        from datetime import datetime
        from models.orm import AccountSecureToken, User
        from services.db_session import get_session
        session = get_session()
        try:
            ast = session.query(AccountSecureToken).filter_by(token=token, used=False).first()
            if not ast or ast.expires_at < datetime.now():
                return ""
            u = session.get(User, ast.user_id)
            return u.email if u else ""
        finally:
            session.close()

    def _notify_superadmins(
        self, session, current_email: str, triggered_from_email: str
    ) -> None:
        """Email all superadmins that an account was self-locked via security link."""
        try:
            from models.orm import User, UserRole
            from services.notification_service import _send_smtp, get_smtp_config
            superadmins = session.query(User).filter_by(
                role=UserRole.superadmin, is_active=True
            ).all()
            recipients = [u.email for u in superadmins if u.email]
            if not recipients:
                return
            cfg = get_smtp_config()
            if not cfg.get("smtp_host") or not cfg.get("smtp_user"):
                return

            email_changed = triggered_from_email != current_email
            if email_changed:
                account_detail = (
                    f"    Current email  : {current_email}\n"
                    f"    Triggered from : {triggered_from_email}  "
                    f"(old email — recently replaced)\n\n"
                    f"The security trigger came from the OLD email address.\n"
                    f"This may indicate the email change itself was unauthorised.\n"
                    f"Investigate both the email change and any password changes.\n"
                )
            else:
                account_detail = (
                    f"    Account: {current_email}\n\n"
                    f"The user reported an unauthorised password change.\n"
                )

            _send_smtp(
                subject=f"SECURITY ALERT: Account locked — {current_email}",
                body=(
                    f"This is an automated security alert from Product License Timer.\n\n"
                    f"An account was automatically disabled because the user "
                    f"reported an unauthorised change:\n\n"
                    f"{account_detail}\n"
                    f"Action required:\n"
                    f"  1. Investigate the recent account activity.\n"
                    f"  2. Re-enable the account via the Users management page "
                    f"once you are satisfied it is safe to do so.\n"
                    f"  3. Contact the user to confirm.\n\n"
                    f"The account will remain disabled until an administrator re-enables it.\n"
                ),
                recipients=recipients,
                cfg=cfg,
            )
        except Exception:
            pass  # notification failure must never prevent the account lock

    def _notify_old_email_of_change(self, old_email: str, new_email: str) -> None:
        """
        After a successful email change, send a security notification to the OLD
        address with a Secure Account link. If clicked, the account is locked
        (now under the new email) and superadmins are alerted — with the full
        old→new trail for tracing.
        """
        try:
            from services.auth_service import create_account_secure_token
            from services.db_session import get_session
            from services.notification_service import _send_smtp, get_smtp_config
            cfg = get_smtp_config()
            if not cfg.get("smtp_host") or not cfg.get("smtp_user"):
                return

            # We need the user_id to create the token.
            # Look up by NEW email because the DB already has the updated address.
            from models.orm import User
            session = get_session()
            try:
                user = session.query(User).filter_by(email=new_email).first()
                if not user:
                    return
                # triggered_from_email = old_email so superadmins see the full trail
                secure_token = create_account_secure_token(
                    session, user.id, triggered_from_email=old_email
                )
            finally:
                session.close()

            secure_link = make_account_secure_link(secure_token)
            _send_smtp(
                subject="Your email address was changed — Product License Timer",
                body=(
                    f"Hello,\n\n"
                    f"The email address on your Product License Timer account "
                    f"has been successfully changed:\n\n"
                    f"    Old email: {old_email}\n"
                    f"    New email: {new_email}\n\n"
                    f"If you authorised this change, no action is needed.\n\n"
                    f"If you did NOT authorise this change, click the link below "
                    f"immediately to lock the account and alert your administrator:\n\n"
                    f"    {secure_link}\n\n"
                    f"Clicking the link will:\n"
                    f"  - Disable the account (the new email can no longer log in)\n"
                    f"  - Notify your administrator with the full change history\n\n"
                    f"This security link expires in 72 hours and can only be used once.\n"
                ),
                recipients=[old_email],
                cfg=cfg,
            )
        except Exception:
            pass  # must never block the main confirmation response

    def _email_change_token_new_email(self, token: str) -> str:
        """Look up the pending new_email for an unexpired EmailChangeToken. Returns '' if not found."""
        from datetime import datetime
        from models.orm import EmailChangeToken
        from services.db_session import get_session
        session = get_session()
        try:
            ect = session.query(EmailChangeToken).filter_by(token=token, used=False).first()
            if not ect or ect.expires_at < datetime.now():
                return ""
            return ect.new_email
        finally:
            session.close()

    # ---- GET ----

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        token = parse_qs(parsed.query).get("token", [""])[0]

        if path == "/health":
            self._send(200, _health_page())

        elif path == "/verify":
            if not token:
                self._send(400, _error_page("No token provided."))
                return
            email = self._token_email(token)
            if not email:
                self._send(400, _expired_page())
                return
            self._send(200, _form_page(token, email))

        elif path == "/change-email":
            if not token:
                self._send(400, _error_page("No token provided."))
                return
            new_email = self._email_change_token_new_email(token)
            if not new_email:
                self._send(400, _expired_page())
                return
            self._send(200, _email_change_form_page(token, new_email))

        elif path == "/secure-account":
            if not token:
                self._send(400, _error_page("No token provided."))
                return
            email = self._secure_token_email(token)
            if not email:
                self._send(400, _error_page(
                    "This link has already been used or has expired.<br>"
                    "If you believe your account was compromised, "
                    "contact your administrator directly."
                ))
                return
            self._send(200, _secure_account_confirm_page(token, email))

        else:
            self._send(404, _error_page("Page not found."))

    # ---- POST ----

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        params = parse_qs(raw)

        token    = params.get("token",    [""])[0]
        password = params.get("password", [""])[0]
        confirm  = params.get("confirm",  [""])[0]

        if path == "/verify":
            if not token:
                self._send(400, _error_page("Token is missing."))
                return
            email = self._token_email(token)
            if not email:
                self._send(400, _expired_page())
                return
            if len(password) < 8:
                self._send(200, _form_page(token, email, "Password must be at least 8 characters."))
                return
            if password != confirm:
                self._send(200, _form_page(token, email, "Passwords do not match."))
                return
            from services.auth_service import verify_and_set_password
            from services.db_session import get_session
            session = get_session()
            try:
                ok, verified_email = verify_and_set_password(session, token, password)
            finally:
                session.close()
            self._send(200, _success_page(verified_email)) if ok else self._send(400, _expired_page())

        elif path == "/change-email":
            if not token:
                self._send(400, _error_page("Token is missing."))
                return
            new_email = self._email_change_token_new_email(token)
            if not new_email:
                self._send(400, _expired_page())
                return
            if len(password) < 8:
                self._send(200, _email_change_form_page(token, new_email,
                                                        "Password must be at least 8 characters."))
                return
            if password != confirm:
                self._send(200, _email_change_form_page(token, new_email, "Passwords do not match."))
                return
            from services.auth_service import confirm_email_change_and_set_password
            from services.db_session import get_session
            session = get_session()
            try:
                ok, old_email, confirmed_new = confirm_email_change_and_set_password(
                    session, token, password)
            finally:
                session.close()
            if ok:
                self._send(200, _email_change_success_page(old_email, confirmed_new))
                # Send security notification to the OLD email with a Secure Account link
                self._notify_old_email_of_change(old_email, confirmed_new)
            else:
                self._send(400, _expired_page())

        elif path == "/secure-account":
            if not token:
                self._send(400, _error_page("Token is missing."))
                return
            from services.auth_service import trigger_account_secure
            from services.db_session import get_session
            session = get_session()
            try:
                ok, current_email, triggered_from = trigger_account_secure(session, token)
                if ok:
                    self._notify_superadmins(session, current_email, triggered_from)
            finally:
                session.close()
            if ok:
                self._send(200, _secure_account_success_page(current_email))
            else:
                self._send(400, _error_page(
                    "This link has already been used or has expired.<br>"
                    "Contact your administrator directly if needed."
                ))

        else:
            self._send(404, _error_page("Page not found."))


# ------------------------------------------------------------------ Public API

def start() -> bool:
    """
    Start the verification server in a background daemon thread.
    Reads port and optional public URL from app_config.json.
    Returns True if the server started, False if the port is already in use.
    """
    global _server, _port
    _port, _ = _load_config()
    try:
        _server = HTTPServer(("0.0.0.0", _port), _Handler)
    except OSError:
        _server = None
        return False
    t = threading.Thread(target=_server.serve_forever, daemon=True, name="VerifyServer")
    t.start()
    return True


def stop() -> None:
    global _server
    if _server:
        _server.shutdown()
        _server = None
