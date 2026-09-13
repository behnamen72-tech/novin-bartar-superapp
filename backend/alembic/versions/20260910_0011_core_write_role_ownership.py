"""B5.6 core write APIs: organization-owned custom roles

Revision ID: 20260910_0011
Revises: 20260910_0010
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0011"
down_revision: str | Sequence[str] | None = "20260910_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_roles_organization_id_organizations",
        "roles",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_roles_organization_id",
        "roles",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_constraint(
        "fk_roles_organization_id_organizations",
        "roles",
        type_="foreignkey",
    )
    op.drop_column("roles", "organization_id")
