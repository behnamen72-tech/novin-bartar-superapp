from __future__ import annotations

from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SupplierKind(str, Enum):
    COMPANY = "company"
    INDIVIDUAL = "individual"
    OTHER = "other"


class SupplierCommercialStatus(str, Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class SupplierSource(str, Enum):
    MANUAL = "manual"
    IMPORT = "import"
    ACCOUNTING_REFERENCE = "accounting_reference"
    PROCUREMENT_REFERENCE = "procurement_reference"
    OTHER = "other"


class SupplierExternalSystem(str, Enum):
    ACCOUNTING = "accounting"
    ERP = "erp"
    PROCUREMENT = "procurement"
    OTHER = "other"


class SupplierProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_profiles"
    __table_args__ = (
        Index(
            "ix_supplier_profiles_org_active_status",
            "organization_id",
            "is_active",
            "commercial_status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_kind: Mapped[SupplierKind] = mapped_column(
        SAEnum(SupplierKind, name="supplier_kind"), nullable=False, default=SupplierKind.COMPANY, index=True
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    commercial_status: Mapped[SupplierCommercialStatus] = mapped_column(
        SAEnum(SupplierCommercialStatus, name="supplier_commercial_status"),
        nullable=False,
        default=SupplierCommercialStatus.PROSPECT,
        index=True,
    )
    source: Mapped[SupplierSource] = mapped_column(
        SAEnum(SupplierSource, name="supplier_source"), nullable=False, default=SupplierSource.MANUAL, index=True
    )
    assigned_owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    organization: Mapped["Organization"] = relationship("Organization")
    assigned_owner: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_owner_user_id])
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    representatives: Mapped[list["SupplierRepresentative"]] = relationship(
        "SupplierRepresentative", back_populates="supplier", cascade="all, delete-orphan"
    )
    notes: Mapped[list["SupplierNote"]] = relationship(
        "SupplierNote", back_populates="supplier", cascade="all, delete-orphan"
    )
    tag_links: Mapped[list["SupplierProfileTag"]] = relationship(
        "SupplierProfileTag", back_populates="supplier", cascade="all, delete-orphan"
    )
    external_references: Mapped[list["SupplierExternalReference"]] = relationship(
        "SupplierExternalReference", back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierRepresentative(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_representatives"
    __table_args__ = (
        Index("ix_supplier_representatives_supplier_active", "supplier_id", "is_active"),
        Index(
            "uq_supplier_representative_active_primary",
            "supplier_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE AND is_active IS TRUE"),
            sqlite_where=text("is_primary = 1 AND is_active = 1"),
        ),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    supplier: Mapped[SupplierProfile] = relationship("SupplierProfile", back_populates="representatives")


class SupplierTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_tags"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", name="uq_supplier_tag_org_name"),
        Index("ix_supplier_tags_org_active", "organization_id", "is_active"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(60), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped["User"] = relationship("User")
    supplier_links: Mapped[list["SupplierProfileTag"]] = relationship(
        "SupplierProfileTag", back_populates="tag", cascade="all, delete-orphan"
    )


class SupplierProfileTag(TimestampMixin, Base):
    __tablename__ = "supplier_profile_tags"

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_tags.id", ondelete="RESTRICT"), primary_key=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    supplier: Mapped[SupplierProfile] = relationship("SupplierProfile", back_populates="tag_links")
    tag: Mapped[SupplierTag] = relationship("SupplierTag", back_populates="supplier_links")
    created_by: Mapped["User"] = relationship("User")


class SupplierNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_notes"
    __table_args__ = (Index("ix_supplier_notes_supplier_created", "supplier_id", "created_at"),)

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    supplier: Mapped[SupplierProfile] = relationship("SupplierProfile", back_populates="notes")
    author: Mapped["User"] = relationship("User")


class SupplierExternalReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_external_references"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "system", "normalized_external_id", name="uq_supplier_external_ref_org_system_id"
        ),
        Index("ix_supplier_external_refs_supplier", "supplier_id", "system"),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    system: Mapped[SupplierExternalSystem] = mapped_column(
        SAEnum(SupplierExternalSystem, name="supplier_external_system"), nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    supplier: Mapped[SupplierProfile] = relationship("SupplierProfile", back_populates="external_references")
    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped["User"] = relationship("User")


from app.core.identity.models import User  # noqa: E402
from app.core.organization.models import Organization  # noqa: E402
