from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.access.policy import has_permission
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db


def require_permission(permission_code: str) -> Callable[..., User]:
    def dependency(
        organization_id: Annotated[UUID, Path()],
        current_user: Annotated[User, Depends(get_current_user)],
        session: Annotated[Session, Depends(get_db)],
    ) -> User:
        allowed = has_permission(
            session,
            user_id=current_user.id,
            permission_code=permission_code,
            organization_id=organization_id,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action in this organization.",
            )
        return current_user

    return dependency
