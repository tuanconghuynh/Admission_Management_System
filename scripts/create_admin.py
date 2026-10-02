import getpass
from sqlalchemy import or_
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def main():
    username = input("Admin username/email: ").strip()
    if not username:
        raise SystemExit("Username is required")
    password = getpass.getpass("Password (at least 12 characters): ")
    if len(password) < 12 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Password too short or confirmation mismatch")
    with SessionLocal.begin() as db:
        if db.query(User).filter(or_(User.username == username, User.email == username)).first():
            raise SystemExit("Account already exists")
        db.add(User(username=username, email=username if "@" in username else None, full_name="Administrator",
            password_hash=hash_password(password), role="Admin", is_active=True, must_change_password=True))
    print("Administrator created; change password on first login")


if __name__ == "__main__":
    main()
