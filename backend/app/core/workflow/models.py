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
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.access.models import OrganizationScopeMode
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowDefinitionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class WorkflowInstanceStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkflowDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "code", "version", name="uq_workflow_definition_org_code_version"
        ),
        CheckConstraint("version > 0", name="ck_workflow_definition_version_positive"),
        Index("ix_workflow_definitions_org_code_status", "organization_id", "code", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scope_mode: Mapped[OrganizationScopeMode] = mapped_column(
        SAEnum(OrganizationScopeMode, name="workflow_definition_scope_mode"),
        nullable=False,
        default=OrganizationScopeMode.SELF,
    )
    status: Mapped[WorkflowDefinitionStatus] = mapped_column(
        SAEnum(WorkflowDefinitionStatus, name="workflow_definition_status"),
        nullable=False,
        default=WorkflowDefinitionStatus.DRAFT,
        index=True,
    )

    organization: Mapped[Organization] = relationship("Organization")
    states: Mapped[list[WorkflowState]] = relationship(
        "WorkflowState", back_populates="definition", cascade="all, delete-orphan"
    )
    transitions: Mapped[list[WorkflowTransition]] = relationship(
        "WorkflowTransition", back_populates="definition", cascade="all, delete-orphan"
    )
    instances: Mapped[list[WorkflowInstance]] = relationship(
        "WorkflowInstance", back_populates="definition"
    )


class WorkflowState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_states"
    __table_args__ = (
        UniqueConstraint("definition_id", "code", name="uq_workflow_state_definition_code"),
        CheckConstraint("position >= 0", name="ck_workflow_state_position_nonnegative"),
        Index("ix_workflow_states_definition_position", "definition_id", "position"),
    )

    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_initial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    definition: Mapped[WorkflowDefinition] = relationship(
        "WorkflowDefinition", back_populates="states"
    )


class WorkflowTransition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (
        UniqueConstraint("definition_id", "code", name="uq_workflow_transition_definition_code"),
        CheckConstraint("from_state_id <> to_state_id", name="ck_workflow_transition_not_self"),
        Index("ix_workflow_transitions_definition_from", "definition_id", "from_state_id"),
    )

    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    from_state_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    to_state_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    definition: Mapped[WorkflowDefinition] = relationship(
        "WorkflowDefinition", back_populates="transitions"
    )
    from_state: Mapped[WorkflowState] = relationship("WorkflowState", foreign_keys=[from_state_id])
    to_state: Mapped[WorkflowState] = relationship("WorkflowState", foreign_keys=[to_state_id])


class WorkflowInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_instances"
    __table_args__ = (
        UniqueConstraint(
            "definition_id",
            "organization_id",
            "resource_type",
            "resource_id",
            name="uq_workflow_instance_definition_resource",
        ),
        Index("ix_workflow_instances_org_status", "organization_id", "status"),
        Index("ix_workflow_instances_resource", "resource_type", "resource_id"),
    )

    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(160), nullable=False)
    current_state_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[WorkflowInstanceStatus] = mapped_column(
        SAEnum(WorkflowInstanceStatus, name="workflow_instance_status"),
        nullable=False,
        default=WorkflowInstanceStatus.ACTIVE,
        index=True,
    )
    started_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    definition: Mapped[WorkflowDefinition] = relationship(
        "WorkflowDefinition", back_populates="instances"
    )
    organization: Mapped[Organization] = relationship("Organization")
    current_state: Mapped[WorkflowState] = relationship("WorkflowState")
    started_by: Mapped[User] = relationship("User")
    history: Mapped[list[WorkflowTransitionRecord]] = relationship(
        "WorkflowTransitionRecord",
        back_populates="instance",
        order_by="WorkflowTransitionRecord.occurred_at",
    )


class WorkflowTransitionRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workflow_transition_records"
    __table_args__ = (
        Index("ix_workflow_transition_records_instance_occurred", "instance_id", "occurred_at"),
    )

    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_instances.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transition_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_transitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    from_state_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False
    )
    to_state_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    instance: Mapped[WorkflowInstance] = relationship("WorkflowInstance", back_populates="history")
    transition: Mapped[WorkflowTransition] = relationship("WorkflowTransition")
    from_state: Mapped[WorkflowState] = relationship("WorkflowState", foreign_keys=[from_state_id])
    to_state: Mapped[WorkflowState] = relationship("WorkflowState", foreign_keys=[to_state_id])
    actor: Mapped[User] = relationship("User")


from app.core.identity.models import User  # noqa: E402
from app.core.organization.models import Organization  # noqa: E402
