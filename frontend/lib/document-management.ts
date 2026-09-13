import type {
  AccessAssignment,
  DocumentItem,
  DocumentPriority,
  DocumentStatus,
  OrganizationItem,
} from "@/lib/core-types";
import { assignmentCoversOrganization } from "@/lib/organization-management";

export const documentStatusLabels: Record<DocumentStatus, string> = {
  active: "فعال",
  archived: "بایگانی‌شده",
  disabled: "غیرفعال",
};

export const documentPriorityLabels: Record<DocumentPriority, string> = {
  low: "کم",
  normal: "عادی",
  high: "بالا",
  critical: "بحرانی",
};

export function canManageDocumentsForOrganization(
  organizationId: string,
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): boolean {
  return assignments.some(
    (assignment) =>
      assignment.permissions.includes("documents.manage") &&
      assignmentCoversOrganization(assignment, organizationId, organizations),
  );
}

export function manageableDocumentOrganizations(
  organizations: readonly OrganizationItem[],
  assignments: readonly AccessAssignment[],
): OrganizationItem[] {
  return organizations.filter(
    (organization) =>
      organization.is_active &&
      canManageDocumentsForOrganization(organization.id, organizations, assignments),
  );
}

export function formatDocumentDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("fa-IR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes.toLocaleString("fa-IR")} بایت`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function documentNeedsAttention(document: DocumentItem): boolean {
  if (!document.expires_at) return false;
  return new Date(document.expires_at).getTime() <= Date.now() + 30 * 24 * 60 * 60 * 1000;
}
