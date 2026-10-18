from werkzeug.security import generate_password_hash
from app import app
from models import db, User

TEST_USERS = [
    ("admin1",   "Admin@123",   "admin",   "admin.email@mail.com"),
    ("analyst1", "Analyst@123", "analyst", "analyst1.email@mail.com"),
    ("analyst2", "Analyst@456", "analyst", "analyst2.email@mail.com"),
]

with app.app_context():
    db.create_all()   
    for username, password, role, email in TEST_USERS:
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, role=role)
            db.session.add(user)
        user.email = email
        user.role = role
        user.password_hash = generate_password_hash(password)  
    db.session.commit()
    print("Seeded users:", [u[0] for u in TEST_USERS])
