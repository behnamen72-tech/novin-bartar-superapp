from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.identity.models import User


def get_user_by_login(session: Session, login: str) -> User | None:
    normalized = login.strip().lower()
    if not normalized:
        return None

    if "@" in normalized:
        statement = select(User).where(func.lower(User.email) == normalized)
    else:
        statement = select(User).where(func.lower(User.username) == normalized)

    return session.scalar(statement)
