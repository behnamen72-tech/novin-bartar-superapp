from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.access.models import OrganizationScopeMode, Permission, Role, RolePermission, UserRoleAssignment
from app.core.access.permissions import CORE_PERMISSION_DEFINITIONS
from app.core.identity.models import User
from app.core.organization.models import Organization
from app.db.session import SessionLocal
from app.modules.hr.permissions import HR_PERMISSION_DEFINITIONS
from app.modules.customers.permissions import CRM_PERMISSION_DEFINITIONS


SUPER_ADMIN_ROLE_CODE = "super_admin"


def main() -> None:
    login = input("Existing user email or username: ").strip().lower()
    organization_code = input("Root organization code for this admin scope: ").strip()

    with SessionLocal() as session:
        if "@" in login:
            user = session.scalar(select(User).where(User.email == login))
        else:
            user = session.scalar(select(User).where(User.username == login))
        if user is None:
            raise SystemExit("User not found.")

        organization = session.scalar(
            select(Organization).where(Organization.code == organization_code)
        )
        if organization is None:
            raise SystemExit("Organization not found.")

        permission_codes = [
            code
            for code, _, _ in (*CORE_PERMISSION_DEFINITIONS, *HR_PERMISSION_DEFINITIONS, *CRM_PERMISSION_DEFINITIONS)
        ]
        permissions = list(
            session.scalars(select(Permission).where(Permission.code.in_(permission_codes))).all()
        )
        if len(permissions) != len(permission_codes):
            raise SystemExit("Platform permissions are missing. Run Alembic migrations first.")

        role = session.scalar(
            select(Role)
            .where(Role.code == SUPER_ADMIN_ROLE_CODE)
            .options(selectinload(Role.permission_links))
        )
        if role is None:
            role = Role(
                code=SUPER_ADMIN_ROLE_CODE,
                name="Super Administrator",
                description="Full platform access within the assigned organization scope.",
                is_system=True,
            )
            session.add(role)
            session.flush()

        existing_permission_ids = {link.permission_id for link in role.permission_links}
        for permission in permissions:
            if permission.id not in existing_permission_ids:
                role.permission_links.append(
                    RolePermission(permission=permission)
                )

        existing_assignment = session.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.role_id == role.id,
                UserRoleAssignment.organization_id == organization.id,
                UserRoleAssignment.scope_mode == OrganizationScopeMode.SELF_AND_DESCENDANTS,
            )
        )
        if existing_assignment is None:
            session.add(
                UserRoleAssignment(
                    user=user,
                    role=role,
                    organization=organization,
                    scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
                )
            )

        session.commit()
        print(
            f"Granted {SUPER_ADMIN_ROLE_CODE} to {user.email} under "
            f"{organization.code} (self + descendants)."
        )


if __name__ == "__main__":
    main()
