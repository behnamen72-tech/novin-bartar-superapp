"""phase b5.5 document operations

Revision ID: 20260910_0010
Revises: 20260910_0009
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0010"
down_revision: str | Sequence[str] | None = "20260910_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_categories",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_document_category_parent_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["document_categories.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "code",
            name="uq_document_category_org_code",
        ),
    )
    op.create_index(
        "ix_document_categories_organization_id",
        "document_categories",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_categories_parent_id",
        "document_categories",
        ["parent_id"],
    )
    op.create_index(
        "ix_document_categories_org_active",
        "document_categories",
        ["organization_id", "is_active"],
    )
    op.create_index(
        "ix_document_categories_parent_active",
        "document_categories",
        ["parent_id", "is_active"],
    )

    op.create_table(
        "document_retention_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("basis", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "retention_days > 0",
            name="ck_document_retention_days_positive",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "code",
            name="uq_document_retention_policy_org_code",
        ),
    )
    op.create_index(
        "ix_document_retention_policies_organization_id",
        "document_retention_policies",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_retention_policies_org_active",
        "document_retention_policies",
        ["organization_id", "is_active"],
    )

    op.add_column("documents", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "priority",
            sa.String(length=40),
            nullable=False,
            server_default="normal",
        ),
    )
    op.add_column("documents", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("retention_policy_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("retention_review_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_category_id",
        "documents",
        "document_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_documents_retention_policy_id",
        "documents",
        "document_retention_policies",
        ["retention_policy_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_documents_category_id", "documents", ["category_id"])
    op.create_index(
        "ix_documents_retention_policy_id",
        "documents",
        ["retention_policy_id"],
    )
    op.create_index("ix_documents_category_status", "documents", ["category_id", "status"])
    op.create_index("ix_documents_expires_at", "documents", ["expires_at"])
    op.create_index(
        "ix_documents_retention_review_at",
        "documents",
        ["retention_review_at"],
    )
    op.create_index("ix_documents_priority", "documents", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_documents_priority", table_name="documents")
    op.drop_index("ix_documents_retention_review_at", table_name="documents")
    op.drop_index("ix_documents_expires_at", table_name="documents")
    op.drop_index("ix_documents_category_status", table_name="documents")
    op.drop_index("ix_documents_retention_policy_id", table_name="documents")
    op.drop_index("ix_documents_category_id", table_name="documents")
    op.drop_constraint(
        "fk_documents_retention_policy_id",
        "documents",
        type_="foreignkey",
    )
    op.drop_constraint("fk_documents_category_id", "documents", type_="foreignkey")
    op.drop_column("documents", "retention_review_at")
    op.drop_column("documents", "retention_policy_id")
    op.drop_column("documents", "expires_at")
    op.drop_column("documents", "category_id")
    op.drop_column("documents", "priority")
    op.drop_column("documents", "description")

    op.drop_index(
        "ix_document_retention_policies_org_active",
        table_name="document_retention_policies",
    )
    op.drop_index(
        "ix_document_retention_policies_organization_id",
        table_name="document_retention_policies",
    )
    op.drop_table("document_retention_policies")

    op.drop_index(
        "ix_document_categories_parent_active",
        table_name="document_categories",
    )
    op.drop_index(
        "ix_document_categories_org_active",
        table_name="document_categories",
    )
    op.drop_index(
        "ix_document_categories_parent_id",
        table_name="document_categories",
    )
    op.drop_index(
        "ix_document_categories_organization_id",
        table_name="document_categories",
    )
    op.drop_table("document_categories")
