import type {
  AccessAssignment,
  OrganizationItem,
  PersonItem,
  UserItem,
} from "@/lib/core-types";
import { assignmentCoversOrganization } from "@/lib/organization-management";

export function canManageOrganizationForPermission(
  organizationId: string,
  permission: "people.manage" | "users.manage" | "access.manage",
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): boolean {
  return assignments.some(
    (assignment) =>
      assignment.permissions.includes(permission) &&
      assignmentCoversOrganization(assignment, organizationId, organizations),
  );
}

export function manageableOrganizationsForPermission(
  permission: "people.manage" | "users.manage" | "access.manage",
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): OrganizationItem[] {
  return organizations.filter(
    (organization) =>
      organization.is_active &&
      canManageOrganizationForPermission(
        organization.id,
        permission,
        organizations,
        assignments,
      ),
  );
}

function mutationRelationshipOrganizationIds(
  person: PersonItem,
  organizations: readonly OrganizationItem[],
): string[] {
  const activeOrganizationIds = new Set(
    person.relationships
      .filter((relationship) => relationship.is_active)
      .map((relationship) => relationship.organization_id)
      .filter((organizationId) => {
        const organization = organizations.find((item) => item.id === organizationId);
        return organization?.is_active !== false;
      }),
  );

  if (activeOrganizationIds.size > 0) {
    return [...activeOrganizationIds];
  }

  return [
    ...new Set(
      person.relationships
        .map((relationship) => relationship.organization_id)
        .filter((organizationId) => {
          const organization = organizations.find((item) => item.id === organizationId);
          return organization?.is_active !== false;
        }),
    ),
  ];
}

export function canManagePersonGlobally(
  person: PersonItem,
  permission: "people.manage" | "users.manage" | "access.manage",
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): boolean {
  const organizationIds = mutationRelationshipOrganizationIds(person, organizations);
  return (
    organizationIds.length > 0 &&
    organizationIds.every((organizationId) =>
      canManageOrganizationForPermission(
        organizationId,
        permission,
        organizations,
        assignments,
      ),
    )
  );
}

export function eligiblePeopleForUserCreation(
  people: readonly PersonItem[],
  users: readonly UserItem[],
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): PersonItem[] {
  const existingPersonIds = new Set(users.map((user) => user.person_id));
  return people.filter(
    (person) =>
      person.is_active &&
      !existingPersonIds.has(person.id) &&
      canManagePersonGlobally(person, "users.manage", organizations, assignments),
  );
}

export function normalizedOptionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

export function normalizedUsername(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return normalized.length > 0 ? normalized : null;
}
