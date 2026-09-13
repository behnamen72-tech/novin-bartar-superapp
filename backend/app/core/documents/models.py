from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DISABLED = "disabled"


class DocumentPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentLinkEntityType(str, Enum):
    # B5.3 intentionally enables only targets whose domain tables and
    # organization-membership rules already exist. New business modules can add
    # their entity type here together with a validator in documents.service.
    ORGANIZATION = "organization"
    PERSON = "person"


class DocumentPermissionType(str, Enum):
    READ = "read"
    MANAGE = "manage"


class RetentionBasis(str, Enum):
    CREATED_AT = "created_at"
    EXPIRES_AT = "expires_at"


class DocumentCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_categories"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_document_category_org_code",
        ),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_document_category_parent_not_self"),
        Index("ix_document_categories_org_active", "organization_id", "is_active"),
        Index("ix_document_categories_parent_active", "parent_id", "is_active"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped[DocumentCategory | None] = relationship(
        "DocumentCategory",
        remote_side="DocumentCategory.id",
        back_populates="children",
    )
    children: Mapped[list[DocumentCategory]] = relationship(
        "DocumentCategory",
        back_populates="parent",
    )
    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="category",
    )


class RetentionPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_document_retention_policy_org_code",
        ),
        CheckConstraint("retention_days > 0", name="ck_document_retention_days_positive"),
        Index("ix_document_retention_policies_org_active", "organization_id", "is_active"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    basis: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="retention_policy",
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_organization_status", "organization_id", "status"),
        Index("ix_documents_category_status", "category_id", "status"),
        Index("ix_documents_expires_at", "expires_at"),
        Index("ix_documents_retention_review_at", "retention_review_at"),
        Index("ix_documents_priority", "priority"),
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=DocumentPriority.NORMAL.value,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        String(40),
        nullable=False,
        default=DocumentStatus.ACTIVE,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retention_policy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_retention_policies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # Snapshot deadline calculated when a policy is assigned or its basis input
    # changes. Editing a policy later does not silently rewrite old documents.
    retention_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    category: Mapped[DocumentCategory | None] = relationship(
        "DocumentCategory",
        back_populates="documents",
    )
    retention_policy: Mapped[RetentionPolicy | None] = relationship(
        "RetentionPolicy",
        back_populates="documents",
    )
    versions: Mapped[list[DocumentVersion]] = relationship(
        "DocumentVersion",
        back_populates="document",
        order_by="DocumentVersion.version_number",
    )
    links: Mapped[list[DocumentLink]] = relationship(
        "DocumentLink",
        back_populates="document",
        order_by="DocumentLink.created_at",
    )
    permissions: Mapped[list[DocumentPermission]] = relationship(
        "DocumentPermission",
        back_populates="document",
        order_by="DocumentPermission.created_at",
    )


class StorageObject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "storage_objects"

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    # Provider-relative object key. Never store a public URL or host-specific absolute path.
    object_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    storage_object_id: Mapped[UUID] = mapped_column(
        ForeignKey("storage_objects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)

    document: Mapped[Document] = relationship("Document", back_populates="versions")
    storage_object: Mapped[StorageObject] = relationship("StorageObject")


class DocumentLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_links"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "entity_type",
            "entity_id",
            name="uq_document_link_target",
        ),
        Index(
            "ix_document_links_entity_active",
            "entity_type",
            "entity_id",
            "is_active",
        ),
        Index(
            "ix_document_links_document_active",
            "document_id",
            "is_active",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Links are never physically deleted by the B5.3 API. Unlinking only flips
    # this flag, preserving relationship history while Audit records the actor.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    document: Mapped[Document] = relationship("Document", back_populates="links")


class DocumentPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "role_id",
            "permission_type",
            name="uq_document_permission_role_type",
        ),
        Index(
            "ix_document_permissions_document_active_type",
            "document_id",
            "is_active",
            "permission_type",
        ),
        Index(
            "ix_document_permissions_role_active",
            "role_id",
            "is_active",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    permission_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    document: Mapped[Document] = relationship("Document", back_populates="permissions")
