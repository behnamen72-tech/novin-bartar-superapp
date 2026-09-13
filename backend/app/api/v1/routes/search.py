from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.core.search.schemas import SearchEntityType, SearchResponse
from app.core.search.service import DEFAULT_TYPES, search_core
from app.db.session import get_db


router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    entity_type: Annotated[list[SearchEntityType] | None, Query()] = None,
    limit_per_type: Annotated[int, Query(ge=1, le=20)] = 8,
) -> SearchResponse:
    normalized = " ".join(q.strip().split())
    if len(normalized) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Search query must contain at least two non-whitespace characters.",
        )

    selected = tuple(dict.fromkeys(entity_type or DEFAULT_TYPES))
    return search_core(
        session,
        user_id=current_user.id,
        query=normalized,
        entity_types=selected,
        limit_per_type=limit_per_type,
    )
