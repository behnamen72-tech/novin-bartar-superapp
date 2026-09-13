"""D3 suppliers foundation

Revision ID: 20260911_0017
Revises: 20260911_0016
Create Date: 2026-09-11
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "20260911_0017"
down_revision: str | Sequence[str] | None = "20260911_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

supplier_kind = sa.Enum("COMPANY", "INDIVIDUAL", "OTHER", name="supplier_kind")
supplier_status = sa.Enum(
    "PROSPECT", "ACTIVE", "INACTIVE", "SUSPENDED", "ARCHIVED", name="supplier_commercial_status"
)
supplier_source = sa.Enum(
    "MANUAL", "IMPORT", "ACCOUNTING_REFERENCE", "PROCUREMENT_REFERENCE", "OTHER", name="supplier_source"
)
external_system = sa.Enum("ACCOUNTING", "ERP", "PROCUREMENT", "OTHER", name="supplier_external_system")

SUPPLIER_PERMISSIONS = (
    ("supplier.read", "Read suppliers", "View organization-scoped supplier operational metadata."),
    ("supplier.manage", "Manage suppliers", "Create and update organization-scoped supplier operational metadata."),
    ("supplier.representative.read", "Read supplier representatives", "View supplier representatives in authorized supplier scope."),
    ("supplier.representative.manage", "Manage supplier representatives", "Create and update supplier representatives in authorized supplier scope."),
    ("supplier.representative.contact.read", "Read supplier representative contacts", "View unmasked representative phone and email values."),
    ("supplier.notes.read", "Read supplier notes", "View supplier notes within authorized organization scope."),
    ("supplier.notes.manage", "Manage supplier notes", "Create and edit supplier notes within authorized organization scope."),
    ("supplier.assign", "Assign supplier owners", "Assign or unassign internal owners for supplier records."),
    ("supplier.tags.catalog.manage", "Manage supplier tag catalog", "Create organization-owned supplier tag vocabulary."),
    ("supplier.tags.assign", "Assign supplier tags", "Attach or remove existing organization-owned tags on suppliers."),
    ("supplier.external_reference.read", "Read supplier external references", "View supplier external-system reference metadata."),
    ("supplier.external_reference.manage", "Manage supplier external references", "Create and remove supplier external-system references."),
)


def upgrade() -> None:
    op.create_table(
        "supplier_profiles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_kind", supplier_kind, nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("commercial_status", supplier_status, nullable=False),
        sa.Column("source", supplier_source, nullable=False),
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
    )
    op.create_index("ix_supplier_profiles_organization_id", "supplier_profiles", ["organization_id"])
    op.create_index("ix_supplier_profiles_supplier_kind", "supplier_profiles", ["supplier_kind"])
    op.create_index("ix_supplier_profiles_commercial_status", "supplier_profiles", ["commercial_status"])
    op.create_index("ix_supplier_profiles_source", "supplier_profiles", ["source"])
    op.create_index("ix_supplier_profiles_assigned_owner_user_id", "supplier_profiles", ["assigned_owner_user_id"])
    op.create_index("ix_supplier_profiles_created_by_user_id", "supplier_profiles", ["created_by_user_id"])
    op.create_index("ix_supplier_profiles_org_active_status", "supplier_profiles", ["organization_id", "is_active", "commercial_status"])

    op.create_table(
        "supplier_representatives",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_representatives_supplier_id", "supplier_representatives", ["supplier_id"])
    op.create_index("ix_supplier_representatives_supplier_active", "supplier_representatives", ["supplier_id", "is_active"])
    op.create_index(
        "uq_supplier_representative_active_primary",
        "supplier_representatives",
        ["supplier_id"],
        unique=True,
        postgresql_where=sa.text("is_primary IS TRUE AND is_active IS TRUE"),
        sqlite_where=sa.text("is_primary = 1 AND is_active = 1"),
    )

    op.create_table(
        "supplier_tags",
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
        sa.UniqueConstraint("organization_id", "normalized_name", name="uq_supplier_tag_org_name"),
    )
    op.create_index("ix_supplier_tags_organization_id", "supplier_tags", ["organization_id"])
    op.create_index("ix_supplier_tags_created_by_user_id", "supplier_tags", ["created_by_user_id"])
    op.create_index("ix_supplier_tags_org_active", "supplier_tags", ["organization_id", "is_active"])

    op.create_table(
        "supplier_notes",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_notes_supplier_id", "supplier_notes", ["supplier_id"])
    op.create_index("ix_supplier_notes_author_user_id", "supplier_notes", ["author_user_id"])
    op.create_index("ix_supplier_notes_supplier_created", "supplier_notes", ["supplier_id", "created_at"])

    op.create_table(
        "supplier_profile_tags",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["supplier_tags.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("supplier_id", "tag_id"),
    )
    op.create_index("ix_supplier_profile_tags_created_by_user_id", "supplier_profile_tags", ["created_by_user_id"])

    op.create_table(
        "supplier_external_references",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("system", external_system, nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("normalized_external_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "system", "normalized_external_id", name="uq_supplier_external_ref_org_system_id"),
    )
    op.create_index("ix_supplier_external_references_supplier_id", "supplier_external_references", ["supplier_id"])
    op.create_index("ix_supplier_external_references_organization_id", "supplier_external_references", ["organization_id"])
    op.create_index("ix_supplier_external_references_system", "supplier_external_references", ["system"])
    op.create_index("ix_supplier_external_references_created_by_user_id", "supplier_external_references", ["created_by_user_id"])
    op.create_index("ix_supplier_external_refs_supplier", "supplier_external_references", ["supplier_id", "system"])

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        permissions,
        [
            {"id": uuid4(), "code": code, "name": name, "description": description}
            for code, name, description in SUPPLIER_PERMISSIONS
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE code LIKE 'supplier.%'"
    )

    op.drop_index("ix_supplier_external_refs_supplier", table_name="supplier_external_references")
    op.drop_index("ix_supplier_external_references_created_by_user_id", table_name="supplier_external_references")
    op.drop_index("ix_supplier_external_references_system", table_name="supplier_external_references")
    op.drop_index("ix_supplier_external_references_organization_id", table_name="supplier_external_references")
    op.drop_index("ix_supplier_external_references_supplier_id", table_name="supplier_external_references")
    op.drop_table("supplier_external_references")

    op.drop_index("ix_supplier_profile_tags_created_by_user_id", table_name="supplier_profile_tags")
    op.drop_table("supplier_profile_tags")

    op.drop_index("ix_supplier_notes_supplier_created", table_name="supplier_notes")
    op.drop_index("ix_supplier_notes_author_user_id", table_name="supplier_notes")
    op.drop_index("ix_supplier_notes_supplier_id", table_name="supplier_notes")
    op.drop_table("supplier_notes")

    op.drop_index("ix_supplier_tags_org_active", table_name="supplier_tags")
    op.drop_index("ix_supplier_tags_created_by_user_id", table_name="supplier_tags")
    op.drop_index("ix_supplier_tags_organization_id", table_name="supplier_tags")
    op.drop_table("supplier_tags")

    op.drop_index("uq_supplier_representative_active_primary", table_name="supplier_representatives")
    op.drop_index("ix_supplier_representatives_supplier_active", table_name="supplier_representatives")
    op.drop_index("ix_supplier_representatives_supplier_id", table_name="supplier_representatives")
    op.drop_table("supplier_representatives")

    op.drop_index("ix_supplier_profiles_org_active_status", table_name="supplier_profiles")
    op.drop_index("ix_supplier_profiles_created_by_user_id", table_name="supplier_profiles")
    op.drop_index("ix_supplier_profiles_assigned_owner_user_id", table_name="supplier_profiles")
    op.drop_index("ix_supplier_profiles_source", table_name="supplier_profiles")
    op.drop_index("ix_supplier_profiles_commercial_status", table_name="supplier_profiles")
    op.drop_index("ix_supplier_profiles_supplier_kind", table_name="supplier_profiles")
    op.drop_index("ix_supplier_profiles_organization_id", table_name="supplier_profiles")
    op.drop_table("supplier_profiles")

    external_system.drop(op.get_bind(), checkfirst=True)
    supplier_source.drop(op.get_bind(), checkfirst=True)
    supplier_status.drop(op.get_bind(), checkfirst=True)
    supplier_kind.drop(op.get_bind(), checkfirst=True)
