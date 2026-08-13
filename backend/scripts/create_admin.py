"""Create an admin user for local development and demos."""

import argparse
import sys

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import SessionLocal, init_db
from app.db.models import User


def create_admin(name: str, email: str, password: str) -> None:
    init_db()
    db: Session = SessionLocal()
    try:
        email = email.lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role == "admin":
                print(f"Admin already exists: {email}")
                return
            existing.role = "admin"
            existing.password_hash = hash_password(password)
            existing.name = name
            existing.email_verified = True
            db.commit()
            print(f"Updated existing user to admin: {email}")
            return

        admin = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            email_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin created: {email}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--name", default="College Admin")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    create_admin(args.name, args.email, args.password)


if __name__ == "__main__":
    main()
