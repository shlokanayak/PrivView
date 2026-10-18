import os
import smtplib
import ssl
import secrets
from email.message import EmailMessage
from functools import wraps

from flask import g, has_request_context, jsonify, request, session
from models import db, User, ActivityLog

def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"


def send_otp_email(to_email, otp):
    sender = os.getenv("SMTP_USER")
    app_password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "")

    msg = EmailMessage()
    msg["Subject"] = "PrivView login code"
    msg["From"] = sender
    msg["To"] = to_email          
    msg.set_content(f"Your PrivView verification code is {otp}.\n"
                    "It expires in 2 minutes. Do not share it with anyone.")

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT")), timeout=15) as server:
        server.starttls(context=ssl.create_default_context())  
        server.login(sender, app_password)
        server.send_message(msg)


def mask_email(email):
    name, domain = email.split("@")
    return name[0] + "*" * (len(name) - 1) + "@" + domain


def log_action(user_id, action, details="", dataset_name=None, success=True, ip=None):
    if ip is None and has_request_context():
        ip = request.remote_addr
    user = db.session.get(User, user_id) if user_id else None
    db.session.add(ActivityLog(user_id=user_id, role=user.role if user else None,
                               action=action, details=str(details)[:500],
                               dataset_name=dataset_name, success=success, ip_address=ip))
    db.session.commit()

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        if user is None or not user.is_active:
            return jsonify(error="Please log in first."), 401
        g.user = user      
        return func(*args, **kwargs)
    return wrapper


def role_required(role):
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
