from __future__ import annotations

from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationType(str, Enum):
    HOLDING = "holding"
    COMPANY = "company"
    BRANCH = "branch"
    UNIT = "unit"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_organizations_parent_not_self",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    organization_type: Mapped[OrganizationType] = mapped_column(
        SAEnum(OrganizationType, name="organization_type"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped[Organization | None] = relationship(
        "Organization",
        remote_side="Organization.id",
        back_populates="children",
    )
    children: Mapped[list[Organization]] = relationship(
        "Organization",
        back_populates="parent",
    )
