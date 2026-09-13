from app.core.organization.models import OrganizationType

_ALLOWED_PARENTS: dict[OrganizationType, set[OrganizationType | None]] = {
    OrganizationType.HOLDING: {None},
    OrganizationType.COMPANY: {OrganizationType.HOLDING},
    OrganizationType.BRANCH: {OrganizationType.COMPANY},
    OrganizationType.UNIT: {OrganizationType.COMPANY, OrganizationType.BRANCH},
}


def validate_parent_type(
    child_type: OrganizationType,
    parent_type: OrganizationType | None,
) -> None:
    allowed = _ALLOWED_PARENTS[child_type]
    if parent_type not in allowed:
        allowed_names = ", ".join(
            "none" if value is None else value.value
            for value in sorted(allowed, key=lambda item: "" if item is None else item.value)
        )
        actual = "none" if parent_type is None else parent_type.value
        raise ValueError(
            f"Invalid organization hierarchy: {child_type.value} cannot have "
            f"parent type {actual}. Allowed: {allowed_names}."
        )
