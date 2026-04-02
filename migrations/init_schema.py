"""
Run once on a fresh SQL Server database.
Usage: python -m migrations.init_schema
"""
from __future__ import annotations
import secrets
import sys
import bcrypt
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os

load_dotenv()


def main() -> None:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    from models.orm import Base, User, UserRole
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    print("Tables created.")

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(engine)
    session = Session()

    existing = session.query(User).filter_by(role=UserRole.superadmin).first()
    if existing:
        print("Superadmin already exists. Skipping seed.")
        session.close()
        return

    email = input("Enter superadmin email: ").strip()
    if not email or "@" not in email:
        print("ERROR: Invalid email.")
        sys.exit(1)

    pw_hash = bcrypt.hashpw("FujiFilm_11111".encode(), bcrypt.gensalt(rounds=12)).decode()
    superadmin = User(
        email=email,
        password_hash=pw_hash,
        role=UserRole.superadmin,
        is_verified=True,
        is_active=True,
    )
    session.add(superadmin)
    session.commit()

    recovery_code = secrets.token_hex(16)
    recovery_path = os.path.join(os.path.dirname(__file__), ".recovery_code")
    with open(recovery_path, "w") as f:
        import hashlib
        f.write(hashlib.sha256(recovery_code.encode()).hexdigest())

    print(f"\nSuperadmin created: {email}")
    print(f"Default password:   FujiFilm_11111 (you will be forced to change this on first login)")
    print(f"\n*** RECOVERY CODE (store this securely — shown only once) ***")
    print(f"    {recovery_code}")
    print(f"*** END RECOVERY CODE ***\n")
    session.close()


if __name__ == "__main__":
    main()
