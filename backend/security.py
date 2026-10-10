# security.py - all security helper code lives here:
#   1. OTP creation + email sending      (MFA)
#   2. login_required / role_required    (RBAC)
#   3. activity logging
import os
import smtplib
import ssl
import secrets
from email.message import EmailMessage
from functools import wraps

from flask import g, has_request_context, jsonify, request, session
from models import db, User, ActivityLog


# ---------- MFA helpers ----------

def generate_otp():
    """Return a random 6-digit code like '048213' (secrets = cryptographically safe)."""
    return f"{secrets.randbelow(1000000):06d}"


def send_otp_email(to_email, otp):
    """Send the OTP through Gmail SMTP. Sender details come from .env."""
    sender = os.getenv("SMTP_USER")
    app_password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "")

    msg = EmailMessage()
    msg["Subject"] = "PrivView login code"
    msg["From"] = sender
    msg["To"] = to_email          # always the email stored in the database
    msg.set_content(f"Your PrivView verification code is {otp}.\n"
                    "It expires in 2 minutes. Do not share it with anyone.")

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT")), timeout=15) as server:
        server.starttls(context=ssl.create_default_context())  # encrypt the connection
        server.login(sender, app_password)
        server.send_message(msg)


def mask_email(email):
    """a.student@gmail.com -> a*******@gmail.com (so the page doesn't reveal the full email)."""
    name, domain = email.split("@")
    return name[0] + "*" * (len(name) - 1) + "@" + domain


# ---------- Activity log ----------

def log_action(user_id, action, details="", dataset_name=None, success=True, ip=None):
    """Write one row to activity_logs. The background upload thread has no request,
    so it passes the ip address in itself."""
    if ip is None and has_request_context():
        ip = request.remote_addr
    user = db.session.get(User, user_id) if user_id else None
    db.session.add(ActivityLog(user_id=user_id, role=user.role if user else None,
                               action=action, details=str(details)[:500],
                               dataset_name=dataset_name, success=success, ip_address=ip))
    db.session.commit()


# ---------- RBAC decorators ----------

def login_required(func):
    """Route runs only if the session belongs to a real, active user in the database."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        if user is None or not user.is_active:
            return jsonify(error="Please log in first."), 401
        g.user = user      # the role comes from the DATABASE, not from the browser
        return func(*args, **kwargs)
    return wrapper


def role_required(role):
    """Route runs only if the logged-in user's DATABASE role equals `role`."""
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(*args, **kwargs):
            if g.user.role != role:
                log_action(g.user.id, "ACCESS_DENIED", f"{g.user.role} tried {request.path}",
                           success=False)
                return jsonify(error="You do not have permission for this."), 403
            return func(*args, **kwargs)
        return wrapper
    return decorator
