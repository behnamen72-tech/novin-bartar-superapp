"""phase b2 authentication

Revision ID: 20260909_0002
Revises: 20260909_0001
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_0002"
down_revision: str | Sequence[str] | None = "20260909_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=512), nullable=True),
    )
    # Existing B1 users did not have credentials. Keep them unable to log in
    # until an administrator explicitly sets a real Argon2 password hash.
    op.execute(
        sa.text(
            "UPDATE users SET password_hash = '!legacy-account-disabled!' "
            "WHERE password_hash IS NULL"
        )
    )
    op.alter_column("users", "password_hash", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "password_hash")
