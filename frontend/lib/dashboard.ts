import type {
  AccessAssignment,
  AuditEventItem,
  DocumentExpirationItem,
  OrganizationItem,
  PersonItem,
  UserItem,
} from "@/lib/core-types";
import { hasAnyPermission } from "@/lib/permissions";

export type DashboardCapabilities = {
  organizations: boolean;
  people: boolean;
  users: boolean;
  documents: boolean;
  audit: boolean;
};

export type DashboardSnapshot = {
  organizations: OrganizationItem[];
  people: PersonItem[];
  users: UserItem[];
  expiringDocuments: DocumentExpirationItem[];
  recentAudit: AuditEventItem[];
};

export type DashboardSummary = {
  organizationCount: number;
  activeOrganizationCount: number;
  peopleCount: number;
  activePeopleCount: number;
  userCount: number;
  activeUserCount: number;
  expiringDocumentCount: number;
  expiredDocumentCount: number;
  assignmentCount: number;
  roleCount: number;
};

export function getDashboardCapabilities(
  permissions: readonly string[],
): DashboardCapabilities {
  return {
    organizations: hasAnyPermission(permissions, ["organization.read"]),
    people: hasAnyPermission(permissions, ["people.read"]),
    users: hasAnyPermission(permissions, ["users.read"]),
    documents: hasAnyPermission(permissions, ["documents.read"]),
    audit: hasAnyPermission(permissions, ["audit.read"]),
  };
}

export function summarizeDashboard(
  snapshot: DashboardSnapshot,
  assignments: readonly AccessAssignment[],
): DashboardSummary {
  return {
    organizationCount: snapshot.organizations.length,
    activeOrganizationCount: snapshot.organizations.filter((item) => item.is_active)
      .length,
    peopleCount: snapshot.people.length,
    activePeopleCount: snapshot.people.filter((item) => item.is_active).length,
    userCount: snapshot.users.length,
    activeUserCount: snapshot.users.filter((item) => item.is_active).length,
    expiringDocumentCount: snapshot.expiringDocuments.filter(
      (item) => item.expiration_state === "expiring_soon",
    ).length,
    expiredDocumentCount: snapshot.expiringDocuments.filter(
      (item) => item.expiration_state === "expired",
    ).length,
    assignmentCount: assignments.length,
    roleCount: new Set(assignments.map((item) => item.role_code)).size,
  };
}
