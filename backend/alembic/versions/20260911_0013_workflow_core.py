"""C1 workflow core foundation

Revision ID: 20260911_0013
Revises: 20260910_0012
Create Date: 2026-09-11
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0013"
down_revision: str | Sequence[str] | None = "20260910_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

workflow_scope_mode = sa.Enum("SELF", "SELF_AND_DESCENDANTS", name="workflow_definition_scope_mode")
workflow_definition_status = sa.Enum("DRAFT", "PUBLISHED", "RETIRED", name="workflow_definition_status")
workflow_instance_status = sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="workflow_instance_status")

WORKFLOW_PERMISSIONS = (
    (
        "workflow.read",
        "Read workflows",
        "View workflow definitions and instances within authorized organization scope.",
    ),
    (
        "workflow.manage",
        "Manage workflows",
        "Create, version, publish, and retire workflow definitions within authorized scope.",
    ),
    (
        "workflow.execute",
        "Execute workflows",
        "Start and advance workflow instances within authorized organization scope.",
    ),
)


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("scope_mode", workflow_scope_mode, nullable=False),
        sa.Column("status", workflow_definition_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_workflow_definition_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", "version", name="uq_workflow_definition_org_code_version"),
    )
    op.create_index("ix_workflow_definitions_organization_id", "workflow_definitions", ["organization_id"])
    op.create_index("ix_workflow_definitions_status", "workflow_definitions", ["status"])
    op.create_index("ix_workflow_definitions_org_code_status", "workflow_definitions", ["organization_id", "code", "status"])

    op.create_table(
        "workflow_states",
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_workflow_state_position_nonnegative"),
        sa.ForeignKeyConstraint(["definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "code", name="uq_workflow_state_definition_code"),
    )
    op.create_index("ix_workflow_states_definition_id", "workflow_states", ["definition_id"])
    op.create_index("ix_workflow_states_definition_position", "workflow_states", ["definition_id", "position"])

    op.create_table(
        "workflow_transitions",
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("from_state_id", sa.Uuid(), nullable=False),
        sa.Column("to_state_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("from_state_id <> to_state_id", name="ck_workflow_transition_not_self"),
        sa.ForeignKeyConstraint(["definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "code", name="uq_workflow_transition_definition_code"),
    )
    op.create_index("ix_workflow_transitions_definition_id", "workflow_transitions", ["definition_id"])
    op.create_index("ix_workflow_transitions_from_state_id", "workflow_transitions", ["from_state_id"])
    op.create_index("ix_workflow_transitions_to_state_id", "workflow_transitions", ["to_state_id"])
    op.create_index("ix_workflow_transitions_definition_from", "workflow_transitions", ["definition_id", "from_state_id"])

    op.create_table(
        "workflow_instances",
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=160), nullable=False),
        sa.Column("current_state_id", sa.Uuid(), nullable=False),
        sa.Column("status", workflow_instance_status, nullable=False),
        sa.Column("started_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["workflow_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "organization_id", "resource_type", "resource_id", name="uq_workflow_instance_definition_resource"),
    )
    op.create_index("ix_workflow_instances_definition_id", "workflow_instances", ["definition_id"])
    op.create_index("ix_workflow_instances_organization_id", "workflow_instances", ["organization_id"])
    op.create_index("ix_workflow_instances_current_state_id", "workflow_instances", ["current_state_id"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])
    op.create_index("ix_workflow_instances_started_by_user_id", "workflow_instances", ["started_by_user_id"])
    op.create_index("ix_workflow_instances_org_status", "workflow_instances", ["organization_id", "status"])
    op.create_index("ix_workflow_instances_resource", "workflow_instances", ["resource_type", "resource_id"])

    op.create_table(
        "workflow_transition_records",
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("transition_id", sa.Uuid(), nullable=False),
        sa.Column("from_state_id", sa.Uuid(), nullable=False),
        sa.Column("to_state_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["workflow_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transition_id"], ["workflow_transitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_transition_records_instance_id", "workflow_transition_records", ["instance_id"])
    op.create_index("ix_workflow_transition_records_transition_id", "workflow_transition_records", ["transition_id"])
    op.create_index("ix_workflow_transition_records_actor_user_id", "workflow_transition_records", ["actor_user_id"])
    op.create_index("ix_workflow_transition_records_instance_occurred", "workflow_transition_records", ["instance_id", "occurred_at"])

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        permissions_table,
        [
            {"id": uuid4(), "code": code, "name": name, "description": description}
            for code, name, description in WORKFLOW_PERMISSIONS
        ],
    )

    # Keep the canonical bootstrap super-admin role current during upgrades.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
        SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.code = 'super_admin'
          AND p.code IN ('workflow.read', 'workflow.manage', 'workflow.execute')
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          );
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_workflow_transition_record_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'workflow_transition_records are immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_workflow_transition_records_immutable
        BEFORE UPDATE OR DELETE ON workflow_transition_records
        FOR EACH ROW
        EXECUTE FUNCTION prevent_workflow_transition_record_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_workflow_transition_records_immutable ON workflow_transition_records;")
    op.execute("DROP FUNCTION IF EXISTS prevent_workflow_transition_record_mutation();")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('workflow.read', 'workflow.manage', 'workflow.execute'));"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('workflow.read', 'workflow.manage', 'workflow.execute');")

    op.drop_index("ix_workflow_transition_records_instance_occurred", table_name="workflow_transition_records")
    op.drop_index("ix_workflow_transition_records_actor_user_id", table_name="workflow_transition_records")
    op.drop_index("ix_workflow_transition_records_transition_id", table_name="workflow_transition_records")
    op.drop_index("ix_workflow_transition_records_instance_id", table_name="workflow_transition_records")
    op.drop_table("workflow_transition_records")

    op.drop_index("ix_workflow_instances_resource", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_org_status", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_started_by_user_id", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_status", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_current_state_id", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_organization_id", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_definition_id", table_name="workflow_instances")
    op.drop_table("workflow_instances")

    op.drop_index("ix_workflow_transitions_definition_from", table_name="workflow_transitions")
    op.drop_index("ix_workflow_transitions_to_state_id", table_name="workflow_transitions")
    op.drop_index("ix_workflow_transitions_from_state_id", table_name="workflow_transitions")
    op.drop_index("ix_workflow_transitions_definition_id", table_name="workflow_transitions")
    op.drop_table("workflow_transitions")

    op.drop_index("ix_workflow_states_definition_position", table_name="workflow_states")
    op.drop_index("ix_workflow_states_definition_id", table_name="workflow_states")
    op.drop_table("workflow_states")

    op.drop_index("ix_workflow_definitions_org_code_status", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_status", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_organization_id", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")

    workflow_instance_status.drop(op.get_bind(), checkfirst=True)
    workflow_definition_status.drop(op.get_bind(), checkfirst=True)
    workflow_scope_mode.drop(op.get_bind(), checkfirst=True)
