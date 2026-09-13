"""D2 customer reference / CRM foundation

Revision ID: 20260911_0016
Revises: 20260911_0015
Create Date: 2026-09-11
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0016"
down_revision: str | Sequence[str] | None = "20260911_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

customer_type = sa.Enum(
    "INDIVIDUAL",
    "HOUSEHOLD",
    "BUSINESS",
    "RETAIL",
    "WHOLESALE",
    "OTHER",
    name="customer_crm_customer_type",
)
commercial_status = sa.Enum(
    "PROSPECT",
    "ACTIVE",
    "INACTIVE",
    "BLOCKED",
    "ARCHIVED",
    name="customer_crm_commercial_status",
)
customer_source = sa.Enum(
    "MANUAL",
    "COMMERCE_ACTIVITY",
    "PHONE_ORDER",
    "IMPORT",
    "OTHER",
    name="customer_crm_source",
)

CRM_PERMISSIONS = (
    ("crm.customer.read", "Read customer CRM", "View organization-scoped customer CRM metadata and references."),
    ("crm.customer.manage", "Manage customer CRM", "Create and change organization-scoped customer CRM metadata."),
    ("crm.customer.notes.read", "Read customer notes", "View customer CRM notes within authorized organization scope."),
    ("crm.customer.notes.manage", "Manage customer notes", "Create and edit customer CRM notes within authorized organization scope."),
    ("crm.customer.assign", "Assign customer owners", "Assign or unassign internal owners for customer CRM records."),
    ("crm.customer.tags.manage", "Manage customer tags", "Create and attach organization-owned CRM tags."),
    ("crm.customer.commerce_activity.read", "Read customer commerce activity", "View authorized commerce activity projections for customer CRM records."),
)


def upgrade() -> None:
    op.create_table(
        "customer_crm_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("commerce_customer_ref", sa.String(length=128), nullable=False),
        sa.Column("customer_type", customer_type, nullable=False),
        sa.Column("commercial_status", commercial_status, nullable=False),
        sa.Column("source", customer_source, nullable=False),
        sa.Column("display_label", sa.String(length=200), nullable=False),
        sa.Column("assigned_owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "commerce_customer_ref", name="uq_customer_crm_org_commerce_ref"),
    )
    op.create_index("ix_customer_crm_records_organization_id", "customer_crm_records", ["organization_id"])
    op.create_index("ix_customer_crm_records_customer_type", "customer_crm_records", ["customer_type"])
    op.create_index("ix_customer_crm_records_commercial_status", "customer_crm_records", ["commercial_status"])
    op.create_index("ix_customer_crm_records_source", "customer_crm_records", ["source"])
    op.create_index("ix_customer_crm_records_assigned_owner_user_id", "customer_crm_records", ["assigned_owner_user_id"])
    op.create_index("ix_customer_crm_records_created_by_user_id", "customer_crm_records", ["created_by_user_id"])
    op.create_index("ix_customer_crm_org_active_status", "customer_crm_records", ["organization_id", "is_active", "commercial_status"])

    op.create_table(
        "customer_tags",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("normalized_name", sa.String(length=60), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "normalized_name", name="uq_customer_tag_org_name"),
    )
    op.create_index("ix_customer_tags_organization_id", "customer_tags", ["organization_id"])
    op.create_index("ix_customer_tags_created_by_user_id", "customer_tags", ["created_by_user_id"])
    op.create_index("ix_customer_tags_org_active", "customer_tags", ["organization_id", "is_active"])

    op.create_table(
        "customer_notes",
        sa.Column("customer_crm_record_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_crm_record_id"], ["customer_crm_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_notes_customer_crm_record_id", "customer_notes", ["customer_crm_record_id"])
    op.create_index("ix_customer_notes_author_user_id", "customer_notes", ["author_user_id"])
    op.create_index("ix_customer_notes_customer_created", "customer_notes", ["customer_crm_record_id", "created_at"])

    op.create_table(
        "customer_crm_tags",
        sa.Column("customer_crm_record_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_crm_record_id"], ["customer_crm_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["customer_tags.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("customer_crm_record_id", "tag_id"),
    )
    op.create_index("ix_customer_crm_tags_created_by_user_id", "customer_crm_tags", ["created_by_user_id"])

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
            for code, name, description in CRM_PERMISSIONS
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE code IN ("
        "'crm.customer.read', 'crm.customer.manage', 'crm.customer.notes.read', "
        "'crm.customer.notes.manage', 'crm.customer.assign', 'crm.customer.tags.manage', "
        "'crm.customer.commerce_activity.read')"
    )
    op.drop_index("ix_customer_crm_tags_created_by_user_id", table_name="customer_crm_tags")
    op.drop_table("customer_crm_tags")

    op.drop_index("ix_customer_notes_customer_created", table_name="customer_notes")
    op.drop_index("ix_customer_notes_author_user_id", table_name="customer_notes")
    op.drop_index("ix_customer_notes_customer_crm_record_id", table_name="customer_notes")
    op.drop_table("customer_notes")

    op.drop_index("ix_customer_tags_org_active", table_name="customer_tags")
    op.drop_index("ix_customer_tags_created_by_user_id", table_name="customer_tags")
    op.drop_index("ix_customer_tags_organization_id", table_name="customer_tags")
    op.drop_table("customer_tags")

    op.drop_index("ix_customer_crm_org_active_status", table_name="customer_crm_records")
    op.drop_index("ix_customer_crm_records_created_by_user_id", table_name="customer_crm_records")
    op.drop_index("ix_customer_crm_records_assigned_owner_user_id", table_name="customer_crm_records")
    op.drop_index("ix_customer_crm_records_source", table_name="customer_crm_records")
    op.drop_index("ix_customer_crm_records_commercial_status", table_name="customer_crm_records")
    op.drop_index("ix_customer_crm_records_customer_type", table_name="customer_crm_records")
    op.drop_index("ix_customer_crm_records_organization_id", table_name="customer_crm_records")
    op.drop_table("customer_crm_records")

    customer_source.drop(op.get_bind(), checkfirst=True)
    commercial_status.drop(op.get_bind(), checkfirst=True)
    customer_type.drop(op.get_bind(), checkfirst=True)
