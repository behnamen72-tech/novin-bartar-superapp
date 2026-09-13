"""D1 HR foundation

Revision ID: 20260911_0015
Revises: 20260911_0014
Create Date: 2026-09-11
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_0015"
down_revision: str | Sequence[str] | None = "20260911_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

hr_job_profile_scope_mode = sa.Enum(
    "SELF",
    "SELF_AND_DESCENDANTS",
    name="hr_job_profile_scope_mode",
)
hr_employment_type = sa.Enum(
    "PERMANENT",
    "FIXED_TERM",
    "PART_TIME",
    "CONTRACTOR",
    "INTERN",
    "OTHER",
    name="hr_employment_type",
)

HR_PERMISSIONS = (
    (
        "hr.read",
        "Read HR foundation",
        "View HR job profiles, planned positions, and employment records within authorized organization scope.",
    ),
    (
        "hr.manage",
        "Manage HR foundation",
        "Create and manage HR job profiles, positions, and employment records within authorized organization scope.",
    ),
)


def upgrade() -> None:
    op.create_table(
        "hr_job_profiles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("scope_mode", hr_job_profile_scope_mode, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_hr_job_profile_org_code"),
    )
    op.create_index("ix_hr_job_profiles_organization_id", "hr_job_profiles", ["organization_id"])
    op.create_index("ix_hr_job_profiles_org_active", "hr_job_profiles", ["organization_id", "is_active"])

    op.create_table(
        "hr_positions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_profile_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=True),
        sa.Column("reports_to_position_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "reports_to_position_id IS NULL OR reports_to_position_id <> id",
            name="ck_hr_position_reports_to_not_self",
        ),
        sa.ForeignKeyConstraint(["job_profile_id"], ["hr_job_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reports_to_position_id"], ["hr_positions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_hr_position_org_code"),
    )
    op.create_index("ix_hr_positions_organization_id", "hr_positions", ["organization_id"])
    op.create_index("ix_hr_positions_job_profile_id", "hr_positions", ["job_profile_id"])
    op.create_index("ix_hr_positions_reports_to_position_id", "hr_positions", ["reports_to_position_id"])
    op.create_index("ix_hr_positions_org_active", "hr_positions", ["organization_id", "is_active"])

    op.create_table(
        "hr_employments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("employment_number", sa.String(length=80), nullable=True),
        sa.Column("employment_type", hr_employment_type, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_hr_employment_date_range"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["position_id"], ["hr_positions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "employment_number", name="uq_hr_employment_org_number"),
    )
    op.create_index("ix_hr_employments_organization_id", "hr_employments", ["organization_id"])
    op.create_index("ix_hr_employments_person_id", "hr_employments", ["person_id"])
    op.create_index("ix_hr_employments_position_id", "hr_employments", ["position_id"])
    op.create_index("ix_hr_employments_employment_type", "hr_employments", ["employment_type"])
    op.create_index("ix_hr_employments_org_active", "hr_employments", ["organization_id", "is_active"])
    op.create_index(
        "ix_hr_employments_person_org_active",
        "hr_employments",
        ["person_id", "organization_id", "is_active"],
    )

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
            for code, name, description in HR_PERMISSIONS
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('hr.read', 'hr.manage')")

    op.drop_index("ix_hr_employments_person_org_active", table_name="hr_employments")
    op.drop_index("ix_hr_employments_org_active", table_name="hr_employments")
    op.drop_index("ix_hr_employments_employment_type", table_name="hr_employments")
    op.drop_index("ix_hr_employments_position_id", table_name="hr_employments")
    op.drop_index("ix_hr_employments_person_id", table_name="hr_employments")
    op.drop_index("ix_hr_employments_organization_id", table_name="hr_employments")
    op.drop_table("hr_employments")

    op.drop_index("ix_hr_positions_org_active", table_name="hr_positions")
    op.drop_index("ix_hr_positions_reports_to_position_id", table_name="hr_positions")
    op.drop_index("ix_hr_positions_job_profile_id", table_name="hr_positions")
    op.drop_index("ix_hr_positions_organization_id", table_name="hr_positions")
    op.drop_table("hr_positions")

    op.drop_index("ix_hr_job_profiles_org_active", table_name="hr_job_profiles")
    op.drop_index("ix_hr_job_profiles_organization_id", table_name="hr_job_profiles")
    op.drop_table("hr_job_profiles")

    hr_employment_type.drop(op.get_bind(), checkfirst=True)
    hr_job_profile_scope_mode.drop(op.get_bind(), checkfirst=True)
