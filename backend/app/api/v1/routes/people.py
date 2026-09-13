from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.permissions import PEOPLE_MANAGE
from app.core.access.policy import AuthorizationError
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.core.people.schemas import (
    PersonCreateRequest,
    PersonListItem,
    PersonRelationshipCreateRequest,
    PersonRelationshipItem,
    PersonRelationshipStatusRequest,
    PersonStatusRequest,
    PersonUpdateRequest,
)
from app.core.people.service import (
    PersonConflictError,
    PersonNotFoundError,
    PersonRelationshipNotFoundError,
    add_person_relationship,
    change_person_relationship_status,
    change_person_status,
    create_person,
    get_person_for_user,
    list_people_for_user,
    update_person,
)
from app.db.session import get_db

router = APIRouter(prefix="/people", tags=["people"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, (PersonNotFoundError, PersonRelationshipNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PersonConflictError) or isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[PersonListItem])
def list_people(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[PersonListItem]:
    return list_people_for_user(session, user_id=current_user.id)


@router.get("/{person_id}", response_model=PersonListItem)
def get_person(
    person_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PersonListItem:
    try:
        return get_person_for_user(session, user_id=current_user.id, person_id=person_id)
    except PersonNotFoundError as exc:
        raise _translate_error(exc) from exc


@router.post("", response_model=PersonListItem, status_code=status.HTTP_201_CREATED)
def create_person_endpoint(
    payload: PersonCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PersonListItem:
    try:
        person = create_person(session, actor=current_user, payload=payload)
        return get_person_for_user(session, user_id=current_user.id, person_id=person.id, permission_code=PEOPLE_MANAGE)
    except (AuthorizationError, PersonNotFoundError, PersonConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch("/{person_id}", response_model=PersonListItem)
def update_person_endpoint(
    person_id: UUID,
    payload: PersonUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PersonListItem:
    try:
        person = update_person(session, actor=current_user, person_id=person_id, payload=payload)
        return get_person_for_user(session, user_id=current_user.id, person_id=person.id, permission_code=PEOPLE_MANAGE)
    except (AuthorizationError, PersonNotFoundError, PersonConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch("/{person_id}/status", response_model=PersonListItem)
def change_person_status_endpoint(
    person_id: UUID,
    payload: PersonStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PersonListItem:
    try:
        person = change_person_status(session, actor=current_user, person_id=person_id, payload=payload)
        return get_person_for_user(session, user_id=current_user.id, person_id=person.id, permission_code=PEOPLE_MANAGE)
    except (AuthorizationError, PersonNotFoundError, PersonConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.post("/{person_id}/relationships", response_model=PersonRelationshipItem, status_code=status.HTTP_201_CREATED)
def create_person_relationship_endpoint(
    person_id: UUID,
    payload: PersonRelationshipCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PersonRelationshipItem:
    try:
        relationship = add_person_relationship(session, actor=current_user, person_id=person_id, payload=payload)
        return PersonRelationshipItem(
            id=relationship.id,
            organization_id=relationship.organization_id,
            organization_name=relationship.organization.name,
            relationship_code=relationship.relationship_code,
            start_date=relationship.start_date,
            end_date=relationship.end_date,
            is_active=relationship.is_active,
        )
    except (AuthorizationError, PersonNotFoundError, PersonConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch("/{person_id}/relationships/{relationship_id}/status", response_model=PersonRelationshipItem)
def change_person_relationship_status_endpoint(
    person_id: UUID,
    relationship_id: UUID,
    payload: PersonRelationshipStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PersonRelationshipItem:
    try:
        relationship = change_person_relationship_status(
            session,
            actor=current_user,
            person_id=person_id,
            relationship_id=relationship_id,
            payload=payload,
        )
        return PersonRelationshipItem(
            id=relationship.id,
            organization_id=relationship.organization_id,
            organization_name=relationship.organization.name,
            relationship_code=relationship.relationship_code,
            start_date=relationship.start_date,
            end_date=relationship.end_date,
            is_active=relationship.is_active,
        )
    except (AuthorizationError, PersonNotFoundError, PersonRelationshipNotFoundError, PersonConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
