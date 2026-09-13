from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.core.access.permissions import USERS_MANAGE, USERS_READ
from app.core.access.policy import AuthorizationError, require_permission_for_organization
from app.core.access.service import authorized_organization_ids
from app.core.audit.service import record_audit_event
from app.core.identity.admin_schemas import (
    UserCreateRequest,
    UserListItem,
    UserPasswordResetRequest,
    UserStatusRequest,
    UserUpdateRequest,
)
from app.core.identity.models import User
from app.core.identity.security import hash_password
from app.core.people.models import Person, PersonOrganizationRelationship


class UserAdminNotFoundError(LookupError):
    pass


class UserAdminConflictError(ValueError):
    pass


def _user_statement(user_id: UUID, *, for_update: bool = False) -> Select[tuple[User]]:
    statement = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.person)
            .selectinload(Person.organization_relationships)
            .selectinload(PersonOrganizationRelationship.organization)
        )
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_user(session: Session, user_id: UUID, *, for_update: bool = False) -> User:
    user = session.scalar(_user_statement(user_id, for_update=for_update))
    if user is None:
        raise UserAdminNotFoundError("User not found.")
    return user


def _person_organization_ids(person: Person) -> set[UUID]:
    active = {
        relationship.organization_id
        for relationship in person.organization_relationships
        if relationship.is_active and relationship.organization.is_active
    }
    if active:
        return active
    return {
        relationship.organization_id
        for relationship in person.organization_relationships
        if relationship.organization.is_active
    }


def _require_users_manage_for_person(
    session: Session,
    *,
    actor_user_id: UUID,
    person: Person,
) -> set[UUID]:
    organization_ids = _person_organization_ids(person)
    if not organization_ids:
        raise AuthorizationError("Permission denied.")
    for organization_id in organization_ids:
        require_permission_for_organization(
            session,
            user_id=actor_user_id,
            permission_code=USERS_MANAGE,
            organization_id=organization_id,
        )
    return organization_ids


def _user_to_item(user: User, visible_organization_ids: set[UUID]) -> UserListItem:
    visible_relationships = [
        relationship
        for relationship in user.person.organization_relationships
        if relationship.organization_id in visible_organization_ids
        and relationship.organization.is_active
    ]
    return UserListItem(
        id=user.id,
        person_id=user.person_id,
        person_name=f"{user.person.first_name} {user.person.last_name}".strip(),
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        organization_names=sorted(
            {relationship.organization.name for relationship in visible_relationships}
        ),
    )


def list_users_for_user(
    session: Session,
    *,
    user_id: UUID,
) -> list[UserListItem]:
    organization_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=USERS_READ,
    )
    if not organization_ids:
        return []

    statement = (
        select(User)
        .options(
            selectinload(User.person)
            .selectinload(Person.organization_relationships)
            .selectinload(PersonOrganizationRelationship.organization)
        )
        .order_by(User.email)
    )

    result: list[UserListItem] = []
    for user in session.scalars(statement).all():
        item = _user_to_item(user, organization_ids)
        if item.organization_names:
            result.append(item)
    return result


def get_user_for_viewer(
    session: Session,
    *,
    viewer_user_id: UUID,
    target_user_id: UUID,
    permission_code: str = USERS_READ,
) -> UserListItem:
    target = _get_user(session, target_user_id)
    allowed_org_ids = authorized_organization_ids(
        session,
        user_id=viewer_user_id,
        permission_code=permission_code,
    )
    item = _user_to_item(target, allowed_org_ids)
    if not item.organization_names:
        raise UserAdminNotFoundError("User not found.")
    return item


def _login_conflicts(
    session: Session,
    *,
    email: str | None,
    username: str | None,
    exclude_user_id: UUID | None = None,
) -> bool:
    conditions = []
    if email is not None:
        conditions.append(func.lower(User.email) == email.lower())
    if username is not None:
        conditions.append(func.lower(User.username) == username.lower())
    if not conditions:
        return False

    from sqlalchemy import or_

    statement = select(User.id).where(or_(*conditions))
    if exclude_user_id is not None:
        statement = statement.where(User.id != exclude_user_id)
    return session.scalar(statement.limit(1)) is not None


def create_user(
    session: Session,
    *,
    actor: User,
    payload: UserCreateRequest,
) -> User:
    person = session.scalar(
        select(Person)
        .where(Person.id == payload.person_id)
        .options(
            selectinload(Person.organization_relationships).selectinload(
                PersonOrganizationRelationship.organization
            ),
            selectinload(Person.user),
        )
        .with_for_update()
    )
    if person is None:
        raise UserAdminNotFoundError("Person not found.")
    if not person.is_active:
        raise UserAdminConflictError("Cannot create a user for an inactive person.")
    organization_ids = _require_users_manage_for_person(
        session,
        actor_user_id=actor.id,
        person=person,
    )
    if person.user is not None:
        raise UserAdminConflictError("Person already has a user account.")
    if _login_conflicts(session, email=payload.email, username=payload.username):
        raise UserAdminConflictError("Email or username already exists.")

    user = User(
        person=person,
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    session.flush()

    for organization_id in sorted(organization_ids, key=str):
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="user.created",
            resource_type="user",
            resource_id=user.id,
            after_state={
                "person_id": str(person.id),
                "email": user.email,
                "username": user.username,
                "is_active": True,
            },
        )
    session.commit()
    return _get_user(session, user.id)


def update_user(
    session: Session,
    *,
    actor: User,
    target_user_id: UUID,
    payload: UserUpdateRequest,
) -> User:
    target = _get_user(session, target_user_id, for_update=True)
    organization_ids = _require_users_manage_for_person(
        session,
        actor_user_id=actor.id,
        person=target.person,
    )
    from app.core.access.service import assert_actor_dominates_user_access

    assert_actor_dominates_user_access(session, actor_user_id=actor.id, target_user_id=target.id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return target

    candidate_email = changes.get("email", target.email)
    candidate_username = changes.get("username", target.username)
    if _login_conflicts(
        session,
        email=candidate_email,
        username=candidate_username,
        exclude_user_id=target.id,
    ):
        raise UserAdminConflictError("Email or username already exists.")

    before = {"email": target.email, "username": target.username}
    if "email" in changes:
        target.email = changes["email"]
    if "username" in changes:
        target.username = changes["username"]
    after = {"email": target.email, "username": target.username}
    if before == after:
        return target

    for organization_id in sorted(organization_ids, key=str):
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="user.updated",
            resource_type="user",
            resource_id=target.id,
            before_state=before,
            after_state=after,
        )
    session.commit()
    return _get_user(session, target.id)


def change_user_status(
    session: Session,
    *,
    actor: User,
    target_user_id: UUID,
    payload: UserStatusRequest,
) -> User:
    target = _get_user(session, target_user_id, for_update=True)
    if target.id == actor.id and not payload.is_active:
        raise UserAdminConflictError(
            "Administrators cannot deactivate their own account through this endpoint."
        )
    organization_ids = _require_users_manage_for_person(
        session,
        actor_user_id=actor.id,
        person=target.person,
    )
    from app.core.access.service import assert_actor_dominates_user_access

    assert_actor_dominates_user_access(session, actor_user_id=actor.id, target_user_id=target.id)
    if target.is_active is payload.is_active:
        return target

    before = {"is_active": target.is_active}
    target.is_active = payload.is_active
    for organization_id in sorted(organization_ids, key=str):
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="user.status.changed",
            resource_type="user",
            resource_id=target.id,
            before_state=before,
            after_state={"is_active": target.is_active},
        )
    session.commit()
    return _get_user(session, target.id)


def reset_user_password(
    session: Session,
    *,
    actor: User,
    target_user_id: UUID,
    payload: UserPasswordResetRequest,
) -> None:
    target = _get_user(session, target_user_id, for_update=True)
    organization_ids = _require_users_manage_for_person(
        session,
        actor_user_id=actor.id,
        person=target.person,
    )
    from app.core.access.service import assert_actor_dominates_user_access

    assert_actor_dominates_user_access(session, actor_user_id=actor.id, target_user_id=target.id)
    target.password_hash = hash_password(payload.new_password.get_secret_value())
    for organization_id in sorted(organization_ids, key=str):
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="user.password.reset",
            resource_type="user",
            resource_id=target.id,
            # Deliberately never include password/hash in before/after/metadata.
            metadata={"password_changed": True},
        )
    session.commit()
