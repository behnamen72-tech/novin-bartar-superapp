from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "people"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization_relationships: Mapped[list[PersonOrganizationRelationship]] = relationship(
        "PersonOrganizationRelationship",
        back_populates="person",
        cascade="all, delete-orphan",
    )
    user: Mapped[User | None] = relationship(
        "User",
        back_populates="person",
        uselist=False,
    )


class PersonOrganizationRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "person_organization_relationships"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_person_org_relationship_date_range",
        ),
    )

    person_id: Mapped[UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Business relationship, not an access-control role.
    # Examples: employee, manager, customer_contact, contractor.
    relationship_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    person: Mapped[Person] = relationship(
        "Person",
        back_populates="organization_relationships",
    )
    organization: Mapped[Organization] = relationship("Organization")


from app.core.identity.models import User  # noqa: E402
from app.core.organization.models import Organization  # noqa: E402
