"""phase b5.3 document linking and lifecycle

Revision ID: 20260909_0007
Revises: 20260909_0006
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_0007"
down_revision: str | Sequence[str] | None = "20260909_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # B5.1 created DocumentLink as a foundation but exposed no link API. B5.3
    # turns unlinking into a non-destructive lifecycle operation.
    op.add_column(
        "document_links",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("document_links", "is_active", server_default=None)

    # A document can have at most one durable row for a target. Re-linking a
    # previously unlinked target reactivates that same row instead of erasing history.
    op.create_unique_constraint(
        "uq_document_link_target",
        "document_links",
        ["document_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_document_links_entity_active",
        "document_links",
        ["entity_type", "entity_id", "is_active"],
    )
    op.create_index(
        "ix_document_links_document_active",
        "document_links",
        ["document_id", "is_active"],
    )
    op.create_index(
        "ix_documents_organization_status",
        "documents",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_organization_status", table_name="documents")
    op.drop_index("ix_document_links_document_active", table_name="document_links")
    op.drop_index("ix_document_links_entity_active", table_name="document_links")
    op.drop_constraint(
        "uq_document_link_target",
        "document_links",
        type_="unique",
    )
    op.drop_column("document_links", "is_active")
