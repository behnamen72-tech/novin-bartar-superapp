from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    actor_identifier: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    before_state: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    event_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    source: Mapped[str] = mapped_column(String(40), nullable=False, default="api")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    actor: Mapped[User | None] = relationship("User")
    organization: Mapped[Organization | None] = relationship("Organization")


from app.core.identity.models import User  # noqa: E402
from app.core.organization.models import Organization  # noqa: E402
