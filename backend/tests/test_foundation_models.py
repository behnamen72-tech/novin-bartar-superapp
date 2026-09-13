import pytest
from app.core.identity.models import User
from app.core.identity.security import hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def build_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_foundation_entities_can_be_persisted() -> None:
    # Import the real application entry point. This must be sufficient to
    # initialize DB persistence rules, including Organization hierarchy checks.
    import app.main  # noqa: F401

    engine = build_engine()

    with Session(engine) as session:
        holding = Organization(
            name="Novin Bartar",
            code="NOVIN",
            organization_type=OrganizationType.HOLDING,
        )
        company = Organization(
            name="Enferadi Market",
            code="ENFERADI",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        person = Person(
            first_name="Test",
            last_name="Person",
            email="person@example.com",
        )
        relationship = PersonOrganizationRelationship(
            person=person,
            organization=company,
            relationship_code="employee",
        )
        user = User(
            person=person,
            email="user@example.com",
            username="testuser",
            password_hash=hash_password("A-secure-test-password-123!"),
        )

        session.add_all([holding, company, person, relationship, user])
        session.commit()

        persisted_user = session.scalar(select(User).where(User.email == "user@example.com"))
        assert persisted_user is not None
        assert persisted_user.person.first_name == "Test"
        assert persisted_user.person.organization_relationships[0].organization.code == "ENFERADI"


def test_invalid_hierarchy_is_blocked_during_real_app_persist() -> None:
    import app.main  # noqa: F401

    engine = build_engine()

    with Session(engine) as session:
        invalid_parent = Organization(
            name="Invalid Branch Parent",
            code="BRANCH-PARENT",
            organization_type=OrganizationType.BRANCH,
        )
        invalid_company = Organization(
            name="Invalid Company",
            code="INVALID-COMPANY",
            organization_type=OrganizationType.COMPANY,
            parent=invalid_parent,
        )
        session.add_all([invalid_parent, invalid_company])

        with pytest.raises(ValueError, match="Invalid organization hierarchy"):
            session.flush()


def test_holding_with_parent_is_blocked_during_real_app_persist() -> None:
    import app.main  # noqa: F401

    engine = build_engine()

    with Session(engine) as session:
        company = Organization(
            name="Company",
            code="COMPANY",
            organization_type=OrganizationType.COMPANY,
        )
        holding = Organization(
            name="Holding",
            code="HOLDING",
            organization_type=OrganizationType.HOLDING,
            parent=company,
        )
        session.add_all([company, holding])

        with pytest.raises(ValueError, match="Invalid organization hierarchy"):
            session.flush()


def test_cors_format_is_comma_separated() -> None:
    from app.core.config import Settings

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        cors_allowed_origins="http://localhost:3000,https://admin.example.com",
        jwt_secret_key="test-only-secret-key-which-is-at-least-32-characters-long",
    )

    assert settings.cors_allowed_origin_list == [
        "http://localhost:3000",
        "https://admin.example.com",
    ]
