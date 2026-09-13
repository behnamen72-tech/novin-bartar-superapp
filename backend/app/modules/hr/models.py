from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.access.models import OrganizationScopeMode
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EmploymentType(StrEnum):
    PERMANENT = "permanent"
    FIXED_TERM = "fixed_term"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"
    OTHER = "other"


class HRJobProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Reusable job definition owned by an organization.

    A profile can be limited to the owner organization or made available to
    descendants. It is intentionally separate from Access roles: this is a
    business/HR concept and never grants application permissions.
    """

    __tablename__ = "hr_job_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_hr_job_profile_org_code",
        ),
        Index(
            "ix_hr_job_profiles_org_active",
            "organization_id",
            "is_active",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    scope_mode: Mapped[OrganizationScopeMode] = mapped_column(
        SAEnum(OrganizationScopeMode, name="hr_job_profile_scope_mode"),
        nullable=False,
        default=OrganizationScopeMode.SELF,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped[Organization] = relationship("Organization")
    positions: Mapped[list[HRPosition]] = relationship(
        "HRPosition",
        back_populates="job_profile",
    )


class HRPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A planned organizational seat.

    Positions can exist before anybody is hired, which makes the HR foundation
    useful for future organization design rather than assuming an existing
    workforce.
    """

    __tablename__ = "hr_positions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_hr_position_org_code",
        ),
        CheckConstraint(
            "reports_to_position_id IS NULL OR reports_to_position_id <> id",
            name="ck_hr_position_reports_to_not_self",
        ),
        Index(
            "ix_hr_positions_org_active",
            "organization_id",
            "is_active",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("hr_job_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    reports_to_position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hr_positions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped[Organization] = relationship("Organization")
    job_profile: Mapped[HRJobProfile] = relationship(
        "HRJobProfile",
        back_populates="positions",
    )
    reports_to: Mapped[HRPosition | None] = relationship(
        "HRPosition",
        remote_side="HRPosition.id",
        foreign_keys=[reports_to_position_id],
    )
    employments: Mapped[list[HREmployment]] = relationship(
        "HREmployment",
        back_populates="position",
    )


class HREmployment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Organization-scoped employment/engagement record for an existing Person."""

    __tablename__ = "hr_employments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "employment_number",
            name="uq_hr_employment_org_number",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_hr_employment_date_range",
        ),
        Index(
            "ix_hr_employments_org_active",
            "organization_id",
            "is_active",
        ),
        Index(
            "ix_hr_employments_person_org_active",
            "person_id",
            "organization_id",
            "is_active",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[UUID] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hr_positions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    employment_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, name="hr_employment_type"),
        nullable=False,
        default=EmploymentType.OTHER,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped[Organization] = relationship("Organization")
    person: Mapped[Person] = relationship("Person")
    position: Mapped[HRPosition | None] = relationship(
        "HRPosition",
        back_populates="employments",
    )


from app.core.organization.models import Organization  # noqa: E402
from app.core.people.models import Person  # noqa: E402
