"""phase b5.2 documents api version creator attribution

Revision ID: 20260909_0006
Revises: 20260909_0005
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_0006"
down_revision: str | Sequence[str] | None = "20260909_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # B5.1 has not exposed document upload APIs, so there should be no production
    # document versions yet. Nullable-first keeps the migration safe if a dev DB
    # already contains experimental rows.
    op.add_column(
        "document_versions",
        sa.Column("created_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_versions_created_by_users",
        "document_versions",
        "users",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_document_versions_created_by",
        "document_versions",
        ["created_by"],
    )

    # Existing experimental rows cannot be attributed safely. Fail closed rather
    # than inventing an actor. A real pre-existing deployment should remediate
    # those rows explicitly before applying this migration.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM document_versions WHERE created_by IS NULL) THEN
                RAISE EXCEPTION 'B5.2 migration requires explicit created_by remediation for existing document_versions';
            END IF;
        END $$
        """
    )
    op.alter_column("document_versions", "created_by", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_document_versions_created_by", table_name="document_versions")
    op.drop_constraint(
        "fk_document_versions_created_by_users",
        "document_versions",
        type_="foreignkey",
    )
    op.drop_column("document_versions", "created_by")
