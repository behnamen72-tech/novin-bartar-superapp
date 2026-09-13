import os

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.access.permissions import CORE_PERMISSION_DEFINITIONS
from app.core.config import settings
from app.core.identity.models import User
from app.core.audit.models import AuditEvent
from app.core.audit.service import record_audit_event
from app.core.identity.security import hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.notifications.models import NotificationSeverity
from app.core.notifications.service import create_notification
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.session import SessionLocal
from app.modules.hr.permissions import HR_PERMISSION_DEFINITIONS
from app.modules.customers.permissions import CRM_PERMISSION_DEFINITIONS


DEMO_EMAIL = "demo@novinbartar.local"
DEMO_USERNAME = "demo-admin"
DEFAULT_DEMO_PASSWORD = "Demo-Only-ChangeMe-123!"
DEMO_ROLE_CODE = "demo_super_admin"
VIEWER_ROLE_CODE = "demo_viewer"


def get_or_create_person(
    session,
    *,
    email: str,
    first_name: str,
    last_name: str,
    organization: Organization,
    relationship_code: str,
    phone: str | None = None,
) -> Person:
    person = session.scalar(select(Person).where(Person.email == email))
    if person is None:
        person = Person(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
        )
        session.add(person)
        session.flush()

    relationship = session.scalar(
        select(PersonOrganizationRelationship).where(
            PersonOrganizationRelationship.person_id == person.id,
            PersonOrganizationRelationship.organization_id == organization.id,
            PersonOrganizationRelationship.relationship_code == relationship_code,
        )
    )
    if relationship is None:
        session.add(
            PersonOrganizationRelationship(
                person=person,
                organization=organization,
                relationship_code=relationship_code,
            )
        )

    return person


def main() -> None:
    if settings.app_env.lower() != "development":
        raise SystemExit("Demo seeding is allowed only when APP_ENV=development.")

    demo_password = os.getenv("DEMO_USER_PASSWORD", DEFAULT_DEMO_PASSWORD)

    with SessionLocal() as session:
        holding = session.scalar(
            select(Organization).where(Organization.code == "NOVIN-BARTAR")
        )
        if holding is None:
            holding = Organization(
                name="نوین برتر",
                code="NOVIN-BARTAR",
                organization_type=OrganizationType.HOLDING,
            )
            session.add(holding)
            session.flush()

        company = session.scalar(
            select(Organization).where(Organization.code == "ENFERADI-MARKET")
        )
        if company is None:
            company = Organization(
                name="انفرادی مارکت",
                code="ENFERADI-MARKET",
                organization_type=OrganizationType.COMPANY,
                parent=holding,
            )
            session.add(company)
            session.flush()

        branch = session.scalar(
            select(Organization).where(Organization.code == "ENFERADI-HQ")
        )
        if branch is None:
            branch = Organization(
                name="شعبه مرکزی انفرادی مارکت",
                code="ENFERADI-HQ",
                organization_type=OrganizationType.BRANCH,
                parent=company,
            )
            session.add(branch)
            session.flush()

        user = session.scalar(
            select(User)
            .where(User.email == DEMO_EMAIL)
            .options(selectinload(User.person))
        )
        if user is None:
            person = get_or_create_person(
                session,
                email=DEMO_EMAIL,
                first_name="مدیر",
                last_name="نمایشی",
                organization=company,
                relationship_code="manager",
            )
            user = User(
                person=person,
                email=DEMO_EMAIL,
                username=DEMO_USERNAME,
                password_hash=hash_password(demo_password),
            )
            session.add(user)
            session.flush()
        else:
            user.password_hash = hash_password(demo_password)
            user.is_active = True
            user.person.is_active = True

        # Extra demo people so Core pages are visually meaningful.
        get_or_create_person(
            session,
            email="sara.employee@demo.local",
            first_name="سارا",
            last_name="محمدی",
            organization=branch,
            relationship_code="employee",
            phone="09120000001",
        )
        get_or_create_person(
            session,
            email="ali.contractor@demo.local",
            first_name="علی",
            last_name="رضایی",
            organization=company,
            relationship_code="contractor",
            phone="09120000002",
        )
        get_or_create_person(
            session,
            email="mina.contact@demo.local",
            first_name="مینا",
            last_name="کریمی",
            organization=company,
            relationship_code="customer_contact",
            phone="09120000003",
        )

        viewer_person = get_or_create_person(
            session,
            email="viewer@novinbartar.local",
            first_name="کاربر",
            last_name="مشاهده‌گر",
            organization=branch,
            relationship_code="employee",
        )
        viewer = session.scalar(
            select(User).where(User.email == "viewer@novinbartar.local")
        )
        if viewer is None:
            viewer = User(
                person=viewer_person,
                email="viewer@novinbartar.local",
                username="demo-viewer",
                password_hash=hash_password("Viewer-Demo-Only-123!"),
            )
            session.add(viewer)
            session.flush()

        permission_codes = [
            code
            for code, _, _ in (*CORE_PERMISSION_DEFINITIONS, *HR_PERMISSION_DEFINITIONS, *CRM_PERMISSION_DEFINITIONS)
        ]
        permissions = list(
            session.scalars(
                select(Permission).where(Permission.code.in_(permission_codes))
            ).all()
        )
        if len(permissions) != len(permission_codes):
            raise SystemExit(
                "Platform permissions are missing. Run `alembic upgrade head` first."
            )

        role = session.scalar(
            select(Role)
            .where(Role.code == DEMO_ROLE_CODE)
            .options(selectinload(Role.permission_links))
        )
        if role is None:
            role = Role(
                code=DEMO_ROLE_CODE,
                name="Demo Super Administrator",
                description="Development-only demo administrator.",
                is_system=True,
            )
            session.add(role)
            session.flush()

        existing_permission_ids = {
            link.permission_id for link in role.permission_links
        }
        for permission in permissions:
            if permission.id not in existing_permission_ids:
                role.permission_links.append(RolePermission(permission=permission))

        assignment = session.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.role_id == role.id,
                UserRoleAssignment.organization_id == holding.id,
                UserRoleAssignment.scope_mode
                == OrganizationScopeMode.SELF_AND_DESCENDANTS,
            )
        )
        if assignment is None:
            session.add(
                UserRoleAssignment(
                    user=user,
                    role=role,
                    organization=holding,
                    scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
                )
            )
        else:
            assignment.is_active = True

        viewer_role = session.scalar(
            select(Role)
            .where(Role.code == VIEWER_ROLE_CODE)
            .options(selectinload(Role.permission_links))
        )
        if viewer_role is None:
            viewer_role = Role(
                code=VIEWER_ROLE_CODE,
                name="Demo Viewer",
                description="Development-only read-only role.",
                is_system=True,
            )
            session.add(viewer_role)
            session.flush()

        read_codes = {
            "organization.read",
            "people.read",
            "users.read",
            "access.read",
        }
        viewer_permission_ids = {
            link.permission_id for link in viewer_role.permission_links
        }
        for permission in permissions:
            if (
                permission.code in read_codes
                and permission.id not in viewer_permission_ids
            ):
                viewer_role.permission_links.append(
                    RolePermission(permission=permission)
                )

        viewer_assignment = session.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == viewer.id,
                UserRoleAssignment.role_id == viewer_role.id,
                UserRoleAssignment.organization_id == company.id,
                UserRoleAssignment.scope_mode
                == OrganizationScopeMode.SELF_AND_DESCENDANTS,
            )
        )
        if viewer_assignment is None:
            session.add(
                UserRoleAssignment(
                    user=viewer,
                    role=viewer_role,
                    organization=company,
                    scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
                )
            )

        create_notification(
            session,
            recipient_user_id=user.id,
            organization_id=holding.id,
            event_code="demo.welcome",
            source="demo_seed",
            severity=NotificationSeverity.SUCCESS,
            title="مرکز اعلان‌ها آماده است",
            body="از این بخش اعلان‌های گردش‌کار، اسناد و ماژول‌های عملیاتی را به‌صورت شخصی دریافت می‌کنید.",
            action_path="/?view=notifications",
            dedupe_key="demo-welcome-notifications-c2",
        )
        create_notification(
            session,
            recipient_user_id=user.id,
            organization_id=company.id,
            event_code="demo.workflow_hint",
            source="workflow",
            severity=NotificationSeverity.INFO,
            title="گردش‌کار C1 فعال است",
            body="برای مشاهده و اجرای گردش‌کارهای سازمانی وارد بخش گردش‌کار شوید.",
            action_path="/?view=workflow",
            dedupe_key="demo-workflow-hint-c2",
        )

        existing_demo_audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "demo.seed_initialized",
                AuditEvent.resource_type == "organization",
                AuditEvent.resource_id == str(holding.id),
            )
        )
        if existing_demo_audit is None:
            record_audit_event(
                session,
                actor=user,
                organization_id=holding.id,
                action="demo.seed_initialized",
                resource_type="organization",
                resource_id=holding.id,
                before_state=None,
                after_state={
                    "name": holding.name,
                    "code": holding.code,
                    "organization_type": holding.organization_type,
                },
                metadata={
                    "note": "Development-only demonstration audit event.",
                    "password": "must never appear in audit output",
                },
                source="demo_seed",
            )

        session.commit()

    print("Demo data is ready.")
    print(f"Login: {DEMO_EMAIL}")
    print(f"Password: {demo_password}")
    print("Demo UI data and C2 sample notifications were also seeded.")
    print("IMPORTANT: demo credentials are for local development only.")


if __name__ == "__main__":
    main()
