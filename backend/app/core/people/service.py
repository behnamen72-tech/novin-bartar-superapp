from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.core.access.permissions import PEOPLE_MANAGE, PEOPLE_READ
from app.core.access.policy import AuthorizationError, require_permission_for_organization
from app.core.access.service import authorized_organization_ids
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.organization.models import Organization
from app.core.people.models import Person, PersonOrganizationRelationship
from app.core.people.schemas import (
    PersonCreateRequest,
    PersonListItem,
    PersonRelationshipCreateRequest,
    PersonRelationshipItem,
    PersonRelationshipStatusRequest,
    PersonStatusRequest,
    PersonUpdateRequest,
)


class PersonNotFoundError(LookupError):
    pass


class PersonRelationshipNotFoundError(LookupError):
    pass


class PersonConflictError(ValueError):
    pass


def _person_statement(person_id: UUID, *, for_update: bool = False) -> Select[tuple[Person]]:
    statement = (
        select(Person)
        .where(Person.id == person_id)
        .options(
            selectinload(Person.organization_relationships).selectinload(
                PersonOrganizationRelationship.organization
            ),
            selectinload(Person.user),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_person(session: Session, person_id: UUID, *, for_update: bool = False) -> Person:
    person = session.scalar(_person_statement(person_id, for_update=for_update))
    if person is None:
        raise PersonNotFoundError("Person not found.")
    return person


def _active_relationship_organization_ids(person: Person) -> set[UUID]:
    return {
        relationship.organization_id
        for relationship in person.organization_relationships
        if relationship.is_active and relationship.organization.is_active
    }


def _all_relationship_organization_ids(person: Person) -> set[UUID]:
    return {
        relationship.organization_id
        for relationship in person.organization_relationships
        if relationship.organization.is_active
    }


def require_people_manage_for_person(
    session: Session,
    *,
    actor_user_id: UUID,
    person: Person,
) -> set[UUID]:
    """Require control of every active organization relation of a shared Person.

    Person fields are global/shared across organizations. Allowing an admin of only
    one relationship to mutate the shared record could change another company's
    view. Relationship-specific writes are authorized separately against that one
    organization.
    """
    organization_ids = _active_relationship_organization_ids(person)
    if not organization_ids:
        organization_ids = _all_relationship_organization_ids(person)
    if not organization_ids:
        raise AuthorizationError("Permission denied.")

    for organization_id in organization_ids:
        require_permission_for_organization(
            session,
            user_id=actor_user_id,
            permission_code=PEOPLE_MANAGE,
            organization_id=organization_id,
        )
    return organization_ids


def _person_to_list_item(person: Person, visible_organization_ids: set[UUID]) -> PersonListItem:
    visible_relationships = [
        relationship
        for relationship in person.organization_relationships
        if relationship.organization_id in visible_organization_ids
        and relationship.organization.is_active
    ]
    return PersonListItem(
        id=person.id,
        first_name=person.first_name,
        last_name=person.last_name,
        email=person.email,
        phone=person.phone,
        is_active=person.is_active,
        relationships=[
            PersonRelationshipItem(
                id=relationship.id,
                organization_id=relationship.organization_id,
                organization_name=relationship.organization.name,
                relationship_code=relationship.relationship_code,
                start_date=relationship.start_date,
                end_date=relationship.end_date,
                is_active=relationship.is_active,
            )
            for relationship in sorted(
                visible_relationships,
                key=lambda item: (
                    item.organization.name,
                    item.relationship_code,
                    str(item.id),
                ),
            )
        ],
    )


def list_people_for_user(
    session: Session,
    *,
    user_id: UUID,
) -> list[PersonListItem]:
    organization_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=PEOPLE_READ,
    )
    if not organization_ids:
        return []

    statement = (
        select(Person)
        .options(
            selectinload(Person.organization_relationships).selectinload(
                PersonOrganizationRelationship.organization
            )
        )
        .order_by(Person.last_name, Person.first_name)
    )

    result: list[PersonListItem] = []
    for person in session.scalars(statement).all():
        item = _person_to_list_item(person, organization_ids)
        if item.relationships:
            result.append(item)
    return result


def get_person_for_user(
    session: Session,
    *,
    user_id: UUID,
    person_id: UUID,
    permission_code: str = PEOPLE_READ,
) -> PersonListItem:
    person = _get_person(session, person_id)
    allowed_org_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=permission_code,
    )
    item = _person_to_list_item(person, allowed_org_ids)
    if not item.relationships:
        # Generic not-found hides existence across organization boundaries.
        raise PersonNotFoundError("Person not found.")
    return item


def create_person(
    session: Session,
    *,
    actor: User,
    payload: PersonCreateRequest,
) -> Person:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=PEOPLE_MANAGE,
        organization_id=payload.organization_id,
    )
    organization = session.get(Organization, payload.organization_id)
    if organization is None or not organization.is_active:
        raise PersonNotFoundError("Organization not found.")

    person = Person(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        is_active=True,
    )
    relationship = PersonOrganizationRelationship(
        person=person,
        organization=organization,
        relationship_code=payload.relationship_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=True,
    )
    session.add_all([person, relationship])
    session.flush()

    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action="person.created",
        resource_type="person",
        resource_id=person.id,
        after_state={
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": person.email,
            "phone": person.phone,
            "is_active": person.is_active,
            "relationship_code": relationship.relationship_code,
            "relationship_id": str(relationship.id),
        },
    )
    session.commit()
    return _get_person(session, person.id)


def update_person(
    session: Session,
    *,
    actor: User,
    person_id: UUID,
    payload: PersonUpdateRequest,
) -> Person:
    person = _get_person(session, person_id, for_update=True)
    organization_ids = require_people_manage_for_person(
        session,
        actor_user_id=actor.id,
        person=person,
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return person

    before = {
        "first_name": person.first_name,
        "last_name": person.last_name,
        "email": person.email,
        "phone": person.phone,
    }
    for field_name, value in changes.items():
        setattr(person, field_name, value)
    after = {
        "first_name": person.first_name,
        "last_name": person.last_name,
        "email": person.email,
        "phone": person.phone,
    }
    if before == after:
        return person

    for organization_id in sorted(organization_ids, key=str):
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="person.updated",
            resource_type="person",
            resource_id=person.id,
            before_state=before,
            after_state=after,
        )
    session.commit()
    return _get_person(session, person.id)


def change_person_status(
    session: Session,
    *,
    actor: User,
    person_id: UUID,
    payload: PersonStatusRequest,
) -> Person:
    person = _get_person(session, person_id, for_update=True)
    organization_ids = require_people_manage_for_person(
        session,
        actor_user_id=actor.id,
        person=person,
    )
    if person.user is not None and person.user.id == actor.id and not payload.is_active:
        raise PersonConflictError(
            "Administrators cannot deactivate their own Person through this endpoint."
        )
    if person.user is not None and person.user.is_active:
        from app.core.access.service import assert_actor_dominates_user_access

        assert_actor_dominates_user_access(
            session, actor_user_id=actor.id, target_user_id=person.user.id
        )
    if person.is_active is payload.is_active:
        return person

    before = {"is_active": person.is_active}
    person.is_active = payload.is_active
    for organization_id in sorted(organization_ids, key=str):
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="person.status.changed",
            resource_type="person",
            resource_id=person.id,
            before_state=before,
            after_state={"is_active": person.is_active},
        )
    session.commit()
    return _get_person(session, person.id)


def add_person_relationship(
    session: Session,
    *,
    actor: User,
    person_id: UUID,
    payload: PersonRelationshipCreateRequest,
) -> PersonOrganizationRelationship:
    person = _get_person(session, person_id, for_update=True)
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=PEOPLE_MANAGE,
        organization_id=payload.organization_id,
    )
    organization = session.get(Organization, payload.organization_id)
    if organization is None or not organization.is_active:
        raise PersonNotFoundError("Organization not found.")

    duplicate = session.scalar(
        select(PersonOrganizationRelationship)
        .where(
            PersonOrganizationRelationship.person_id == person.id,
            PersonOrganizationRelationship.organization_id == organization.id,
            PersonOrganizationRelationship.relationship_code == payload.relationship_code,
            PersonOrganizationRelationship.is_active.is_(True),
        )
        .limit(1)
    )
    if duplicate is not None:
        raise PersonConflictError("An active matching relationship already exists.")

    relationship = PersonOrganizationRelationship(
        person=person,
        organization=organization,
        relationship_code=payload.relationship_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=True,
    )
    session.add(relationship)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action="person.relationship.created",
        resource_type="person_relationship",
        resource_id=relationship.id,
        after_state={
            "person_id": str(person.id),
            "organization_id": str(organization.id),
            "relationship_code": relationship.relationship_code,
            "start_date": relationship.start_date.isoformat() if relationship.start_date else None,
            "end_date": relationship.end_date.isoformat() if relationship.end_date else None,
            "is_active": True,
        },
    )
    session.commit()
    session.refresh(relationship)
    return relationship


def change_person_relationship_status(
    session: Session,
    *,
    actor: User,
    person_id: UUID,
    relationship_id: UUID,
    payload: PersonRelationshipStatusRequest,
) -> PersonOrganizationRelationship:
    _get_person(session, person_id, for_update=True)
    relationship = session.scalar(
        select(PersonOrganizationRelationship)
        .where(
            PersonOrganizationRelationship.id == relationship_id,
            PersonOrganizationRelationship.person_id == person_id,
        )
        .with_for_update()
    )
    if relationship is None:
        raise PersonRelationshipNotFoundError("Person relationship not found.")
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=PEOPLE_MANAGE,
        organization_id=relationship.organization_id,
    )
    if relationship.is_active is payload.is_active:
        return relationship

    if payload.is_active:
        duplicate = session.scalar(
            select(PersonOrganizationRelationship.id)
            .where(
                PersonOrganizationRelationship.person_id == person_id,
                PersonOrganizationRelationship.organization_id == relationship.organization_id,
                PersonOrganizationRelationship.relationship_code == relationship.relationship_code,
                PersonOrganizationRelationship.is_active.is_(True),
                PersonOrganizationRelationship.id != relationship.id,
            )
            .limit(1)
        )
        if duplicate is not None:
            raise PersonConflictError("An active matching relationship already exists.")
    else:
        person = _get_person(session, person_id)
        if person.user is not None:
            from app.core.access.models import UserRoleAssignment

            active_access = session.scalar(
                select(UserRoleAssignment.id)
                .where(
                    UserRoleAssignment.user_id == person.user.id,
                    UserRoleAssignment.organization_id == relationship.organization_id,
                    UserRoleAssignment.is_active.is_(True),
                )
                .limit(1)
            )
            if active_access is not None:
                raise PersonConflictError(
                    "Deactivate access assignments rooted at this organization before "
                    "deactivating the person's relationship."
                )

    before = {"is_active": relationship.is_active}
    relationship.is_active = payload.is_active
    record_audit_event(
        session,
        actor=actor,
        organization_id=relationship.organization_id,
        action="person.relationship.status.changed",
        resource_type="person_relationship",
        resource_id=relationship.id,
        before_state=before,
        after_state={"is_active": relationship.is_active},
        metadata={"person_id": str(person_id)},
    )
    session.commit()
    session.refresh(relationship)
    return relationship


def search_people_for_user(
    session: Session,
    *,
    user_id: UUID,
    query: str,
    limit: int = 8,
) -> list[PersonListItem]:
    allowed_org_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=PEOPLE_READ,
    )
    if not allowed_org_ids:
        return []

    normalized = query.strip().lower()
    if not normalized:
        return []
    pattern = f"%{normalized}%"

    # Filter by an authorized relationship in SQL before applying the limit.
    # This avoids loading unrelated people and prevents Search from becoming a
    # cross-organization enumeration side channel.
    statement = (
        select(Person)
        .join(PersonOrganizationRelationship)
        .where(
            PersonOrganizationRelationship.organization_id.in_(allowed_org_ids),
            or_(
                func.lower(Person.first_name).like(pattern),
                func.lower(Person.last_name).like(pattern),
                func.lower(func.coalesce(Person.email, "")).like(pattern),
                func.lower(func.coalesce(Person.phone, "")).like(pattern),
            ),
        )
        .distinct()
        .options(
            selectinload(Person.organization_relationships).selectinload(
                PersonOrganizationRelationship.organization
            )
        )
        .order_by(Person.last_name, Person.first_name, Person.id)
        .limit(limit)
    )

    result: list[PersonListItem] = []
    for person in session.scalars(statement).all():
        item = _person_to_list_item(person, allowed_org_ids)
        if item.relationships:
            result.append(item)
    return result
