"""phase b5.4 document-level access control

Revision ID: 20260910_0008
Revises: 20260909_0007
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260910_0008"
down_revision: str | Sequence[str] | None = "20260909_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # DocumentPermission existed as an *unenforced* B5.1 foundation. Silently
    # activating historical/manual rows could unexpectedly hide documents, so
    # fail closed and require explicit remediation if any pre-B5.4 rows exist.
    # The project production database is PostgreSQL; keeping this as a database
    # guard also makes the migration safe against out-of-band manual inserts.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM document_permissions LIMIT 1) THEN
                RAISE EXCEPTION
                    'B5.4 activates document_permissions; review and remediate existing rows before migration';
            END IF;
        END $$;
        """
    )

    # Once semantics are active, make duplicate logical grants impossible and
    # add the lookup indexes used by the ACL gate.
    op.create_unique_constraint(
        "uq_document_permission_role_type",
        "document_permissions",
        ["document_id", "role_id", "permission_type"],
    )
    op.create_index(
        "ix_document_permissions_document_active_type",
        "document_permissions",
        ["document_id", "is_active", "permission_type"],
    )
    op.create_index(
        "ix_document_permissions_role_active",
        "document_permissions",
        ["role_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_permissions_role_active",
        table_name="document_permissions",
    )
    op.drop_index(
        "ix_document_permissions_document_active_type",
        table_name="document_permissions",
    )
    op.drop_constraint(
        "uq_document_permission_role_type",
        "document_permissions",
        type_="unique",
    )
