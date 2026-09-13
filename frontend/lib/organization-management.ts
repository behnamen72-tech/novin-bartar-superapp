import type {
  AccessAssignment,
  OrganizationItem,
  OrganizationType,
} from "@/lib/core-types";

const childTypesByParent: Record<OrganizationType, readonly OrganizationType[]> = {
  holding: ["company"],
  company: ["branch", "unit"],
  branch: ["unit"],
  unit: [],
};

export function allowedChildTypes(parentType: OrganizationType): readonly OrganizationType[] {
  return childTypesByParent[parentType];
}

function organizationMap(organizations: readonly OrganizationItem[]) {
  return new Map(organizations.map((organization) => [organization.id, organization]));
}

export function assignmentCoversOrganization(
  assignment: AccessAssignment,
  targetOrganizationId: string,
  organizations: readonly OrganizationItem[],
): boolean {
  if (assignment.organization_id === targetOrganizationId) return true;
  if (assignment.scope_mode !== "self_and_descendants") return false;

  const byId = organizationMap(organizations);
  const target = byId.get(targetOrganizationId);
  if (!target) return false;

  const visited = new Set<string>();
  let current = target;

  while (current.parent_id) {
    if (visited.has(current.id)) return false;
    visited.add(current.id);

    const parent = byId.get(current.parent_id);
    if (!parent || !parent.is_active) return false;
    if (parent.id === assignment.organization_id) return true;
    current = parent;
  }

  return false;
}

export function canManageOrganization(
  organizationId: string,
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): boolean {
  return assignments.some(
    (assignment) =>
      assignment.permissions.includes("organization.manage") &&
      assignmentCoversOrganization(assignment, organizationId, organizations),
  );
}

export function canCreateChildUnder(
  parentId: string,
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): boolean {
  const parent = organizations.find((organization) => organization.id === parentId);
  if (!parent || !parent.is_active || allowedChildTypes(parent.organization_type).length === 0) {
    return false;
  }

  return assignments.some(
    (assignment) =>
      assignment.permissions.includes("organization.manage") &&
      assignment.scope_mode === "self_and_descendants" &&
      assignmentCoversOrganization(assignment, parentId, organizations),
  );
}

export function manageableCreateParents(
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): OrganizationItem[] {
  return organizations.filter((organization) =>
    canCreateChildUnder(organization.id, organizations, assignments),
  );
}

export function hasActiveChildren(
  organizationId: string,
  organizations: readonly OrganizationItem[],
): boolean {
  return organizations.some(
    (organization) =>
      organization.parent_id === organizationId && organization.is_active,
  );
}

export function canActivateOrganization(
  organization: OrganizationItem,
  organizations: readonly OrganizationItem[],
): boolean {
  if (organization.is_active) return false;
  if (!organization.parent_id) return true;
  const parent = organizations.find((item) => item.id === organization.parent_id);
  return Boolean(parent?.is_active);
}

export function normalizedOrganizationCode(value: string): string {
  return value.trim().toUpperCase();
}
