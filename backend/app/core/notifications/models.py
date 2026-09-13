from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin


class NotificationSeverity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "recipient_user_id",
            "dedupe_key",
            name="uq_notifications_recipient_dedupe_key",
        ),
        Index(
            "ix_notifications_recipient_created",
            "recipient_user_id",
            "created_at",
        ),
        Index(
            "ix_notifications_recipient_read_created",
            "recipient_user_id",
            "read_at",
            "created_at",
        ),
        Index(
            "ix_notifications_organization_created",
            "organization_id",
            "created_at",
        ),
    )

    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    event_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="system", index=True)
    severity: Mapped[NotificationSeverity] = mapped_column(
        SAEnum(NotificationSeverity, name="notification_severity"),
        nullable=False,
        default=NotificationSeverity.INFO,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str | None] = mapped_column(Text(), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    action_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    recipient: Mapped[User] = relationship("User")
    organization: Mapped[Organization | None] = relationship("Organization")


from app.core.identity.models import User  # noqa: E402
from app.core.organization.models import Organization  # noqa: E402
