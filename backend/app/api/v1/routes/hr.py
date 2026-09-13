from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db
from app.modules.hr.schemas import (
    HREmploymentCreateRequest,
    HREmploymentResponse,
    HREmploymentStatusRequest,
    HREmploymentUpdateRequest,
    HRJobProfileCreateRequest,
    HRJobProfileResponse,
    HRJobProfileUpdateRequest,
    HROrganizationCapabilityResponse,
    HRPersonOptionResponse,
    HRPositionCreateRequest,
    HRPositionResponse,
    HRPositionUpdateRequest,
    HRStatusRequest,
)
from app.modules.hr.service import (
    HRConflictError,
    HRNotFoundError,
    HRValidationError,
    change_employment_status,
    change_job_profile_status,
    change_position_status,
    create_employment,
    create_job_profile,
    create_position,
    list_employments_for_user,
    list_hr_organizations_for_user,
    list_job_profiles_for_user,
    list_people_for_hr,
    list_positions_for_user,
    update_employment,
    update_job_profile,
    update_position,
)

router = APIRouter(prefix="/hr", tags=["hr"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, HRNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (HRConflictError, IntegrityError)):
        detail = str(exc) if not isinstance(exc, IntegrityError) else "HR write conflict."
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, (HRValidationError, ValueError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("/organizations", response_model=list[HROrganizationCapabilityResponse])
def list_hr_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[HROrganizationCapabilityResponse]:
    return [
        HROrganizationCapabilityResponse.model_validate(item)
        for item in list_hr_organizations_for_user(session, user_id=current_user.id)
    ]


@router.get("/job-profiles", response_model=list[HRJobProfileResponse])
def list_hr_job_profiles(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[HRJobProfileResponse]:
    try:
        items = list_job_profiles_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except (AuthorizationError, HRNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [HRJobProfileResponse.model_validate(item) for item in items]


@router.post(
    "/job-profiles",
    response_model=HRJobProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hr_job_profile(
    payload: HRJobProfileCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HRJobProfileResponse:
    try:
        item = create_job_profile(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HRJobProfileResponse.model_validate(item)


@router.patch("/job-profiles/{profile_id}", response_model=HRJobProfileResponse)
def patch_hr_job_profile(
    profile_id: UUID,
    payload: HRJobProfileUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HRJobProfileResponse:
    try:
        item = update_job_profile(
            session,
            actor=current_user,
            profile_id=profile_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HRJobProfileResponse.model_validate(item)


@router.post("/job-profiles/{profile_id}/status", response_model=HRJobProfileResponse)
def set_hr_job_profile_status(
    profile_id: UUID,
    payload: HRStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HRJobProfileResponse:
    try:
        item = change_job_profile_status(
            session,
            actor=current_user,
            profile_id=profile_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HRJobProfileResponse.model_validate(item)


@router.get("/positions", response_model=list[HRPositionResponse])
def list_hr_positions(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[HRPositionResponse]:
    try:
        items = list_positions_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except (AuthorizationError, HRNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [HRPositionResponse.model_validate(item) for item in items]


@router.post(
    "/positions",
    response_model=HRPositionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hr_position(
    payload: HRPositionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HRPositionResponse:
    try:
        item = create_position(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HRPositionResponse.model_validate(item)


@router.patch("/positions/{position_id}", response_model=HRPositionResponse)
def patch_hr_position(
    position_id: UUID,
    payload: HRPositionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HRPositionResponse:
    try:
        item = update_position(
            session,
            actor=current_user,
            position_id=position_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HRPositionResponse.model_validate(item)


@router.post("/positions/{position_id}/status", response_model=HRPositionResponse)
def set_hr_position_status(
    position_id: UUID,
    payload: HRStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HRPositionResponse:
    try:
        item = change_position_status(
            session,
            actor=current_user,
            position_id=position_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HRPositionResponse.model_validate(item)


@router.get("/people", response_model=list[HRPersonOptionResponse])
def list_hr_people(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[HRPersonOptionResponse]:
    try:
        items = list_people_for_hr(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
        )
    except (AuthorizationError, HRNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [HRPersonOptionResponse.model_validate(item) for item in items]


@router.get("/employments", response_model=list[HREmploymentResponse])
def list_hr_employments(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[HREmploymentResponse]:
    try:
        items = list_employments_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except (AuthorizationError, HRNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [HREmploymentResponse.model_validate(item) for item in items]


@router.post(
    "/employments",
    response_model=HREmploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hr_employment(
    payload: HREmploymentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HREmploymentResponse:
    try:
        item = create_employment(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HREmploymentResponse.model_validate(item)


@router.patch("/employments/{employment_id}", response_model=HREmploymentResponse)
def patch_hr_employment(
    employment_id: UUID,
    payload: HREmploymentUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HREmploymentResponse:
    try:
        item = update_employment(
            session,
            actor=current_user,
            employment_id=employment_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HREmploymentResponse.model_validate(item)


@router.post("/employments/{employment_id}/status", response_model=HREmploymentResponse)
def set_hr_employment_status(
    employment_id: UUID,
    payload: HREmploymentStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HREmploymentResponse:
    try:
        item = change_employment_status(
            session,
            actor=current_user,
            employment_id=employment_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        HRNotFoundError,
        HRConflictError,
        HRValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return HREmploymentResponse.model_validate(item)
