import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

from models import db, now, User, LoginAttempt, Dataset, DatasetAccess
from security import (generate_otp, send_otp_email, mask_email,
                      log_action, login_required, role_required)
import crypto_utils
from admin_routes import admin_bp          
from analyst_routes import analyst_bp     

OTP_LIFETIME = timedelta(minutes=2)  
MAX_RESENDS = 1                      
MAX_WRONG = 2                        

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SESSION_COOKIE_HTTPONLY"] = True      
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"     
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024   
db.init_app(app)
app.register_blueprint(admin_bp)
app.register_blueprint(analyst_bp)

try:
    crypto_utils.get_key()
except crypto_utils.CryptoConfigError as e:
    print("WARNING:", e, "- dataset uploads will fail until this is fixed.")


@app.errorhandler(413)
def file_too_large(error):
    if session.get("user_id"):
        log_action(session["user_id"], "UPLOAD_FAILED", "File exceeds the size limit", success=False)
    return jsonify(error="The file is too large (maximum 5 MB)."), 413


def get_pending_attempt():
    attempt_id = session.get("attempt_id")
    attempt = db.session.get(LoginAttempt, attempt_id) if attempt_id else None
    if attempt is None or attempt.status != "pending":
        return None
    return attempt


def end_attempt(attempt):
    attempt.status = "failed"
    db.session.commit()
    session.pop("attempt_id", None)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", ""))

    if not username or not password or role not in ("admin", "analyst"):
        return jsonify(error="Please fill in all fields."), 400

    user = User.query.filter_by(username=username).first()

    if (user is None or not user.is_active
            or not check_password_hash(user.password_hash, password)
            or user.role != role):                
        log_action(user.id if user else None, "LOGIN_FAILED", f"username={username[:50]}",
                   success=False)
        return jsonify(error="Invalid username, password or role."), 401

    LoginAttempt.query.filter_by(user_id=user.id, status="pending").update({"status": "replaced"})

    otp = generate_otp()
    attempt = LoginAttempt(user_id=user.id,
                           otp_hash=generate_password_hash(otp),  
                           expires_at=now() + OTP_LIFETIME)
    db.session.add(attempt)
    db.session.commit()

    try:
        send_otp_email(user.email, otp)         
    except Exception as e:
        print("EMAIL ERROR:", e)
        attempt.status = "failed"
        db.session.commit()
        return jsonify(error="Could not send the OTP email. Check the SMTP settings."), 500

    session.clear()
    session["attempt_id"] = attempt.id            
    log_action(user.id, "OTP_SENT", "")
    return jsonify(message="OTP sent", email=mask_email(user.email),
                   expires_in=int(OTP_LIFETIME.total_seconds()))

@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    attempt = get_pending_attempt()
    if attempt is None:
        return jsonify(error="Login session ended. Please log in again.", restart=True), 401

    code = str((request.get_json(silent=True) or {}).get("otp", "")).strip()
    if len(code) != 6 or not code.isdigit():
        return jsonify(error="Enter the 6-digit code."), 400

    if now() > attempt.expires_at:
        if attempt.resend_count >= MAX_RESENDS:    
            end_attempt(attempt)
            return jsonify(error="OTP expired. Please log in again.", restart=True), 401
        return jsonify(error="OTP expired. Click Resend."), 400

    if check_password_hash(attempt.otp_hash, code):
        attempt.status = "verified"
        db.session.commit()
        user = db.session.get(User, attempt.user_id)
        session.clear()
        session.permanent = True
        session["user_id"] = user.id             
        log_action(user.id, "LOGIN_SUCCESS", "")
        return jsonify(role=user.role, username=user.username)

    attempt.wrong_count += 1
    db.session.commit()
    log_action(attempt.user_id, "OTP_WRONG", f"wrong_count={attempt.wrong_count}", success=False)
    if attempt.wrong_count >= MAX_WRONG:
        end_attempt(attempt)
        return jsonify(error="Wrong OTP again. Login cancelled.", restart=True), 401
    return jsonify(error="Wrong OTP. 1 attempt left."), 401

@app.route("/api/resend-otp", methods=["POST"])
def resend_otp():
    attempt = get_pending_attempt()
    if attempt is None:
        return jsonify(error="Login session ended. Please log in again.", restart=True), 401
    if attempt.resend_count >= MAX_RESENDS:
        return jsonify(error="You already used your one resend."), 400

    user = db.session.get(User, attempt.user_id)
    otp = generate_otp()
    try:
        send_otp_email(user.email, otp)
    except Exception as e:
        print("EMAIL ERROR:", e)
        return jsonify(error="Could not send the OTP email."), 500

    attempt.otp_hash = generate_password_hash(otp)   
    attempt.expires_at = now() + OTP_LIFETIME
    attempt.resend_count += 1
    db.session.commit()
    log_action(user.id, "OTP_RESENT", "")
    return jsonify(message="New OTP sent", expires_in=int(OTP_LIFETIME.total_seconds()))

@app.route("/api/me")
@login_required
def me():
    return jsonify(username=g.user.username, role=g.user.role)


@app.route("/api/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        log_action(user_id, "LOGOUT", "")
    return jsonify(message="Logged out")

@app.route("/api/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    return jsonify(message=f"Welcome, admin {g.user.username}",
                   total_users=User.query.count(),
                   total_datasets=Dataset.query.count())


@app.route("/api/analyst/dashboard")
@role_required("analyst")
def analyst_dashboard():
    allowed = DatasetAccess.query.filter_by(user_id=g.user.id).count()
    return jsonify(message=f"Welcome, analyst {g.user.username}",
                   authorised_datasets=allowed)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
