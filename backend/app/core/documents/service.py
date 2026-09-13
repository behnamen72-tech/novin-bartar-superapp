from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.access.models import Role, RolePermission
from app.core.access.permissions import (
    ACCESS_MANAGE,
    AUDIT_READ,
    DOCUMENTS_MANAGE,
    DOCUMENTS_READ,
    PEOPLE_READ,
)
from app.core.access.policy import (
    AuthorizationError,
    has_permission,
    require_permission_for_organization,
)
from app.core.access.service import (
    authorized_organization_ids,
    effective_role_ids_for_permission,
    role_has_effective_assignment_for_organization,
)
from app.core.audit.models import AuditEvent
from app.core.audit.service import record_audit_event
from app.core.documents.models import (
    Document,
    DocumentCategory,
    DocumentLink,
    DocumentLinkEntityType,
    DocumentPermission,
    DocumentPermissionType,
    DocumentPriority,
    DocumentStatus,
    DocumentVersion,
    RetentionBasis,
    RetentionPolicy,
    StorageObject,
)
from app.core.documents.security import validate_upload_content
from app.core.documents.storage.interface import StorageProvider
from app.core.identity.models import User
from app.core.organization.models import Organization
from app.core.people.models import Person, PersonOrganizationRelationship


class DocumentNotFoundError(LookupError):
    pass


class DocumentLinkNotFoundError(LookupError):
    pass


class DocumentLinkTargetNotFoundError(LookupError):
    pass


class DocumentStateConflictError(RuntimeError):
    pass


class DocumentLinkConflictError(RuntimeError):
    pass


class DocumentLinkFilterError(ValueError):
    pass


class DocumentPermissionNotFoundError(LookupError):
    pass


class DocumentPermissionTargetNotFoundError(LookupError):
    pass


class DocumentPermissionConflictError(RuntimeError):
    pass


class DocumentMetadataValidationError(ValueError):
    pass


class DocumentCategoryNotFoundError(LookupError):
    pass


class DocumentCategoryConflictError(RuntimeError):
    pass


class RetentionPolicyNotFoundError(LookupError):
    pass


class RetentionPolicyConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadedDocument:
    content: bytes
    file_name: str
    mime_type: str
    version_number: int


def _document_acl_types_for(permission_code: str) -> tuple[str, ...]:
    if permission_code == DOCUMENTS_READ:
        return (DocumentPermissionType.READ.value, DocumentPermissionType.MANAGE.value)
    if permission_code == DOCUMENTS_MANAGE:
        return (DocumentPermissionType.MANAGE.value,)
    raise AuthorizationError("Unsupported document permission check.")


def _document_has_active_acl(session: Session, *, document_id: UUID) -> bool:
    return (
        session.scalar(
            select(DocumentPermission.id)
            .where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.is_active.is_(True),
            )
            .limit(1)
        )
        is not None
    )


def _require_document_permission(
    session: Session,
    *,
    user_id: UUID,
    document: Document,
    permission_code: str,
) -> None:
    # Organization permission is always the outer boundary. Document ACLs only
    # restrict that existing authority; they never grant cross-organization access.
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=permission_code,
        organization_id=document.organization_id,
    )

    if not _document_has_active_acl(session, document_id=document.id):
        return

    effective_role_ids = effective_role_ids_for_permission(
        session,
        user_id=user_id,
        organization_id=document.organization_id,
        permission_code=permission_code,
    )
    if not effective_role_ids:
        raise DocumentNotFoundError("Document not found.")

    allowed = session.scalar(
        select(DocumentPermission.id)
        .where(
            DocumentPermission.document_id == document.id,
            DocumentPermission.is_active.is_(True),
            DocumentPermission.role_id.in_(effective_role_ids),
            DocumentPermission.permission_type.in_(_document_acl_types_for(permission_code)),
        )
        .limit(1)
    )
    if allowed is None:
        # Hide the existence of a confidential document from users who are inside
        # the organization but not on the document allowlist.
        raise DocumentNotFoundError("Document not found.")


def _require_document_permission_admin(
    session: Session,
    *,
    user_id: UUID,
    document: Document,
) -> None:
    """Authorize ACL administration with a narrow recovery path.

    Normal document managers must satisfy the document MANAGE ACL. Existing
    `access.manage` acts as a break-glass ACL-administration permission within the
    same organization scope, but does not grant document read/download access.
    """
    original_error: Exception | None = None
    try:
        _require_document_permission(
            session,
            user_id=user_id,
            document=document,
            permission_code=DOCUMENTS_MANAGE,
        )
        return
    except (AuthorizationError, DocumentNotFoundError) as exc:
        original_error = exc

    try:
        require_permission_for_organization(
            session,
            user_id=user_id,
            permission_code=ACCESS_MANAGE,
            organization_id=document.organization_id,
        )
    except AuthorizationError:
        assert original_error is not None
        raise original_error from None


def _get_locked_document_for_permission_admin(
    session: Session,
    *,
    user_id: UUID,
    document_id: UUID,
) -> Document:
    document = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None:
        raise DocumentNotFoundError("Document not found.")
    _require_document_permission_admin(session, user_id=user_id, document=document)
    return document


def _validate_document_permission_target(
    session: Session,
    *,
    document: Document,
    role_id: UUID,
    permission_type: DocumentPermissionType,
) -> Role:
    role = session.scalar(
        select(Role)
        .where(Role.id == role_id, Role.is_active.is_(True))
        .options(selectinload(Role.permission_links).selectinload(RolePermission.permission))
    )
    required_permission_code = (
        DOCUMENTS_READ if permission_type == DocumentPermissionType.READ else DOCUMENTS_MANAGE
    )
    if role is None or not any(
        link.permission.is_active and link.permission.code == required_permission_code
        for link in role.permission_links
    ):
        raise DocumentPermissionTargetNotFoundError(
            "Role is not available for this document permission."
        )

    if not role_has_effective_assignment_for_organization(
        session,
        role_id=role.id,
        organization_id=document.organization_id,
    ):
        raise DocumentPermissionTargetNotFoundError(
            "Role is not available for this document permission."
        )
    return role


def _require_active_document(document: Document) -> None:
    if document.status != DocumentStatus.ACTIVE:
        raise DocumentStateConflictError(
            "Document must be active before its content or links can be changed."
        )


def _get_locked_document(
    session: Session,
    *,
    user_id: UUID,
    document_id: UUID,
    permission_code: str,
) -> Document:
    document = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None:
        raise DocumentNotFoundError("Document not found.")

    _require_document_permission(
        session,
        user_id=user_id,
        document=document,
        permission_code=permission_code,
    )
    return document


def _validate_link_target(
    session: Session,
    *,
    actor_id: UUID,
    document: Document,
    entity_type: DocumentLinkEntityType,
    entity_id: UUID,
) -> None:
    if entity_type == DocumentLinkEntityType.ORGANIZATION:
        # Organization ownership is already first-class on Document. The generic
        # link API may reference the owner organization, but B5.3 deliberately
        # prevents a document owned by Company A from being linked to Company B.
        target = session.get(Organization, entity_id)
        if target is None or target.id != document.organization_id:
            raise DocumentLinkTargetNotFoundError(
                "Link target is not available for this document organization."
            )
        return

    if entity_type == DocumentLinkEntityType.PERSON:
        # Managing documents does not implicitly grant visibility into People.
        # Reuse the existing permission engine before accepting a Person target.
        require_permission_for_organization(
            session,
            user_id=actor_id,
            permission_code=PEOPLE_READ,
            organization_id=document.organization_id,
        )
        person = session.get(Person, entity_id)
        if person is None:
            raise DocumentLinkTargetNotFoundError(
                "Link target is not available for this document organization."
            )

        relationship_exists = session.scalar(
            select(PersonOrganizationRelationship.id)
            .where(
                PersonOrganizationRelationship.person_id == person.id,
                PersonOrganizationRelationship.organization_id == document.organization_id,
            )
            .limit(1)
        )
        # Historical relationships count. Documents may legitimately need to
        # remain linked to a former employee/contact after that relationship ends.
        if relationship_exists is None:
            raise DocumentLinkTargetNotFoundError(
                "Link target is not available for this document organization."
            )
        return

    # The Pydantic API enum prevents this today; keep a fail-closed service guard
    # for direct/internal callers and future entity types.
    raise DocumentLinkTargetNotFoundError("Unsupported document link target type.")


def create_document(
    session: Session,
    *,
    actor: User,
    title: str,
    document_type: str,
    organization_id: UUID,
) -> Document:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=DOCUMENTS_MANAGE,
        organization_id=organization_id,
    )

    document = Document(
        title=title,
        document_type=document_type,
        organization_id=organization_id,
        created_by=actor.id,
        status=DocumentStatus.ACTIVE,
    )
    session.add(document)
    session.flush()

    record_audit_event(
        session,
        actor=actor,
        organization_id=organization_id,
        action="document.created",
        resource_type="document",
        resource_id=document.id,
        after_state={
            "title": document.title,
            "document_type": document.document_type,
            "status": document.status,
            "organization_id": document.organization_id,
        },
    )

    session.commit()
    session.refresh(document)
    return document


def _document_acl_list_condition(
    session: Session,
    *,
    user_id: UUID,
    organization_ids: set[UUID],
    permission_code: str,
) -> ColumnElement[bool]:
    """Build a DB-level predicate for organization + document ACL access."""
    active_acl_exists = exists().where(
        DocumentPermission.document_id == Document.id,
        DocumentPermission.is_active.is_(True),
    )
    acl_types = _document_acl_types_for(permission_code)
    organization_conditions = []

    for organization_id in organization_ids:
        role_ids = effective_role_ids_for_permission(
            session,
            user_id=user_id,
            organization_id=organization_id,
            permission_code=permission_code,
        )
        if role_ids:
            matching_acl_exists = exists().where(
                DocumentPermission.document_id == Document.id,
                DocumentPermission.is_active.is_(True),
                DocumentPermission.role_id.in_(role_ids),
                DocumentPermission.permission_type.in_(acl_types),
            )
            acl_access = or_(~active_acl_exists, matching_acl_exists)
        else:
            acl_access = ~active_acl_exists

        organization_conditions.append(
            and_(Document.organization_id == organization_id, acl_access)
        )

    return or_(*organization_conditions)


def list_documents(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None = None,
    document_type: str | None = None,
    status: DocumentStatus | None = None,
    entity_type: DocumentLinkEntityType | None = None,
    entity_id: UUID | None = None,
    search: str | None = None,
    category_id: UUID | None = None,
    priority: DocumentPriority | None = None,
    expires_before: datetime | None = None,
    expires_after: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Document]:
    if (entity_type is None) != (entity_id is None):
        raise DocumentLinkFilterError("entity_type and entity_id must be provided together.")

    if organization_id is not None:
        require_permission_for_organization(
            session,
            user_id=user_id,
            permission_code=DOCUMENTS_READ,
            organization_id=organization_id,
        )
        allowed_organization_ids = {organization_id}
    else:
        allowed_organization_ids = authorized_organization_ids(
            session,
            user_id=user_id,
            permission_code=DOCUMENTS_READ,
        )

    if not allowed_organization_ids:
        return []

    statement = select(Document).where(
        _document_acl_list_condition(
            session,
            user_id=user_id,
            organization_ids=allowed_organization_ids,
            permission_code=DOCUMENTS_READ,
        )
    )

    if document_type is not None:
        statement = statement.where(Document.document_type == document_type.strip().lower())
    if status is not None:
        statement = statement.where(Document.status == status)
    if category_id is not None:
        statement = statement.where(Document.category_id == category_id)
    if priority is not None:
        statement = statement.where(Document.priority == priority.value)
    if expires_before is not None:
        statement = statement.where(Document.expires_at <= expires_before)
    if expires_after is not None:
        statement = statement.where(Document.expires_at >= expires_after)
    if search is not None:
        normalized_search = search.strip().lower()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    func.lower(Document.title).like(pattern),
                    func.lower(Document.document_type).like(pattern),
                    func.lower(func.coalesce(Document.description, "")).like(pattern),
                )
            )
    if entity_type is not None and entity_id is not None:
        statement = statement.join(DocumentLink).where(
            DocumentLink.entity_type == entity_type.value,
            DocumentLink.entity_id == str(entity_id),
            DocumentLink.is_active.is_(True),
        )

    statement = (
        statement.order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def get_document_for_user(
    session: Session,
    *,
    user_id: UUID,
    document_id: UUID,
    permission_code: str = DOCUMENTS_READ,
) -> Document:
    statement = (
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.versions).selectinload(DocumentVersion.storage_object),
            selectinload(Document.links),
        )
    )
    document = session.scalar(statement)
    if document is None:
        raise DocumentNotFoundError("Document not found.")

    _require_document_permission(
        session,
        user_id=user_id,
        document=document,
        permission_code=permission_code,
    )
    return document


def archive_document(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
) -> Document:
    document = _get_locked_document(
        session,
        user_id=actor.id,
        document_id=document_id,
        permission_code=DOCUMENTS_MANAGE,
    )

    if document.status == DocumentStatus.ARCHIVED:
        # Idempotent archive: release the row lock without writing a duplicate Audit event.
        session.commit()
        return document
    if document.status != DocumentStatus.ACTIVE:
        session.rollback()
        raise DocumentStateConflictError("Only active documents can be archived.")

    before_status = document.status
    document.status = DocumentStatus.ARCHIVED
    record_audit_event(
        session,
        actor=actor,
        organization_id=document.organization_id,
        action="document.archived",
        resource_type="document",
        resource_id=document.id,
        before_state={"status": before_status},
        after_state={"status": document.status},
    )
    session.commit()
    session.refresh(document)
    return document


def restore_document(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
) -> Document:
    document = _get_locked_document(
        session,
        user_id=actor.id,
        document_id=document_id,
        permission_code=DOCUMENTS_MANAGE,
    )

    if document.status == DocumentStatus.ACTIVE:
        # Idempotent restore: release the row lock without writing a duplicate Audit event.
        session.commit()
        return document
    if document.status != DocumentStatus.ARCHIVED:
        session.rollback()
        raise DocumentStateConflictError("Only archived documents can be restored.")

    before_status = document.status
    document.status = DocumentStatus.ACTIVE
    record_audit_event(
        session,
        actor=actor,
        organization_id=document.organization_id,
        action="document.restored",
        resource_type="document",
        resource_id=document.id,
        before_state={"status": before_status},
        after_state={"status": document.status},
    )
    session.commit()
    session.refresh(document)
    return document


def add_document_link(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    entity_type: DocumentLinkEntityType,
    entity_id: UUID,
) -> DocumentLink:
    try:
        document = _get_locked_document(
            session,
            user_id=actor.id,
            document_id=document_id,
            permission_code=DOCUMENTS_MANAGE,
        )
        _require_active_document(document)
        _validate_link_target(
            session,
            actor_id=actor.id,
            document=document,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        existing = session.scalar(
            select(DocumentLink).where(
                DocumentLink.document_id == document.id,
                DocumentLink.entity_type == entity_type.value,
                DocumentLink.entity_id == str(entity_id),
            )
        )
        if existing is not None and existing.is_active:
            raise DocumentLinkConflictError("Document is already linked to this target.")

        if existing is None:
            link = DocumentLink(
                document_id=document.id,
                entity_type=entity_type.value,
                entity_id=str(entity_id),
                is_active=True,
            )
            session.add(link)
            session.flush()
            reactivated = False
        else:
            link = existing
            link.is_active = True
            session.flush()
            reactivated = True

        record_audit_event(
            session,
            actor=actor,
            organization_id=document.organization_id,
            action="document.linked",
            resource_type="document",
            resource_id=document.id,
            after_state={
                "link_id": link.id,
                "entity_type": link.entity_type,
                "entity_id": link.entity_id,
                "is_active": link.is_active,
            },
            metadata={"reactivated": reactivated},
        )
        # No fallible work after commit inside this compensation-style block.
        session.commit()
        return link
    except Exception:
        session.rollback()
        raise


def list_document_links(
    session: Session,
    *,
    user_id: UUID,
    document_id: UUID,
) -> list[DocumentLink]:
    document = get_document_for_user(
        session,
        user_id=user_id,
        document_id=document_id,
        permission_code=DOCUMENTS_READ,
    )
    return [link for link in document.links if link.is_active]


def unlink_document(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    link_id: UUID,
) -> None:
    try:
        document = _get_locked_document(
            session,
            user_id=actor.id,
            document_id=document_id,
            permission_code=DOCUMENTS_MANAGE,
        )
        _require_active_document(document)

        link = session.scalar(
            select(DocumentLink).where(
                DocumentLink.id == link_id,
                DocumentLink.document_id == document.id,
            )
        )
        if link is None or not link.is_active:
            raise DocumentLinkNotFoundError("Document link not found.")

        before_state = {
            "link_id": link.id,
            "entity_type": link.entity_type,
            "entity_id": link.entity_id,
            "is_active": True,
        }
        link.is_active = False
        session.flush()

        record_audit_event(
            session,
            actor=actor,
            organization_id=document.organization_id,
            action="document.unlinked",
            resource_type="document",
            resource_id=document.id,
            before_state=before_state,
            after_state={**before_state, "is_active": False},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise


def list_document_permissions(
    session: Session,
    *,
    user_id: UUID,
    document_id: UUID,
) -> list[DocumentPermission]:
    document = session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found.")
    _require_document_permission_admin(session, user_id=user_id, document=document)

    return list(
        session.scalars(
            select(DocumentPermission)
            .where(
                DocumentPermission.document_id == document.id,
                DocumentPermission.is_active.is_(True),
            )
            .order_by(
                DocumentPermission.permission_type,
                DocumentPermission.created_at,
                DocumentPermission.id,
            )
        ).all()
    )


def grant_document_permission(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    role_id: UUID,
    permission_type: DocumentPermissionType,
) -> DocumentPermission:
    try:
        document = _get_locked_document_for_permission_admin(
            session,
            user_id=actor.id,
            document_id=document_id,
        )
        role = _validate_document_permission_target(
            session,
            document=document,
            role_id=role_id,
            permission_type=permission_type,
        )

        existing = session.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document.id,
                DocumentPermission.role_id == role.id,
                DocumentPermission.permission_type == permission_type.value,
            )
        )
        if existing is not None and existing.is_active:
            raise DocumentPermissionConflictError(
                "Document permission is already active for this role."
            )

        active_count = int(
            session.scalar(
                select(func.count(DocumentPermission.id)).where(
                    DocumentPermission.document_id == document.id,
                    DocumentPermission.is_active.is_(True),
                )
            )
            or 0
        )

        # Turning on restrictive ACL mode must never accidentally lock out the
        # actor who enabled it. The first row is therefore a MANAGE row owned by
        # one of the actor's effective manager roles. `access.manage` is the
        # explicit scoped recovery/admin exception.
        if active_count == 0:
            if permission_type != DocumentPermissionType.MANAGE:
                raise DocumentPermissionConflictError(
                    "The first document permission must be a manage permission."
                )
            actor_manage_roles = effective_role_ids_for_permission(
                session,
                user_id=actor.id,
                organization_id=document.organization_id,
                permission_code=DOCUMENTS_MANAGE,
            )
            actor_is_access_admin = has_permission(
                session,
                user_id=actor.id,
                permission_code=ACCESS_MANAGE,
                organization_id=document.organization_id,
            )
            if role.id not in actor_manage_roles and not actor_is_access_admin:
                raise DocumentPermissionConflictError(
                    "The first manage permission must keep the current manager in control."
                )

        if existing is None:
            permission = DocumentPermission(
                document_id=document.id,
                role_id=role.id,
                permission_type=permission_type.value,
                is_active=True,
            )
            session.add(permission)
            session.flush()
            reactivated = False
        else:
            permission = existing
            permission.is_active = True
            session.flush()
            reactivated = True

        record_audit_event(
            session,
            actor=actor,
            organization_id=document.organization_id,
            action="document.permission.granted",
            resource_type="document",
            resource_id=document.id,
            after_state={
                "document_permission_id": permission.id,
                "role_id": permission.role_id,
                "permission_type": permission.permission_type,
                "is_active": True,
            },
            metadata={
                "reactivated": reactivated,
                "acl_mode": "restricted",
            },
        )
        session.commit()
        return permission
    except Exception:
        session.rollback()
        raise


def revoke_document_permission(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    document_permission_id: UUID,
) -> None:
    try:
        document = _get_locked_document_for_permission_admin(
            session,
            user_id=actor.id,
            document_id=document_id,
        )
        permission = session.scalar(
            select(DocumentPermission).where(
                DocumentPermission.id == document_permission_id,
                DocumentPermission.document_id == document.id,
                DocumentPermission.is_active.is_(True),
            )
        )
        if permission is None:
            raise DocumentPermissionNotFoundError("Document permission not found.")

        other_active = list(
            session.scalars(
                select(DocumentPermission).where(
                    DocumentPermission.document_id == document.id,
                    DocumentPermission.id != permission.id,
                    DocumentPermission.is_active.is_(True),
                )
            ).all()
        )
        if (
            permission.permission_type == DocumentPermissionType.MANAGE.value
            and other_active
            and not any(
                item.permission_type == DocumentPermissionType.MANAGE.value for item in other_active
            )
        ):
            raise DocumentPermissionConflictError(
                "A restricted document must keep at least one active manage permission."
            )

        before_state = {
            "document_permission_id": permission.id,
            "role_id": permission.role_id,
            "permission_type": permission.permission_type,
            "is_active": True,
        }
        permission.is_active = False
        session.flush()

        remaining_count = len(other_active)
        record_audit_event(
            session,
            actor=actor,
            organization_id=document.organization_id,
            action="document.permission.revoked",
            resource_type="document",
            resource_id=document.id,
            before_state=before_state,
            after_state={**before_state, "is_active": False},
            metadata={
                "acl_mode_after": "restricted" if remaining_count else "inherited",
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise


def create_document_version(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    filename: str | None,
    declared_content_type: str | None,
    content: bytes,
    max_size_bytes: int,
    storage: StorageProvider,
) -> DocumentVersion:
    document = get_document_for_user(
        session,
        user_id=actor.id,
        document_id=document_id,
        permission_code=DOCUMENTS_MANAGE,
    )
    _require_active_document(document)

    safe_filename, extension, mime_type = validate_upload_content(
        filename=filename,
        declared_content_type=declared_content_type,
        content=content,
        max_size_bytes=max_size_bytes,
    )

    object_key = f"{document.organization_id}/{document.id}/{uuid4().hex}{extension}"
    checksum = sha256(content).hexdigest()
    stored_key: str | None = None

    try:
        # Serialize version-number allocation and lifecycle mutation per document.
        locked_document = session.scalar(
            select(Document).where(Document.id == document.id).with_for_update()
        )
        if locked_document is None:
            raise DocumentNotFoundError("Document not found.")

        # Re-check authorization and lifecycle state against the locked row so a
        # future move/archive cannot create a TOCTOU authorization/state gap.
        _require_document_permission(
            session,
            user_id=actor.id,
            document=locked_document,
            permission_code=DOCUMENTS_MANAGE,
        )
        _require_active_document(locked_document)

        current_max = session.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == locked_document.id
            )
        )
        version_number = int(current_max or 0) + 1

        stored_key = storage.save(object_key, content)
        storage_object = StorageObject(
            provider=storage.provider_name,
            object_path=stored_key,
            checksum=checksum,
            size_bytes=len(content),
        )
        session.add(storage_object)
        session.flush()

        version = DocumentVersion(
            document_id=locked_document.id,
            storage_object_id=storage_object.id,
            created_by=actor.id,
            version_number=version_number,
            file_name=safe_filename,
            mime_type=mime_type,
        )
        session.add(version)
        session.flush()

        record_audit_event(
            session,
            actor=actor,
            organization_id=locked_document.organization_id,
            action="document.version.created",
            resource_type="document",
            resource_id=locked_document.id,
            after_state={
                "version_id": version.id,
                "version_number": version.version_number,
                "file_name": version.file_name,
                "mime_type": version.mime_type,
                "size_bytes": storage_object.size_bytes,
                "checksum": storage_object.checksum,
            },
        )

        session.commit()
        # Do not perform fallible DB work after commit inside the compensation
        # block: a post-commit exception must never delete a now-committed file.
        return version
    except Exception:
        session.rollback()
        if stored_key is not None:
            storage.discard_uncommitted(stored_key)
        raise


def download_latest_document(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    storage: StorageProvider,
) -> DownloadedDocument:
    document = get_document_for_user(
        session,
        user_id=actor.id,
        document_id=document_id,
        permission_code=DOCUMENTS_READ,
    )

    statement = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .options(selectinload(DocumentVersion.storage_object))
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    version = session.scalar(statement)
    if version is None:
        raise DocumentNotFoundError("Document has no uploaded version.")

    storage_object = version.storage_object
    if storage_object.provider != storage.provider_name:
        raise RuntimeError("Configured storage provider cannot read this document version.")

    content = storage.read(storage_object.object_path)
    if len(content) != storage_object.size_bytes:
        raise OSError("Stored file size does not match document metadata.")
    if storage_object.checksum and sha256(content).hexdigest() != storage_object.checksum:
        raise OSError("Stored file checksum validation failed.")

    # Archived documents remain readable/downloadable. Archive freezes mutation;
    # it is not a destructive delete operation.
    record_audit_event(
        session,
        actor=actor,
        organization_id=document.organization_id,
        action="document.downloaded",
        resource_type="document",
        resource_id=document.id,
        metadata={
            "version_id": version.id,
            "version_number": version.version_number,
            "file_name": version.file_name,
            "size_bytes": storage_object.size_bytes,
            "checksum": storage_object.checksum,
            "document_status": document.status,
        },
    )
    session.commit()

    return DownloadedDocument(
        content=content,
        file_name=version.file_name,
        mime_type=version.mime_type,
        version_number=version.version_number,
    )


def version_to_response_data(version: DocumentVersion) -> dict[str, object]:
    storage_object = version.storage_object
    return {
        "id": version.id,
        "document_id": version.document_id,
        "version_number": version.version_number,
        "file_name": version.file_name,
        "mime_type": version.mime_type,
        "created_by": version.created_by,
        "created_at": version.created_at,
        "size_bytes": storage_object.size_bytes,
        "checksum": storage_object.checksum,
    }


def _allowed_document_organization_ids(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None,
    permission_code: str,
) -> set[UUID]:
    if organization_id is not None:
        require_permission_for_organization(
            session,
            user_id=user_id,
            permission_code=permission_code,
            organization_id=organization_id,
        )
        return {organization_id}
    return authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=permission_code,
    )


def _resolve_active_category(
    session: Session,
    *,
    organization_id: UUID,
    category_id: UUID,
) -> DocumentCategory:
    category = session.scalar(
        select(DocumentCategory).where(
            DocumentCategory.id == category_id,
            DocumentCategory.organization_id == organization_id,
            DocumentCategory.is_active.is_(True),
        )
    )
    if category is None:
        raise DocumentCategoryNotFoundError(
            "Document category is not available for this organization."
        )
    return category


def _resolve_active_retention_policy(
    session: Session,
    *,
    organization_id: UUID,
    retention_policy_id: UUID,
) -> RetentionPolicy:
    policy = session.scalar(
        select(RetentionPolicy).where(
            RetentionPolicy.id == retention_policy_id,
            RetentionPolicy.organization_id == organization_id,
            RetentionPolicy.is_active.is_(True),
        )
    )
    if policy is None:
        raise RetentionPolicyNotFoundError(
            "Retention policy is not available for this organization."
        )
    return policy


def _retention_review_at(
    *,
    document: Document,
    policy: RetentionPolicy,
    expires_at: datetime | None,
) -> datetime:
    if policy.basis == RetentionBasis.CREATED_AT.value:
        base = document.created_at
    elif policy.basis == RetentionBasis.EXPIRES_AT.value:
        if expires_at is None:
            raise DocumentMetadataValidationError(
                "This retention policy requires an expiration date."
            )
        base = expires_at
    else:
        raise DocumentMetadataValidationError("Unsupported retention policy basis.")
    return base + timedelta(days=policy.retention_days)


def update_document_metadata(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    changes: dict[str, object],
) -> Document:
    allowed_fields = {
        "title",
        "document_type",
        "description",
        "priority",
        "category_id",
        "expires_at",
        "retention_policy_id",
    }
    unknown = set(changes) - allowed_fields
    if unknown:
        raise DocumentMetadataValidationError("Unsupported document metadata field.")
    if not changes:
        raise DocumentMetadataValidationError("No metadata changes were provided.")

    try:
        document = _get_locked_document(
            session,
            user_id=actor.id,
            document_id=document_id,
            permission_code=DOCUMENTS_MANAGE,
        )
        _require_active_document(document)

        before_state = {
            "title": document.title,
            "document_type": document.document_type,
            "description": document.description,
            "priority": document.priority,
            "category_id": document.category_id,
            "expires_at": document.expires_at,
            "retention_policy_id": document.retention_policy_id,
            "retention_review_at": document.retention_review_at,
        }

        if "title" in changes:
            title = changes["title"]
            if not isinstance(title, str) or not title.strip():
                raise DocumentMetadataValidationError("Document title cannot be empty.")
            document.title = " ".join(title.split())

        if "document_type" in changes:
            document_type = changes["document_type"]
            if not isinstance(document_type, str) or not document_type.strip():
                raise DocumentMetadataValidationError("Document type cannot be empty.")
            document.document_type = document_type.strip().lower()

        if "description" in changes:
            description = changes["description"]
            if description is not None and not isinstance(description, str):
                raise DocumentMetadataValidationError("Invalid document description.")
            document.description = (
                description.strip() or None if isinstance(description, str) else None
            )

        if "priority" in changes:
            priority = changes["priority"]
            if isinstance(priority, DocumentPriority):
                document.priority = priority.value
            elif isinstance(priority, str) and priority in {
                item.value for item in DocumentPriority
            }:
                document.priority = priority
            else:
                raise DocumentMetadataValidationError("Invalid document priority.")

        if "category_id" in changes:
            category_id = changes["category_id"]
            if category_id is None:
                document.category_id = None
            elif isinstance(category_id, UUID):
                category = _resolve_active_category(
                    session,
                    organization_id=document.organization_id,
                    category_id=category_id,
                )
                document.category_id = category.id
            else:
                raise DocumentMetadataValidationError("Invalid document category.")

        effective_expires_at = document.expires_at
        if "expires_at" in changes:
            expires_at = changes["expires_at"]
            if expires_at is not None and not isinstance(expires_at, datetime):
                raise DocumentMetadataValidationError("Invalid document expiration date.")
            effective_expires_at = expires_at
            document.expires_at = expires_at

        policy: RetentionPolicy | None = None
        if "retention_policy_id" in changes:
            retention_policy_id = changes["retention_policy_id"]
            if retention_policy_id is None:
                document.retention_policy_id = None
                document.retention_review_at = None
            elif isinstance(retention_policy_id, UUID):
                policy = _resolve_active_retention_policy(
                    session,
                    organization_id=document.organization_id,
                    retention_policy_id=retention_policy_id,
                )
                document.retention_policy_id = policy.id
            else:
                raise DocumentMetadataValidationError("Invalid retention policy.")
        elif document.retention_policy_id is not None:
            # Existing assignments remain valid even if the policy is later deactivated.
            policy = session.get(RetentionPolicy, document.retention_policy_id)

        if document.retention_policy_id is not None and policy is None:
            policy = session.get(RetentionPolicy, document.retention_policy_id)
            if policy is None:
                raise DocumentMetadataValidationError("Assigned retention policy is missing.")

        if policy is not None and ("retention_policy_id" in changes or "expires_at" in changes):
            document.retention_review_at = _retention_review_at(
                document=document,
                policy=policy,
                expires_at=effective_expires_at,
            )

        session.flush()
        after_state = {
            "title": document.title,
            "document_type": document.document_type,
            "description": document.description,
            "priority": document.priority,
            "category_id": document.category_id,
            "expires_at": document.expires_at,
            "retention_policy_id": document.retention_policy_id,
            "retention_review_at": document.retention_review_at,
        }
        changed_keys = [key for key in after_state if before_state[key] != after_state[key]]
        if changed_keys:
            record_audit_event(
                session,
                actor=actor,
                organization_id=document.organization_id,
                action="document.metadata.updated",
                resource_type="document",
                resource_id=document.id,
                before_state={key: before_state[key] for key in changed_keys},
                after_state={key: after_state[key] for key in changed_keys},
                metadata={"changed_fields": changed_keys},
            )
        session.commit()
        session.refresh(document)
        return document
    except Exception:
        session.rollback()
        raise


def _validate_category_parent(
    session: Session,
    *,
    organization_id: UUID,
    category_id: UUID | None,
    parent_id: UUID | None,
) -> DocumentCategory | None:
    if parent_id is None:
        return None
    if category_id is not None and parent_id == category_id:
        raise DocumentCategoryConflictError("A category cannot be its own parent.")

    parent = _resolve_active_category(
        session,
        organization_id=organization_id,
        category_id=parent_id,
    )
    current = parent
    visited: set[UUID] = set()
    while current.parent_id is not None:
        if current.id in visited:
            raise DocumentCategoryConflictError("Category hierarchy contains a cycle.")
        visited.add(current.id)
        if category_id is not None and current.parent_id == category_id:
            raise DocumentCategoryConflictError("Category hierarchy cannot contain a cycle.")
        ancestor = session.get(DocumentCategory, current.parent_id)
        if ancestor is None or ancestor.organization_id != organization_id:
            raise DocumentCategoryConflictError("Category hierarchy is invalid.")
        current = ancestor
    return parent


def list_document_categories(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None = None,
    include_inactive: bool = False,
) -> list[DocumentCategory]:
    allowed = _allowed_document_organization_ids(
        session,
        user_id=user_id,
        organization_id=organization_id,
        permission_code=DOCUMENTS_READ,
    )
    if not allowed:
        return []
    statement = select(DocumentCategory).where(DocumentCategory.organization_id.in_(allowed))
    if not include_inactive:
        statement = statement.where(DocumentCategory.is_active.is_(True))
    statement = statement.order_by(
        DocumentCategory.organization_id,
        DocumentCategory.name,
        DocumentCategory.id,
    )
    return list(session.scalars(statement).all())


def create_document_category(
    session: Session,
    *,
    actor: User,
    organization_id: UUID,
    code: str,
    name: str,
    description: str | None,
    parent_id: UUID | None,
) -> DocumentCategory:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=DOCUMENTS_MANAGE,
        organization_id=organization_id,
    )
    _validate_category_parent(
        session,
        organization_id=organization_id,
        category_id=None,
        parent_id=parent_id,
    )
    try:
        category = DocumentCategory(
            organization_id=organization_id,
            code=code.strip().lower(),
            name=" ".join(name.split()),
            description=description,
            parent_id=parent_id,
            is_active=True,
        )
        session.add(category)
        session.flush()
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="document.category.created",
            resource_type="document_category",
            resource_id=category.id,
            after_state={
                "code": category.code,
                "name": category.name,
                "parent_id": category.parent_id,
                "is_active": True,
            },
        )
        session.commit()
        session.refresh(category)
        return category
    except IntegrityError as exc:
        session.rollback()
        raise DocumentCategoryConflictError(
            "A category with this code already exists in the organization."
        ) from exc
    except Exception:
        session.rollback()
        raise


def update_document_category(
    session: Session,
    *,
    actor: User,
    category_id: UUID,
    changes: dict[str, object],
) -> DocumentCategory:
    allowed_fields = {"code", "name", "description", "parent_id"}
    if not changes or set(changes) - allowed_fields:
        raise DocumentMetadataValidationError("Invalid category update.")

    try:
        category = session.scalar(
            select(DocumentCategory).where(DocumentCategory.id == category_id).with_for_update()
        )
        if category is None:
            raise DocumentCategoryNotFoundError("Document category not found.")
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=DOCUMENTS_MANAGE,
            organization_id=category.organization_id,
        )

        before = {
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "parent_id": category.parent_id,
        }
        if "code" in changes:
            code = changes["code"]
            if not isinstance(code, str) or not code.strip():
                raise DocumentMetadataValidationError("Category code cannot be empty.")
            category.code = code.strip().lower()
        if "name" in changes:
            name = changes["name"]
            if not isinstance(name, str) or not name.strip():
                raise DocumentMetadataValidationError("Category name cannot be empty.")
            category.name = " ".join(name.split())
        if "description" in changes:
            description = changes["description"]
            if description is not None and not isinstance(description, str):
                raise DocumentMetadataValidationError("Invalid category description.")
            category.description = (
                description.strip() or None if isinstance(description, str) else None
            )
        if "parent_id" in changes:
            parent_id = changes["parent_id"]
            if parent_id is not None and not isinstance(parent_id, UUID):
                raise DocumentMetadataValidationError("Invalid category parent.")
            _validate_category_parent(
                session,
                organization_id=category.organization_id,
                category_id=category.id,
                parent_id=parent_id,
            )
            category.parent_id = parent_id

        session.flush()
        after = {
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "parent_id": category.parent_id,
        }
        changed_keys = [key for key in after if before[key] != after[key]]
        if changed_keys:
            record_audit_event(
                session,
                actor=actor,
                organization_id=category.organization_id,
                action="document.category.updated",
                resource_type="document_category",
                resource_id=category.id,
                before_state={key: before[key] for key in changed_keys},
                after_state={key: after[key] for key in changed_keys},
            )
        session.commit()
        session.refresh(category)
        return category
    except IntegrityError as exc:
        session.rollback()
        raise DocumentCategoryConflictError(
            "A category with this code already exists in the organization."
        ) from exc
    except Exception:
        session.rollback()
        raise


def deactivate_document_category(
    session: Session,
    *,
    actor: User,
    category_id: UUID,
) -> None:
    try:
        category = session.scalar(
            select(DocumentCategory).where(DocumentCategory.id == category_id).with_for_update()
        )
        if category is None:
            raise DocumentCategoryNotFoundError("Document category not found.")
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=DOCUMENTS_MANAGE,
            organization_id=category.organization_id,
        )
        if not category.is_active:
            session.commit()
            return
        active_child = session.scalar(
            select(DocumentCategory.id)
            .where(
                DocumentCategory.parent_id == category.id,
                DocumentCategory.is_active.is_(True),
            )
            .limit(1)
        )
        if active_child is not None:
            raise DocumentCategoryConflictError(
                "Deactivate active child categories before this category."
            )
        category.is_active = False
        record_audit_event(
            session,
            actor=actor,
            organization_id=category.organization_id,
            action="document.category.deactivated",
            resource_type="document_category",
            resource_id=category.id,
            before_state={"is_active": True},
            after_state={"is_active": False},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise


def restore_document_category(
    session: Session,
    *,
    actor: User,
    category_id: UUID,
) -> DocumentCategory:
    try:
        category = session.scalar(
            select(DocumentCategory).where(DocumentCategory.id == category_id).with_for_update()
        )
        if category is None:
            raise DocumentCategoryNotFoundError("Document category not found.")
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=DOCUMENTS_MANAGE,
            organization_id=category.organization_id,
        )
        if category.is_active:
            session.commit()
            return category
        if category.parent_id is not None:
            _resolve_active_category(
                session,
                organization_id=category.organization_id,
                category_id=category.parent_id,
            )
        category.is_active = True
        record_audit_event(
            session,
            actor=actor,
            organization_id=category.organization_id,
            action="document.category.restored",
            resource_type="document_category",
            resource_id=category.id,
            before_state={"is_active": False},
            after_state={"is_active": True},
        )
        session.commit()
        session.refresh(category)
        return category
    except Exception:
        session.rollback()
        raise


def list_retention_policies(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None = None,
    include_inactive: bool = False,
) -> list[RetentionPolicy]:
    allowed = _allowed_document_organization_ids(
        session,
        user_id=user_id,
        organization_id=organization_id,
        permission_code=DOCUMENTS_READ,
    )
    if not allowed:
        return []
    statement = select(RetentionPolicy).where(RetentionPolicy.organization_id.in_(allowed))
    if not include_inactive:
        statement = statement.where(RetentionPolicy.is_active.is_(True))
    statement = statement.order_by(
        RetentionPolicy.organization_id,
        RetentionPolicy.name,
        RetentionPolicy.id,
    )
    return list(session.scalars(statement).all())


def create_retention_policy(
    session: Session,
    *,
    actor: User,
    organization_id: UUID,
    code: str,
    name: str,
    description: str | None,
    retention_days: int,
    basis: RetentionBasis,
) -> RetentionPolicy:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=DOCUMENTS_MANAGE,
        organization_id=organization_id,
    )
    try:
        policy = RetentionPolicy(
            organization_id=organization_id,
            code=code.strip().lower(),
            name=" ".join(name.split()),
            description=description,
            retention_days=retention_days,
            basis=basis.value,
            is_active=True,
        )
        session.add(policy)
        session.flush()
        record_audit_event(
            session,
            actor=actor,
            organization_id=organization_id,
            action="document.retention_policy.created",
            resource_type="document_retention_policy",
            resource_id=policy.id,
            after_state={
                "code": policy.code,
                "name": policy.name,
                "retention_days": policy.retention_days,
                "basis": policy.basis,
                "is_active": True,
            },
        )
        session.commit()
        session.refresh(policy)
        return policy
    except IntegrityError as exc:
        session.rollback()
        raise RetentionPolicyConflictError(
            "A retention policy with this code already exists in the organization."
        ) from exc
    except Exception:
        session.rollback()
        raise


def update_retention_policy(
    session: Session,
    *,
    actor: User,
    retention_policy_id: UUID,
    changes: dict[str, object],
) -> RetentionPolicy:
    allowed_fields = {"code", "name", "description", "retention_days", "basis"}
    if not changes or set(changes) - allowed_fields:
        raise DocumentMetadataValidationError("Invalid retention policy update.")
    try:
        policy = session.scalar(
            select(RetentionPolicy)
            .where(RetentionPolicy.id == retention_policy_id)
            .with_for_update()
        )
        if policy is None:
            raise RetentionPolicyNotFoundError("Retention policy not found.")
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=DOCUMENTS_MANAGE,
            organization_id=policy.organization_id,
        )
        before = {
            "code": policy.code,
            "name": policy.name,
            "description": policy.description,
            "retention_days": policy.retention_days,
            "basis": policy.basis,
        }
        if "code" in changes:
            code = changes["code"]
            if not isinstance(code, str) or not code.strip():
                raise DocumentMetadataValidationError("Retention policy code cannot be empty.")
            policy.code = code.strip().lower()
        if "name" in changes:
            name = changes["name"]
            if not isinstance(name, str) or not name.strip():
                raise DocumentMetadataValidationError("Retention policy name cannot be empty.")
            policy.name = " ".join(name.split())
        if "description" in changes:
            description = changes["description"]
            if description is not None and not isinstance(description, str):
                raise DocumentMetadataValidationError("Invalid retention policy description.")
            policy.description = (
                description.strip() or None if isinstance(description, str) else None
            )
        if "retention_days" in changes:
            days = changes["retention_days"]
            if not isinstance(days, int) or isinstance(days, bool) or days < 1 or days > 36500:
                raise DocumentMetadataValidationError("Invalid retention period.")
            policy.retention_days = days
        if "basis" in changes:
            basis = changes["basis"]
            if isinstance(basis, RetentionBasis):
                policy.basis = basis.value
            elif isinstance(basis, str) and basis in {item.value for item in RetentionBasis}:
                policy.basis = basis
            else:
                raise DocumentMetadataValidationError("Invalid retention basis.")
        session.flush()
        after = {
            "code": policy.code,
            "name": policy.name,
            "description": policy.description,
            "retention_days": policy.retention_days,
            "basis": policy.basis,
        }
        changed_keys = [key for key in after if before[key] != after[key]]
        if changed_keys:
            record_audit_event(
                session,
                actor=actor,
                organization_id=policy.organization_id,
                action="document.retention_policy.updated",
                resource_type="document_retention_policy",
                resource_id=policy.id,
                before_state={key: before[key] for key in changed_keys},
                after_state={key: after[key] for key in changed_keys},
                metadata={
                    "existing_document_deadlines_recalculated": False,
                    "reason": "document deadlines are snapshots",
                },
            )
        session.commit()
        session.refresh(policy)
        return policy
    except IntegrityError as exc:
        session.rollback()
        raise RetentionPolicyConflictError(
            "A retention policy with this code already exists in the organization."
        ) from exc
    except Exception:
        session.rollback()
        raise


def deactivate_retention_policy(
    session: Session,
    *,
    actor: User,
    retention_policy_id: UUID,
) -> None:
    try:
        policy = session.scalar(
            select(RetentionPolicy)
            .where(RetentionPolicy.id == retention_policy_id)
            .with_for_update()
        )
        if policy is None:
            raise RetentionPolicyNotFoundError("Retention policy not found.")
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=DOCUMENTS_MANAGE,
            organization_id=policy.organization_id,
        )
        if not policy.is_active:
            session.commit()
            return
        policy.is_active = False
        record_audit_event(
            session,
            actor=actor,
            organization_id=policy.organization_id,
            action="document.retention_policy.deactivated",
            resource_type="document_retention_policy",
            resource_id=policy.id,
            before_state={"is_active": True},
            after_state={"is_active": False},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise


def restore_retention_policy(
    session: Session,
    *,
    actor: User,
    retention_policy_id: UUID,
) -> RetentionPolicy:
    try:
        policy = session.scalar(
            select(RetentionPolicy)
            .where(RetentionPolicy.id == retention_policy_id)
            .with_for_update()
        )
        if policy is None:
            raise RetentionPolicyNotFoundError("Retention policy not found.")
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=DOCUMENTS_MANAGE,
            organization_id=policy.organization_id,
        )
        if policy.is_active:
            session.commit()
            return policy
        policy.is_active = True
        record_audit_event(
            session,
            actor=actor,
            organization_id=policy.organization_id,
            action="document.retention_policy.restored",
            resource_type="document_retention_policy",
            resource_id=policy.id,
            before_state={"is_active": False},
            after_state={"is_active": True},
        )
        session.commit()
        session.refresh(policy)
        return policy
    except Exception:
        session.rollback()
        raise


def list_expiring_documents(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None = None,
    within_days: int = 30,
    include_expired: bool = True,
    limit: int = 100,
    offset: int = 0,
    now: datetime | None = None,
) -> list[Document]:
    allowed = _allowed_document_organization_ids(
        session,
        user_id=user_id,
        organization_id=organization_id,
        permission_code=DOCUMENTS_READ,
    )
    if not allowed:
        return []
    current = now or datetime.now(UTC)
    cutoff = current + timedelta(days=within_days)
    statement = select(Document).where(
        _document_acl_list_condition(
            session,
            user_id=user_id,
            organization_ids=allowed,
            permission_code=DOCUMENTS_READ,
        ),
        Document.expires_at.is_not(None),
        Document.expires_at <= cutoff,
    )
    if not include_expired:
        statement = statement.where(Document.expires_at >= current)
    statement = (
        statement.order_by(Document.expires_at.asc(), Document.id.asc()).offset(offset).limit(limit)
    )
    return list(session.scalars(statement).all())


def list_retention_due_documents(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    now: datetime | None = None,
) -> list[Document]:
    allowed = _allowed_document_organization_ids(
        session,
        user_id=user_id,
        organization_id=organization_id,
        permission_code=DOCUMENTS_READ,
    )
    if not allowed:
        return []
    current = now or datetime.now(UTC)
    statement = (
        select(Document)
        .where(
            _document_acl_list_condition(
                session,
                user_id=user_id,
                organization_ids=allowed,
                permission_code=DOCUMENTS_READ,
            ),
            Document.retention_review_at.is_not(None),
            Document.retention_review_at <= current,
        )
        .order_by(Document.retention_review_at.asc(), Document.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def list_document_timeline(
    session: Session,
    *,
    user_id: UUID,
    document_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEvent]:
    document = get_document_for_user(
        session,
        user_id=user_id,
        document_id=document_id,
        permission_code=DOCUMENTS_READ,
    )
    # Timeline exposes Audit actor/change data, so preserve the central B4
    # audit.read boundary rather than silently creating a second audit surface.
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=AUDIT_READ,
        organization_id=document.organization_id,
    )
    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == document.organization_id,
            AuditEvent.resource_type == "document",
            AuditEvent.resource_id == str(document.id),
        )
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())
