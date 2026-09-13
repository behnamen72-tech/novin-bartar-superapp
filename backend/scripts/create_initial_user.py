from getpass import getpass

from sqlalchemy import select

from app.core.identity.models import User
from app.core.identity.security import hash_password
from app.core.people.models import Person
from app.db.session import SessionLocal


def main() -> None:
    email = input("Login email: ").strip().lower()
    username = input("Username (optional): ").strip().lower() or None
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")

    with SessionLocal() as session:
        existing_email = session.scalar(
            select(User).where(User.email == email)
        )
        if existing_email is not None:
            raise SystemExit("A user with this email already exists.")

        if username is not None:
            existing_username = session.scalar(
                select(User).where(User.username == username)
            )
            if existing_username is not None:
                raise SystemExit("A user with this username already exists.")

        person = Person(
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        user = User(
            person=person,
            email=email,
            username=username,
            password_hash=hash_password(password),
        )

        session.add_all([person, user])
        session.commit()

        print(f"Created user: {user.email}")


if __name__ == "__main__":
    main()
