# seed.py - creates the first test users (there is no signup page).
# 1) Change the e-mail addresses below to REAL inboxes you can open.
# 2) Run once:  python seed.py     (safe to run again, it updates the users)
from werkzeug.security import generate_password_hash
from app import app
from models import db, User

TEST_USERS = [
    # username,  password,      role,      email  <-- OTP goes here
    ("admin1",   "Admin@123",   "admin",   "your.admin.email@gmail.com"),
    ("analyst1", "Analyst@123", "analyst", "your.analyst.email@gmail.com"),
    ("analyst2", "Analyst@456", "analyst", "another.email@gmail.com"),
]

with app.app_context():
    db.create_all()   # safety net: creates missing tables if you skipped schema.sql
    for username, password, role, email in TEST_USERS:
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, role=role)
            db.session.add(user)
        user.email = email
        user.role = role
        user.password_hash = generate_password_hash(password)   # Werkzeug hashing
    db.session.commit()
    print("Seeded users:", [u[0] for u in TEST_USERS])
