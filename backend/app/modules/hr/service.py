from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access.models import OrganizationScopeMode
from app.core.access.policy import (
    has_permission,
    organization_is_in_scope,
    require_permission_for_organization,
)
from app.core.access.service import authorized_organization_ids
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.organization.models import Organization
from app.core.people.models import Person, PersonOrganizationRelationship
from app.modules.hr.models import HREmployment, HRJobProfile, HRPosition
from app.modules.hr.permissions import HR_MANAGE, HR_READ
from app.modules.hr.schemas import (
    HREmploymentCreateRequest,
    HREmploymentStatusRequest,
    HREmploymentUpdateRequest,
    HRJobProfileCreateRequest,
    HRJobProfileUpdateRequest,
    HRPositionCreateRequest,
    HRPositionUpdateRequest,
    HRStatusRequest,
)


class HRNotFoundError(LookupError):
    pass


class HRConflictError(ValueError):
    pass


class HRValidationError(ValueError):
    pass


def _require_manage_for_resource(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    not_found_message: str,
) -> None:
    # Resource-ID endpoints intentionally hide existence across organization
    # boundaries instead of turning guessed IDs into a 403 oracle.
    if not has_permission(
        session,
        user_id=user_id,
        permission_code=HR_MANAGE,
        organization_id=organization_id,
    ):
        raise HRNotFoundError(not_found_message)


def _require_manage_for_profile_impact(
    session: Session,
    *,
    user_id: UUID,
    profile: HRJobProfile,
) -> None:
    impacted_ids = {profile.organization_id}
    impacted_ids.update(
        session.scalars(
            select(HRPosition.organization_id)
            .where(
                HRPosition.job_profile_id == profile.id,
                HRPosition.is_active.is_(True),
            )
            .distinct()
        ).all()
    )
    for organization_id in impacted_ids:
        if not has_permission(
            session,
            user_id=user_id,
            permission_code=HR_MANAGE,
            organization_id=organization_id,
        ):
            raise HRNotFoundError("Job profile not found.")


def _active_organization(session: Session, organization_id: UUID) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise HRNotFoundError("Organization not found.")
    return organization


def _organization_ancestor_ids(session: Session, organization: Organization) -> set[UUID]:
    result = {organization.id}
    visited: set[UUID] = set()
    current = organization
    while current.parent_id is not None:
        if current.id in visited:
            raise HRValidationError("Organization hierarchy contains a cycle.")
        visited.add(current.id)
        parent = current.parent or session.get(Organization, current.parent_id)
        if parent is None or not parent.is_active:
            break
        result.add(parent.id)
        current = parent
    return result


def _profile_applies_to_organization(
    session: Session,
    *,
    profile: HRJobProfile,
    organization_id: UUID,
) -> bool:
    if not profile.is_active:
        return False
    if profile.organization_id == organization_id:
        return True
    if profile.scope_mode is OrganizationScopeMode.SELF:
        return False
    return organization_is_in_scope(
        session,
        scope_organization_id=profile.organization_id,
        scope_mode=profile.scope_mode,
        target_organization_id=organization_id,
    )


def _get_job_profile(
    session: Session,
    profile_id: UUID,
    *,
    for_update: bool = False,
) -> HRJobProfile:
    statement = select(HRJobProfile).where(HRJobProfile.id == profile_id)
    if for_update:
        statement = statement.with_for_update()
    profile = session.scalar(statement)
    if profile is None:
        raise HRNotFoundError("Job profile not found.")
    return profile


def _position_statement(
    position_id: UUID, *, for_update: bool = False
) -> Select[tuple[HRPosition]]:
    statement = (
        select(HRPosition)
        .where(HRPosition.id == position_id)
        .options(selectinload(HRPosition.job_profile))
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_position(
    session: Session,
    position_id: UUID,
    *,
    for_update: bool = False,
) -> HRPosition:
    position = session.scalar(_position_statement(position_id, for_update=for_update))
    if position is None:
        raise HRNotFoundError("Position not found.")
    return position


def _employment_statement(
    employment_id: UUID, *, for_update: bool = False
) -> Select[tuple[HREmployment]]:
    statement = (
        select(HREmployment)
        .where(HREmployment.id == employment_id)
        .options(
            selectinload(HREmployment.person),
            selectinload(HREmployment.position),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_employment(
    session: Session,
    employment_id: UUID,
    *,
    for_update: bool = False,
) -> HREmployment:
    employment = session.scalar(_employment_statement(employment_id, for_update=for_update))
    if employment is None:
        raise HRNotFoundError("Employment record not found.")
    return employment


def list_hr_organizations_for_user(
    session: Session,
    *,
    user_id: UUID,
) -> list[dict[str, object]]:
    read_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=HR_READ,
    )
    manage_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=HR_MANAGE,
    )
    visible_ids = read_ids | manage_ids
    if not visible_ids:
        return []

    organizations = session.scalars(
        select(Organization)
        .where(Organization.id.in_(visible_ids), Organization.is_active.is_(True))
        .order_by(Organization.name, Organization.id)
    ).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "code": item.code,
            "organization_type": item.organization_type.value,
            "parent_id": item.parent_id,
            "is_active": item.is_active,
            "can_read": item.id in read_ids,
            "can_manage": item.id in manage_ids,
        }
        for item in organizations
    ]


def list_job_profiles_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
) -> list[HRJobProfile]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=HR_READ,
        organization_id=organization_id,
    )
    organization = _active_organization(session, organization_id)
    owner_ids = _organization_ancestor_ids(session, organization)

    statement = (
        select(HRJobProfile)
        .where(HRJobProfile.organization_id.in_(owner_ids))
        .order_by(HRJobProfile.title, HRJobProfile.code, HRJobProfile.id)
    )
    if not include_inactive:
        statement = statement.where(HRJobProfile.is_active.is_(True))

    profiles = session.scalars(statement).all()
    result: list[HRJobProfile] = []
    for profile in profiles:
        if profile.organization_id == organization_id:
            result.append(profile)
            continue
        if profile.scope_mode is OrganizationScopeMode.SELF_AND_DESCENDANTS:
            result.append(profile)
    return result


def create_job_profile(
    session: Session,
    *,
    actor: User,
    payload: HRJobProfileCreateRequest,
) -> HRJobProfile:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=HR_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    duplicate = session.scalar(
        select(HRJobProfile.id)
        .where(
            HRJobProfile.organization_id == payload.organization_id,
            HRJobProfile.code == payload.code,
        )
        .limit(1)
    )
    if duplicate is not None:
        raise HRConflictError("Job profile code already exists in this organization.")

    profile = HRJobProfile(
        organization_id=payload.organization_id,
        code=payload.code,
        title=payload.title,
        description=payload.description,
        scope_mode=payload.scope_mode,
        is_active=True,
    )
    session.add(profile)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=profile.organization_id,
        action="hr.job_profile.created",
        resource_type="hr_job_profile",
        resource_id=profile.id,
        after_state={
            "code": profile.code,
            "title": profile.title,
            "scope_mode": profile.scope_mode.value,
            "is_active": True,
        },
    )
    session.commit()
    session.refresh(profile)
    return profile


def update_job_profile(
    session: Session,
    *,
    actor: User,
    profile_id: UUID,
    payload: HRJobProfileUpdateRequest,
) -> HRJobProfile:
    profile = _get_job_profile(session, profile_id, for_update=True)
    _require_manage_for_profile_impact(
        session,
        user_id=actor.id,
        profile=profile,
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return profile

    if (
        changes.get("scope_mode") is OrganizationScopeMode.SELF
        and profile.scope_mode is OrganizationScopeMode.SELF_AND_DESCENDANTS
    ):
        active_descendant_position = session.scalar(
            select(HRPosition.id)
            .where(
                HRPosition.job_profile_id == profile.id,
                HRPosition.organization_id != profile.organization_id,
                HRPosition.is_active.is_(True),
            )
            .limit(1)
        )
        if active_descendant_position is not None:
            raise HRConflictError(
                "Deactivate descendant positions using this profile before narrowing its scope."
            )

    before = {
        "title": profile.title,
        "description": profile.description,
        "scope_mode": profile.scope_mode.value,
    }
    for field_name, value in changes.items():
        setattr(profile, field_name, value)
    after = {
        "title": profile.title,
        "description": profile.description,
        "scope_mode": profile.scope_mode.value,
    }
    if before == after:
        return profile

    record_audit_event(
        session,
        actor=actor,
        organization_id=profile.organization_id,
        action="hr.job_profile.updated",
        resource_type="hr_job_profile",
        resource_id=profile.id,
        before_state=before,
        after_state=after,
    )
    session.commit()
    session.refresh(profile)
    return profile


def change_job_profile_status(
    session: Session,
    *,
    actor: User,
    profile_id: UUID,
    payload: HRStatusRequest,
) -> HRJobProfile:
    profile = _get_job_profile(session, profile_id, for_update=True)
    _require_manage_for_profile_impact(
        session,
        user_id=actor.id,
        profile=profile,
    )
    if profile.is_active is payload.is_active:
        return profile

    if not payload.is_active:
        active_position = session.scalar(
            select(HRPosition.id)
            .where(
                HRPosition.job_profile_id == profile.id,
                HRPosition.is_active.is_(True),
            )
            .limit(1)
        )
        if active_position is not None:
            raise HRConflictError("Deactivate active positions using this job profile first.")

    before = {"is_active": profile.is_active}
    profile.is_active = payload.is_active
    record_audit_event(
        session,
        actor=actor,
        organization_id=profile.organization_id,
        action="hr.job_profile.status.changed",
        resource_type="hr_job_profile",
        resource_id=profile.id,
        before_state=before,
        after_state={"is_active": profile.is_active},
    )
    session.commit()
    session.refresh(profile)
    return profile


def list_positions_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
) -> list[HRPosition]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=HR_READ,
        organization_id=organization_id,
    )
    _active_organization(session, organization_id)
    statement = (
        select(HRPosition)
        .where(HRPosition.organization_id == organization_id)
        .options(selectinload(HRPosition.job_profile))
        .order_by(HRPosition.code, HRPosition.id)
    )
    if not include_inactive:
        statement = statement.where(HRPosition.is_active.is_(True))
    return list(session.scalars(statement).all())


def _validate_reports_to(
    session: Session,
    *,
    organization_id: UUID,
    reports_to_position_id: UUID | None,
    position_id: UUID | None = None,
) -> HRPosition | None:
    if reports_to_position_id is None:
        return None
    parent = _get_position(session, reports_to_position_id)
    if not parent.is_active or parent.organization_id != organization_id:
        raise HRValidationError(
            "reports_to_position_id must reference an active position in the same organization."
        )
    if position_id is not None and parent.id == position_id:
        raise HRValidationError("A position cannot report to itself.")

    visited: set[UUID] = set()
    current = parent
    while current.reports_to_position_id is not None:
        if current.id in visited:
            raise HRValidationError("Position reporting hierarchy contains a cycle.")
        visited.add(current.id)
        if position_id is not None and current.reports_to_position_id == position_id:
            raise HRValidationError("Position reporting hierarchy cannot contain a cycle.")
        next_position = session.get(HRPosition, current.reports_to_position_id)
        if next_position is None:
            break
        current = next_position
    return parent


def _validate_job_profile_for_position(
    session: Session,
    *,
    profile_id: UUID,
    organization_id: UUID,
) -> HRJobProfile:
    profile = _get_job_profile(session, profile_id)
    if not _profile_applies_to_organization(
        session,
        profile=profile,
        organization_id=organization_id,
    ):
        raise HRValidationError("Job profile is not active or does not apply to this organization.")
    return profile


def create_position(
    session: Session,
    *,
    actor: User,
    payload: HRPositionCreateRequest,
) -> HRPosition:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=HR_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    _validate_job_profile_for_position(
        session,
        profile_id=payload.job_profile_id,
        organization_id=payload.organization_id,
    )
    _validate_reports_to(
        session,
        organization_id=payload.organization_id,
        reports_to_position_id=payload.reports_to_position_id,
    )
    duplicate = session.scalar(
        select(HRPosition.id)
        .where(
            HRPosition.organization_id == payload.organization_id,
            HRPosition.code == payload.code,
        )
        .limit(1)
    )
    if duplicate is not None:
        raise HRConflictError("Position code already exists in this organization.")

    position = HRPosition(
        organization_id=payload.organization_id,
        job_profile_id=payload.job_profile_id,
        code=payload.code,
        name=payload.name,
        reports_to_position_id=payload.reports_to_position_id,
        is_active=True,
    )
    session.add(position)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=position.organization_id,
        action="hr.position.created",
        resource_type="hr_position",
        resource_id=position.id,
        after_state={
            "code": position.code,
            "name": position.name,
            "job_profile_id": str(position.job_profile_id),
            "reports_to_position_id": str(position.reports_to_position_id)
            if position.reports_to_position_id
            else None,
            "is_active": True,
        },
    )
    session.commit()
    return _get_position(session, position.id)


def update_position(
    session: Session,
    *,
    actor: User,
    position_id: UUID,
    payload: HRPositionUpdateRequest,
) -> HRPosition:
    position = _get_position(session, position_id, for_update=True)
    _require_manage_for_resource(
        session,
        user_id=actor.id,
        organization_id=position.organization_id,
        not_found_message="Position not found.",
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return position

    if "job_profile_id" in changes:
        _validate_job_profile_for_position(
            session,
            profile_id=changes["job_profile_id"],
            organization_id=position.organization_id,
        )
    if "reports_to_position_id" in changes:
        _validate_reports_to(
            session,
            organization_id=position.organization_id,
            reports_to_position_id=changes["reports_to_position_id"],
            position_id=position.id,
        )
    if "code" in changes and changes["code"] != position.code:
        duplicate = session.scalar(
            select(HRPosition.id)
            .where(
                HRPosition.organization_id == position.organization_id,
                HRPosition.code == changes["code"],
                HRPosition.id != position.id,
            )
            .limit(1)
        )
        if duplicate is not None:
            raise HRConflictError("Position code already exists in this organization.")

    before = {
        "job_profile_id": str(position.job_profile_id),
        "code": position.code,
        "name": position.name,
        "reports_to_position_id": str(position.reports_to_position_id)
        if position.reports_to_position_id
        else None,
    }
    for field_name, value in changes.items():
        setattr(position, field_name, value)
    after = {
        "job_profile_id": str(position.job_profile_id),
        "code": position.code,
        "name": position.name,
        "reports_to_position_id": str(position.reports_to_position_id)
        if position.reports_to_position_id
        else None,
    }
    if before == after:
        return position

    record_audit_event(
        session,
        actor=actor,
        organization_id=position.organization_id,
        action="hr.position.updated",
        resource_type="hr_position",
        resource_id=position.id,
        before_state=before,
        after_state=after,
    )
    session.commit()
    return _get_position(session, position.id)


def change_position_status(
    session: Session,
    *,
    actor: User,
    position_id: UUID,
    payload: HRStatusRequest,
) -> HRPosition:
    position = _get_position(session, position_id, for_update=True)
    _require_manage_for_resource(
        session,
        user_id=actor.id,
        organization_id=position.organization_id,
        not_found_message="Position not found.",
    )
    if position.is_active is payload.is_active:
        return position

    if not payload.is_active:
        active_employment = session.scalar(
            select(HREmployment.id)
            .where(
                HREmployment.position_id == position.id,
                HREmployment.is_active.is_(True),
            )
            .limit(1)
        )
        if active_employment is not None:
            raise HRConflictError("End the active employment occupying this position first.")
        active_child = session.scalar(
            select(HRPosition.id)
            .where(
                HRPosition.reports_to_position_id == position.id,
                HRPosition.is_active.is_(True),
            )
            .limit(1)
        )
        if active_child is not None:
            raise HRConflictError(
                "Reassign active child positions before deactivating this position."
            )
    else:
        _validate_job_profile_for_position(
            session,
            profile_id=position.job_profile_id,
            organization_id=position.organization_id,
        )
        _validate_reports_to(
            session,
            organization_id=position.organization_id,
            reports_to_position_id=position.reports_to_position_id,
            position_id=position.id,
        )

    before = {"is_active": position.is_active}
    position.is_active = payload.is_active
    record_audit_event(
        session,
        actor=actor,
        organization_id=position.organization_id,
        action="hr.position.status.changed",
        resource_type="hr_position",
        resource_id=position.id,
        before_state=before,
        after_state={"is_active": position.is_active},
    )
    session.commit()
    return _get_position(session, position.id)


def _validate_person_for_employment(
    session: Session,
    *,
    person_id: UUID,
    organization_id: UUID,
    effective_date: date | None = None,
    for_update: bool = False,
) -> Person:
    statement = select(Person).where(Person.id == person_id)
    if for_update:
        statement = statement.with_for_update()
    person = session.scalar(statement)
    if person is None or not person.is_active:
        raise HRNotFoundError("Person not found.")
    relation_date = effective_date or date.today()
    active_relationship = session.scalar(
        select(PersonOrganizationRelationship.id)
        .where(
            PersonOrganizationRelationship.person_id == person_id,
            PersonOrganizationRelationship.organization_id == organization_id,
            PersonOrganizationRelationship.is_active.is_(True),
            or_(
                PersonOrganizationRelationship.start_date.is_(None),
                PersonOrganizationRelationship.start_date <= relation_date,
            ),
            or_(
                PersonOrganizationRelationship.end_date.is_(None),
                PersonOrganizationRelationship.end_date >= relation_date,
            ),
        )
        .limit(1)
    )
    if active_relationship is None:
        raise HRValidationError(
            "Person must have an active relationship with the organization before "
            "an employment record can be created."
        )
    return person


def _validate_position_for_employment(
    session: Session,
    *,
    position_id: UUID | None,
    organization_id: UUID,
    exclude_employment_id: UUID | None = None,
) -> HRPosition | None:
    if position_id is None:
        return None
    position = _get_position(session, position_id, for_update=True)
    if position.organization_id != organization_id or not position.is_active:
        raise HRValidationError(
            "Position must be active and belong to the employment organization."
        )
    occupied_statement = select(HREmployment.id).where(
        HREmployment.position_id == position.id,
        HREmployment.is_active.is_(True),
    )
    if exclude_employment_id is not None:
        occupied_statement = occupied_statement.where(HREmployment.id != exclude_employment_id)
    occupied = session.scalar(occupied_statement.limit(1))
    if occupied is not None:
        raise HRConflictError("Position already has an active employment.")
    return position


def list_people_for_hr(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> list[Person]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=HR_READ,
        organization_id=organization_id,
    )
    _active_organization(session, organization_id)
    statement = (
        select(Person)
        .join(PersonOrganizationRelationship)
        .where(
            Person.is_active.is_(True),
            PersonOrganizationRelationship.organization_id == organization_id,
            PersonOrganizationRelationship.is_active.is_(True),
            or_(
                PersonOrganizationRelationship.start_date.is_(None),
                PersonOrganizationRelationship.start_date <= date.today(),
            ),
            or_(
                PersonOrganizationRelationship.end_date.is_(None),
                PersonOrganizationRelationship.end_date >= date.today(),
            ),
        )
        .distinct()
        .order_by(Person.last_name, Person.first_name, Person.id)
    )
    return list(session.scalars(statement).all())


def list_employments_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
) -> list[HREmployment]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=HR_READ,
        organization_id=organization_id,
    )
    _active_organization(session, organization_id)
    statement = (
        select(HREmployment)
        .where(HREmployment.organization_id == organization_id)
        .options(
            selectinload(HREmployment.person),
            selectinload(HREmployment.position),
        )
        .order_by(HREmployment.is_active.desc(), HREmployment.start_date.desc(), HREmployment.id)
    )
    if not include_inactive:
        statement = statement.where(HREmployment.is_active.is_(True))
    return list(session.scalars(statement).all())


def create_employment(
    session: Session,
    *,
    actor: User,
    payload: HREmploymentCreateRequest,
) -> HREmployment:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=HR_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    _validate_person_for_employment(
        session,
        person_id=payload.person_id,
        organization_id=payload.organization_id,
        effective_date=payload.start_date,
        for_update=True,
    )

    existing_active = session.scalar(
        select(HREmployment.id)
        .where(
            HREmployment.person_id == payload.person_id,
            HREmployment.organization_id == payload.organization_id,
            HREmployment.is_active.is_(True),
        )
        .limit(1)
    )
    if existing_active is not None:
        raise HRConflictError("Person already has an active employment in this organization.")

    _validate_position_for_employment(
        session,
        position_id=payload.position_id,
        organization_id=payload.organization_id,
    )
    if payload.employment_number is not None:
        duplicate_number = session.scalar(
            select(HREmployment.id)
            .where(
                HREmployment.organization_id == payload.organization_id,
                HREmployment.employment_number == payload.employment_number,
            )
            .limit(1)
        )
        if duplicate_number is not None:
            raise HRConflictError("Employment number already exists in this organization.")

    employment = HREmployment(
        organization_id=payload.organization_id,
        person_id=payload.person_id,
        position_id=payload.position_id,
        employment_number=payload.employment_number,
        employment_type=payload.employment_type,
        start_date=payload.start_date,
        end_date=None,
        is_active=True,
    )
    session.add(employment)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=employment.organization_id,
        action="hr.employment.created",
        resource_type="hr_employment",
        resource_id=employment.id,
        after_state={
            "person_id": str(employment.person_id),
            "position_id": str(employment.position_id) if employment.position_id else None,
            "employment_number": employment.employment_number,
            "employment_type": employment.employment_type.value,
            "start_date": employment.start_date.isoformat(),
            "is_active": True,
        },
    )
    session.commit()
    return _get_employment(session, employment.id)


def update_employment(
    session: Session,
    *,
    actor: User,
    employment_id: UUID,
    payload: HREmploymentUpdateRequest,
) -> HREmployment:
    employment = _get_employment(session, employment_id, for_update=True)
    _require_manage_for_resource(
        session,
        user_id=actor.id,
        organization_id=employment.organization_id,
        not_found_message="Employment record not found.",
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return employment

    if "position_id" in changes:
        _validate_position_for_employment(
            session,
            position_id=changes["position_id"],
            organization_id=employment.organization_id,
            exclude_employment_id=employment.id,
        )
    if "employment_number" in changes and changes["employment_number"] is not None:
        duplicate_number = session.scalar(
            select(HREmployment.id)
            .where(
                HREmployment.organization_id == employment.organization_id,
                HREmployment.employment_number == changes["employment_number"],
                HREmployment.id != employment.id,
            )
            .limit(1)
        )
        if duplicate_number is not None:
            raise HRConflictError("Employment number already exists in this organization.")

    candidate_start = changes.get("start_date", employment.start_date)
    if "start_date" in changes:
        _validate_person_for_employment(
            session,
            person_id=employment.person_id,
            organization_id=employment.organization_id,
            effective_date=candidate_start,
        )
    if employment.end_date is not None and employment.end_date < candidate_start:
        raise HRValidationError("start_date cannot be after the recorded end_date.")

    before = {
        "position_id": str(employment.position_id) if employment.position_id else None,
        "employment_number": employment.employment_number,
        "employment_type": employment.employment_type.value,
        "start_date": employment.start_date.isoformat(),
    }
    for field_name, value in changes.items():
        setattr(employment, field_name, value)
    after = {
        "position_id": str(employment.position_id) if employment.position_id else None,
        "employment_number": employment.employment_number,
        "employment_type": employment.employment_type.value,
        "start_date": employment.start_date.isoformat(),
    }
    if before == after:
        return employment

    record_audit_event(
        session,
        actor=actor,
        organization_id=employment.organization_id,
        action="hr.employment.updated",
        resource_type="hr_employment",
        resource_id=employment.id,
        before_state=before,
        after_state=after,
    )
    session.commit()
    return _get_employment(session, employment.id)


def change_employment_status(
    session: Session,
    *,
    actor: User,
    employment_id: UUID,
    payload: HREmploymentStatusRequest,
) -> HREmployment:
    employment = _get_employment(session, employment_id, for_update=True)
    _require_manage_for_resource(
        session,
        user_id=actor.id,
        organization_id=employment.organization_id,
        not_found_message="Employment record not found.",
    )
    if employment.is_active is payload.is_active:
        if (
            not payload.is_active
            and payload.end_date is not None
            and employment.end_date != payload.end_date
        ):
            if payload.end_date < employment.start_date:
                raise HRValidationError("end_date cannot be before start_date.")
            before: dict[str, object] = {
                "end_date": employment.end_date.isoformat() if employment.end_date else None
            }
            employment.end_date = payload.end_date
            record_audit_event(
                session,
                actor=actor,
                organization_id=employment.organization_id,
                action="hr.employment.end_date.corrected",
                resource_type="hr_employment",
                resource_id=employment.id,
                before_state=before,
                after_state={"end_date": employment.end_date.isoformat()},
            )
            session.commit()
            return _get_employment(session, employment.id)
        return employment

    before = {
        "is_active": employment.is_active,
        "end_date": employment.end_date.isoformat() if employment.end_date else None,
    }

    if payload.is_active:
        _validate_person_for_employment(
            session,
            person_id=employment.person_id,
            organization_id=employment.organization_id,
            for_update=True,
        )
        conflicting = session.scalar(
            select(HREmployment.id)
            .where(
                HREmployment.person_id == employment.person_id,
                HREmployment.organization_id == employment.organization_id,
                HREmployment.is_active.is_(True),
                HREmployment.id != employment.id,
            )
            .limit(1)
        )
        if conflicting is not None:
            raise HRConflictError(
                "Person already has another active employment in this organization."
            )
        _validate_position_for_employment(
            session,
            position_id=employment.position_id,
            organization_id=employment.organization_id,
            exclude_employment_id=employment.id,
        )
        employment.is_active = True
        employment.end_date = None
    else:
        end_date = payload.end_date or date.today()
        if end_date < employment.start_date:
            raise HRValidationError("end_date cannot be before start_date.")
        employment.is_active = False
        employment.end_date = end_date

    record_audit_event(
        session,
        actor=actor,
        organization_id=employment.organization_id,
        action="hr.employment.status.changed",
        resource_type="hr_employment",
        resource_id=employment.id,
        before_state=before,
        after_state={
            "is_active": employment.is_active,
            "end_date": employment.end_date.isoformat() if employment.end_date else None,
        },
    )
    session.commit()
    return _get_employment(session, employment.id)
