"""C2 notifications core

Revision ID: 20260911_0014
Revises: 20260911_0013
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0014"
down_revision: str | Sequence[str] | None = "20260911_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

notification_severity = sa.Enum(
    "INFO",
    "SUCCESS",
    "WARNING",
    "CRITICAL",
    name="notification_severity",
)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("event_code", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("severity", notification_severity, nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=160), nullable=True),
        sa.Column("action_path", sa.String(length=500), nullable=True),
        sa.Column("dedupe_key", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipient_user_id", "dedupe_key", name="uq_notifications_recipient_dedupe_key"),
    )
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_event_code", "notifications", ["event_code"])
    op.create_index("ix_notifications_source", "notifications", ["source"])
    op.create_index("ix_notifications_severity", "notifications", ["severity"])
    op.create_index("ix_notifications_resource_type", "notifications", ["resource_type"])
    op.create_index("ix_notifications_resource_id", "notifications", ["resource_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_read_at", "notifications", ["read_at"])
    op.create_index("ix_notifications_recipient_created", "notifications", ["recipient_user_id", "created_at"])
    op.create_index("ix_notifications_recipient_read_created", "notifications", ["recipient_user_id", "read_at", "created_at"])
    op.create_index("ix_notifications_organization_created", "notifications", ["organization_id", "created_at"])

    # Content/ownership are immutable; only read_at may change. Physical delete
    # is forbidden so a recipient cannot rewrite notification history.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_notification_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'notifications cannot be physically deleted';
            END IF;

            IF NEW.recipient_user_id IS DISTINCT FROM OLD.recipient_user_id
               OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
               OR NEW.event_code IS DISTINCT FROM OLD.event_code
               OR NEW.source IS DISTINCT FROM OLD.source
               OR NEW.severity IS DISTINCT FROM OLD.severity
               OR NEW.title IS DISTINCT FROM OLD.title
               OR NEW.body IS DISTINCT FROM OLD.body
               OR NEW.resource_type IS DISTINCT FROM OLD.resource_type
               OR NEW.resource_id IS DISTINCT FROM OLD.resource_id
               OR NEW.action_path IS DISTINCT FROM OLD.action_path
               OR NEW.dedupe_key IS DISTINCT FROM OLD.dedupe_key
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.id IS DISTINCT FROM OLD.id THEN
                RAISE EXCEPTION 'notification content and ownership are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_notifications_protected
        BEFORE UPDATE OR DELETE ON notifications
        FOR EACH ROW
        EXECUTE FUNCTION protect_notification_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_notifications_protected ON notifications;")
    op.execute("DROP FUNCTION IF EXISTS protect_notification_mutation();")

    op.drop_index("ix_notifications_organization_created", table_name="notifications")
    op.drop_index("ix_notifications_recipient_read_created", table_name="notifications")
    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_index("ix_notifications_read_at", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_resource_id", table_name="notifications")
    op.drop_index("ix_notifications_resource_type", table_name="notifications")
    op.drop_index("ix_notifications_severity", table_name="notifications")
    op.drop_index("ix_notifications_source", table_name="notifications")
    op.drop_index("ix_notifications_event_code", table_name="notifications")
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_table("notifications")
    notification_severity.drop(op.get_bind(), checkfirst=True)
