"""add missing document_type index

Revision ID: 20260910_0009
Revises: 20260910_0008
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260910_0009"
down_revision: str | Sequence[str] | None = "20260910_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_document_type",
        "documents",
        ["document_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_document_type", table_name="documents")
