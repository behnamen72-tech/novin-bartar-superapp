from __future__ import annotations

from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CustomerType(str, Enum):
    INDIVIDUAL = "individual"
    HOUSEHOLD = "household"
    BUSINESS = "business"
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    OTHER = "other"


class CommercialStatus(str, Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


class CustomerSource(str, Enum):
    MANUAL = "manual"
    COMMERCE_ACTIVITY = "commerce_activity"
    PHONE_ORDER = "phone_order"
    IMPORT = "import"
    OTHER = "other"


class CustomerCRMRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Organization-owned CRM metadata for an external Commerce customer.

    ``commerce_customer_ref`` is an opaque external reference, not a foreign key.
    This record never becomes an Internal User/Person/Employee identity.
    """

    __tablename__ = "customer_crm_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "commerce_customer_ref",
            name="uq_customer_crm_org_commerce_ref",
        ),
        Index(
            "ix_customer_crm_org_active_status",
            "organization_id",
            "is_active",
            "commercial_status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    commerce_customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_type: Mapped[CustomerType] = mapped_column(
        SAEnum(CustomerType, name="customer_crm_customer_type"),
        nullable=False,
        default=CustomerType.INDIVIDUAL,
        index=True,
    )
    commercial_status: Mapped[CommercialStatus] = mapped_column(
        SAEnum(CommercialStatus, name="customer_crm_commercial_status"),
        nullable=False,
        default=CommercialStatus.PROSPECT,
        index=True,
    )
    source: Mapped[CustomerSource] = mapped_column(
        SAEnum(CustomerSource, name="customer_crm_source"),
        nullable=False,
        default=CustomerSource.MANUAL,
        index=True,
    )
    display_label: Mapped[str] = mapped_column(String(200), nullable=False)
    assigned_owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    organization: Mapped["Organization"] = relationship("Organization")
    assigned_owner: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assigned_owner_user_id]
    )
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    notes: Mapped[list["CustomerNote"]] = relationship(
        "CustomerNote", back_populates="customer", cascade="all, delete-orphan"
    )
    tag_links: Mapped[list["CustomerCRMTag"]] = relationship(
        "CustomerCRMTag", back_populates="customer", cascade="all, delete-orphan"
    )


class CustomerTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_tags"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "normalized_name", name="uq_customer_tag_org_name"
        ),
        Index("ix_customer_tags_org_active", "organization_id", "is_active"),
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
    customer_links: Mapped[list["CustomerCRMTag"]] = relationship(
        "CustomerCRMTag", back_populates="tag", cascade="all, delete-orphan"
    )


class CustomerCRMTag(TimestampMixin, Base):
    __tablename__ = "customer_crm_tags"

    customer_crm_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_crm_records.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_tags.id", ondelete="RESTRICT"), primary_key=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    customer: Mapped[CustomerCRMRecord] = relationship(
        "CustomerCRMRecord", back_populates="tag_links"
    )
    tag: Mapped[CustomerTag] = relationship("CustomerTag", back_populates="customer_links")
    created_by: Mapped["User"] = relationship("User")


class CustomerNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_notes"
    __table_args__ = (
        Index("ix_customer_notes_customer_created", "customer_crm_record_id", "created_at"),
    )

    customer_crm_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_crm_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    customer: Mapped[CustomerCRMRecord] = relationship(
        "CustomerCRMRecord", back_populates="notes"
    )
    author: Mapped["User"] = relationship("User")


from app.core.identity.models import User  # noqa: E402
from app.core.organization.models import Organization  # noqa: E402
