"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiDownload, apiFetch } from "@/lib/api-client";
import {
  canManageDocumentsForOrganization,
  documentPriorityLabels,
  documentStatusLabels,
  formatDocumentDate,
  formatFileSize,
} from "@/lib/document-management";
import type {
  AccessAssignment,
  DocumentCategoryItem,
  DocumentDetailItem,
  DocumentItem,
  DocumentLinkEntityType,
  DocumentLinkItem,
  DocumentPermissionItem,
  DocumentPermissionType,
  DocumentPriority,
  DocumentStatus,
  DocumentTimelineEventItem,
  DocumentVersionItem,
  OrganizationItem,
  PersonItem,
  RetentionBasis,
  RetentionPolicyItem,
  RoleAdminItem,
} from "@/lib/core-types";
import { assignmentCoversOrganization } from "@/lib/organization-management";

const ALLOWED_UPLOADS = ".pdf,.docx,.xlsx,.png,.jpg,.jpeg";

type Notice = { tone: "error" | "success"; text: string } | null;
type DetailTab = "metadata" | "versions" | "links" | "permissions" | "timeline";
type EditorMode = "create" | "edit";
type ConfigMode = "categories" | "retention";

type DocumentManagementViewProps = {
  organizations: OrganizationItem[];
  people: PersonItem[];
  assignments: AccessAssignment[];
  allPermissions: string[];
};

function mutationMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  }
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Document not found.": "سند پیدا نشد یا دیگر در محدوده دسترسی شما نیست.",
    "Only active documents can be archived.": "فقط سند فعال قابل بایگانی است.",
    "Only archived documents can be restored.": "فقط سند بایگانی‌شده قابل بازیابی است.",
    "Archived documents cannot be modified.": "سند بایگانی‌شده قابل ویرایش نیست.",
    "Document has no versions.": "برای این سند هنوز فایلی بارگذاری نشده است.",
    "A category with this code already exists in the organization.": "این کد دسته‌بندی قبلاً در سازمان استفاده شده است.",
    "A retention policy with this code already exists in the organization.": "این کد سیاست نگهداری قبلاً در سازمان استفاده شده است.",
    "Role is not available for this document permission.": "Role انتخاب‌شده برای این نوع دسترسی سند در دسترس نیست.",
    "Document permission is already active for this role.": "این دسترسی برای Role انتخاب‌شده از قبل فعال است.",
    "The first document permission must be a manage permission.": "برای فعال‌کردن حالت محدود، اولین دسترسی سند باید از نوع مدیریت باشد.",
    "The first manage permission must keep the current manager in control.": "اولین دسترسی مدیریت باید کنترل مدیر فعلی را حفظ کند.",
    "A restricted document must keep at least one active manage permission.": "سند محدودشده باید حداقل یک دسترسی مدیریت فعال داشته باشد.",
  };
  if (known[error.detail]) return known[error.detail];
  if (error.status === 403) return "برای این عملیات مجوز کافی ندارید.";
  if (error.status === 404) return "اطلاعات موردنظر پیدا نشد یا قابل مشاهده نیست.";
  if (error.status === 409) return "این عملیات با وضعیت فعلی سند سازگار نیست.";
  if (error.status === 400 || error.status === 422) return "اطلاعات واردشده معتبر نیست.";
  return error.detail || "عملیات انجام نشد.";
}

function organizationName(id: string, organizations: readonly OrganizationItem[], assignments: readonly AccessAssignment[]) {
  return organizations.find((item) => item.id === id)?.name
    ?? assignments.find((item) => item.organization_id === id)?.organization_name
    ?? `سازمان ${id.slice(0, 8)}`;
}

function toLocalDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName || "document";
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function DocumentManagementView({
  organizations,
  people,
  assignments,
  allPermissions,
}: DocumentManagementViewProps) {
  const canManageAny = allPermissions.includes("documents.manage");
  const canReadAccess = allPermissions.includes("access.read");
  const canReadPeople = allPermissions.includes("people.read") || allPermissions.includes("people.manage");

  const organizationOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const organization of organizations) map.set(organization.id, organization.name);
    for (const assignment of assignments) map.set(assignment.organization_id, assignment.organization_name);
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [assignments, organizations]);

  const manageableOrganizationOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const organization of organizations) {
      if (organization.is_active && canManageDocumentsForOrganization(organization.id, organizations, assignments)) {
        map.set(organization.id, organization.name);
      }
    }
    for (const assignment of assignments) {
      if (assignment.permissions.includes("documents.manage")) {
        map.set(assignment.organization_id, assignment.organization_name);
      }
    }
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [assignments, organizations]);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [categories, setCategories] = useState<DocumentCategoryItem[]>([]);
  const [retentionPolicies, setRetentionPolicies] = useState<RetentionPolicyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);
  const [query, setQuery] = useState("");
  const [organizationFilter, setOrganizationFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | "">("");
  const [priorityFilter, setPriorityFilter] = useState<DocumentPriority | "">("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetailItem | null>(null);
  const [timeline, setTimeline] = useState<DocumentTimelineEventItem[]>([]);
  const [documentPermissions, setDocumentPermissions] = useState<DocumentPermissionItem[]>([]);
  const [aclRoles, setAclRoles] = useState<RoleAdminItem[]>([]);
  const [aclLoaded, setAclLoaded] = useState(false);
  const [aclRoleId, setAclRoleId] = useState("");
  const [aclPermissionType, setAclPermissionType] = useState<DocumentPermissionType>("manage");
  const [detailTab, setDetailTab] = useState<DetailTab>("metadata");
  const [detailLoading, setDetailLoading] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [editorMode, setEditorMode] = useState<EditorMode | null>(null);
  const [configMode, setConfigMode] = useState<ConfigMode | null>(null);
  const [configEditingId, setConfigEditingId] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<DocumentPriority>("normal");
  const [categoryId, setCategoryId] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [retentionPolicyId, setRetentionPolicyId] = useState("");

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [linkType, setLinkType] = useState<DocumentLinkEntityType>("person");
  const [linkEntityId, setLinkEntityId] = useState("");

  const [configOrgId, setConfigOrgId] = useState("");
  const [configCode, setConfigCode] = useState("");
  const [configName, setConfigName] = useState("");
  const [configDescription, setConfigDescription] = useState("");
  const [categoryParentId, setCategoryParentId] = useState("");
  const [retentionDays, setRetentionDays] = useState("365");
  const [retentionBasis, setRetentionBasis] = useState<RetentionBasis>("created_at");

  const canAdminDocumentAcl = useCallback((targetOrganizationId: string) => (
    canManageDocumentsForOrganization(targetOrganizationId, organizations, assignments)
    || assignments.some((assignment) =>
      assignment.permissions.includes("access.manage")
      && assignmentCoversOrganization(assignment, targetOrganizationId, organizations),
    )
  ), [assignments, organizations]);

  const eligibleAclRoles = useMemo(() => {
    const requiredPermission = aclPermissionType === "manage" ? "documents.manage" : "documents.read";
    return aclRoles.filter((role) => role.is_active && role.permissions.includes(requiredPermission));
  }, [aclPermissionType, aclRoles]);

  const loadSupportingData = useCallback(async () => {
    try {
      const [nextCategories, nextPolicies] = await Promise.all([
        apiFetch<DocumentCategoryItem[]>("/api/core/document-categories?include_inactive=true"),
        apiFetch<RetentionPolicyItem[]>("/api/core/document-retention-policies?include_inactive=true"),
      ]);
      setCategories(nextCategories);
      setRetentionPolicies(nextPolicies);
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 403)) {
        setNotice({ tone: "error", text: "دسته‌بندی‌ها یا سیاست‌های نگهداری به‌روزرسانی نشدند." });
      }
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    const params = new URLSearchParams({ limit: "200", offset: "0" });
    if (query.trim()) params.set("q", query.trim());
    if (organizationFilter) params.set("organization_id", organizationFilter);
    if (statusFilter) params.set("status", statusFilter);
    if (priorityFilter) params.set("priority", priorityFilter);

    try {
      setDocuments(await apiFetch<DocumentItem[]>(`/api/core/documents?${params.toString()}`));
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [organizationFilter, priorityFilter, query, statusFilter]);

  useEffect(() => {
    void Promise.all([loadDocuments(), loadSupportingData()]);
  }, [loadDocuments, loadSupportingData]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key !== "Escape" || busyAction) return;
      if (editorMode) setEditorMode(null);
      else if (configMode) setConfigMode(null);
      else if (selectedId) closeDetail();
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  });

  const categoryMap = useMemo(() => new Map(categories.map((item) => [item.id, item])), [categories]);
  const policyMap = useMemo(() => new Map(retentionPolicies.map((item) => [item.id, item])), [retentionPolicies]);

  const selectedCategories = useMemo(
    () => categories.filter((item) => item.organization_id === (detail?.organization_id ?? organizationId) && item.is_active),
    [categories, detail?.organization_id, organizationId],
  );
  const selectedPolicies = useMemo(
    () => retentionPolicies.filter((item) => item.organization_id === (detail?.organization_id ?? organizationId) && item.is_active),
    [retentionPolicies, detail?.organization_id, organizationId],
  );

  async function openDetail(documentId: string) {
    setSelectedId(documentId);
    setDetailLoading(true);
    setDetailTab("metadata");
    setTimeline([]);
    setDocumentPermissions([]);
    setAclRoles([]);
    setAclLoaded(false);
    setAclRoleId("");
    setAclPermissionType("manage");
    setNotice(null);
    try {
      const next = await apiFetch<DocumentDetailItem>(`/api/core/documents/${encodeURIComponent(documentId)}`);
      setDetail(next);
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
      setSelectedId(null);
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  function closeDetail() {
    setSelectedId(null);
    setDetail(null);
    setTimeline([]);
    setDocumentPermissions([]);
    setAclRoles([]);
    setAclLoaded(false);
    setAclRoleId("");
    setUploadFile(null);
    setLinkEntityId("");
  }

  async function reloadDetail(documentId = selectedId) {
    if (!documentId) return;
    const next = await apiFetch<DocumentDetailItem>(`/api/core/documents/${encodeURIComponent(documentId)}`);
    setDetail(next);
    setDocuments((current) => current.map((item) => item.id === next.id ? next : item));
    setTimeline([]);
  }

  async function loadDocumentAcl(documentId: string) {
    const nextPermissions = await apiFetch<DocumentPermissionItem[]>(
      `/api/core/documents/${encodeURIComponent(documentId)}/permissions`,
    );
    setDocumentPermissions(nextPermissions);
    setAclPermissionType(nextPermissions.length === 0 ? "manage" : "read");
    setAclRoleId("");

    if (canReadAccess) {
      try {
        setAclRoles(await apiFetch<RoleAdminItem[]>("/api/core/access/roles"));
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 403)) throw error;
        setAclRoles([]);
      }
    } else {
      setAclRoles([]);
    }
    setAclLoaded(true);
  }

  async function openPermissions() {
    if (!detail || !canAdminDocumentAcl(detail.organization_id)) return;
    setDetailTab("permissions");
    if (aclLoaded) return;
    setDetailLoading(true);
    try {
      await loadDocumentAcl(detail.id);
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setDetailLoading(false);
    }
  }

  async function grantDocumentAcl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !aclRoleId || !canAdminDocumentAcl(detail.organization_id)) return;
    setBusyAction("acl-grant");
    setNotice(null);
    try {
      await apiFetch<DocumentPermissionItem>(
        `/api/core/documents/${encodeURIComponent(detail.id)}/permissions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role_id: aclRoleId, permission_type: aclPermissionType }),
        },
      );
      await loadDocumentAcl(detail.id);
      setTimeline([]);
      setNotice({ tone: "success", text: "دسترسی محدودکننده سند برای Role ثبت شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function revokeDocumentAcl(permissionId: string) {
    if (!detail || !canAdminDocumentAcl(detail.organization_id) || !window.confirm("این دسترسی Role از سند برداشته شود؟")) return;
    setBusyAction(`acl-revoke-${permissionId}`);
    setNotice(null);
    try {
      await apiFetch<void>(
        `/api/core/documents/${encodeURIComponent(detail.id)}/permissions/${encodeURIComponent(permissionId)}`,
        { method: "DELETE" },
      );
      await loadDocumentAcl(detail.id);
      setTimeline([]);
      setNotice({ tone: "success", text: "دسترسی سند لغو شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function openTimeline() {
    if (!selectedId) return;
    setDetailTab("timeline");
    if (timeline.length > 0) return;
    setDetailLoading(true);
    try {
      setTimeline(await apiFetch<DocumentTimelineEventItem[]>(
        `/api/core/documents/${encodeURIComponent(selectedId)}/timeline?limit=100&offset=0`,
      ));
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setDetailLoading(false);
    }
  }

  function resetEditor(document?: DocumentDetailItem) {
    setTitle(document?.title ?? "");
    setDocumentType(document?.document_type ?? "");
    setOrganizationId(document?.organization_id ?? manageableOrganizationOptions[0]?.id ?? "");
    setDescription(document?.description ?? "");
    setPriority(document?.priority ?? "normal");
    setCategoryId(document?.category_id ?? "");
    setExpiresAt(toLocalDateTime(document?.expires_at ?? null));
    setRetentionPolicyId(document?.retention_policy_id ?? "");
  }

  function openCreate() {
    resetEditor();
    setEditorMode("create");
    setNotice(null);
  }

  function openEdit() {
    if (!detail || detail.status !== "active") return;
    resetEditor(detail);
    setEditorMode("edit");
    setNotice(null);
  }

  async function saveDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("save-document");
    setNotice(null);
    try {
      if (editorMode === "create") {
        const created = await apiFetch<DocumentItem>("/api/core/documents", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: title.trim(),
            document_type: documentType.trim(),
            organization_id: organizationId,
          }),
        });
        setDocuments((current) => [created, ...current]);
        setEditorMode(null);
        await openDetail(created.id);
        setNotice({ tone: "success", text: "سند ایجاد شد. اکنون می‌توانید فایل و اطلاعات تکمیلی را اضافه کنید." });
      } else if (editorMode === "edit" && detail) {
        const updated = await apiFetch<DocumentItem>(
          `/api/core/documents/${encodeURIComponent(detail.id)}/metadata`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              title: title.trim(),
              document_type: documentType.trim(),
              description: description.trim() || null,
              priority,
              category_id: categoryId || null,
              expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
              retention_policy_id: retentionPolicyId || null,
            }),
          },
        );
        setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
        setEditorMode(null);
        await reloadDetail(updated.id);
        setNotice({ tone: "success", text: "اطلاعات سند به‌روزرسانی شد." });
      }
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function toggleArchive() {
    if (!detail) return;
    const restoring = detail.status === "archived";
    const action = restoring ? "restore" : "archive";
    if (!window.confirm(restoring ? "این سند از بایگانی خارج شود؟" : "این سند بایگانی شود؟")) return;
    setBusyAction(action);
    setNotice(null);
    try {
      const updated = await apiFetch<DocumentItem>(
        `/api/core/documents/${encodeURIComponent(detail.id)}/${action}`,
        { method: "POST" },
      );
      setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
      await reloadDetail(updated.id);
      setNotice({ tone: "success", text: restoring ? "سند بازیابی شد." : "سند بایگانی شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function uploadVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !uploadFile) return;
    setBusyAction("upload");
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      await apiFetch<DocumentVersionItem>(
        `/api/core/documents/${encodeURIComponent(detail.id)}/versions`,
        { method: "POST", body: form },
      );
      setUploadFile(null);
      await reloadDetail(detail.id);
      setDetailTab("versions");
      setNotice({ tone: "success", text: "نسخه جدید فایل با موفقیت ثبت شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function downloadLatest() {
    if (!detail) return;
    setBusyAction("download");
    setNotice(null);
    try {
      const result = await apiDownload(`/api/core/documents/${encodeURIComponent(detail.id)}/download`);
      downloadBlob(result.blob, result.fileName);
      setTimeline([]);
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function addLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !linkEntityId) return;
    setBusyAction("link");
    setNotice(null);
    try {
      await apiFetch<DocumentLinkItem>(`/api/core/documents/${encodeURIComponent(detail.id)}/links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entity_type: linkType, entity_id: linkEntityId }),
      });
      setLinkEntityId("");
      await reloadDetail(detail.id);
      setNotice({ tone: "success", text: "پیوند سند ثبت شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function removeLink(linkId: string) {
    if (!detail || !window.confirm("این پیوند از سند حذف شود؟")) return;
    setBusyAction(`unlink-${linkId}`);
    setNotice(null);
    try {
      await apiFetch<void>(
        `/api/core/documents/${encodeURIComponent(detail.id)}/links/${encodeURIComponent(linkId)}`,
        { method: "DELETE" },
      );
      await reloadDetail(detail.id);
      setNotice({ tone: "success", text: "پیوند غیرفعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  function openConfig(mode: ConfigMode) {
    setConfigMode(mode);
    setConfigOrgId(manageableOrganizationOptions[0]?.id ?? "");
    setConfigEditingId(null);
    setConfigCode("");
    setConfigName("");
    setConfigDescription("");
    setCategoryParentId("");
    setRetentionDays("365");
    setRetentionBasis("created_at");
    setNotice(null);
  }

  function beginConfigEdit(item: DocumentCategoryItem | RetentionPolicyItem) {
    setConfigEditingId(item.id);
    setConfigOrgId(item.organization_id);
    setConfigCode(item.code);
    setConfigName(item.name);
    setConfigDescription(item.description ?? "");
    if (configMode === "categories" && "parent_id" in item) {
      setCategoryParentId(item.parent_id ?? "");
    }
    if (configMode === "retention" && "retention_days" in item) {
      setRetentionDays(String(item.retention_days));
      setRetentionBasis(item.basis);
    }
  }

  function clearConfigEditor() {
    setConfigEditingId(null);
    setConfigCode("");
    setConfigName("");
    setConfigDescription("");
    setCategoryParentId("");
    setRetentionDays("365");
    setRetentionBasis("created_at");
  }

  async function createConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configMode) return;
    setBusyAction("config-create");
    setNotice(null);
    try {
      if (configMode === "categories") {
        const payload = {
          code: configCode.trim(),
          name: configName.trim(),
          description: configDescription.trim() || null,
          parent_id: categoryParentId || null,
        };
        if (configEditingId) {
          const updated = await apiFetch<DocumentCategoryItem>(
            `/api/core/document-categories/${encodeURIComponent(configEditingId)}`,
            { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
          );
          setCategories((current) => current.map((item) => item.id === updated.id ? updated : item));
          setNotice({ tone: "success", text: "دسته‌بندی به‌روزرسانی شد." });
        } else {
          const created = await apiFetch<DocumentCategoryItem>("/api/core/document-categories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ organization_id: configOrgId, ...payload }),
          });
          setCategories((current) => [...current, created]);
          setNotice({ tone: "success", text: "دسته‌بندی جدید ایجاد شد." });
        }
      } else {
        const payload = {
          code: configCode.trim(),
          name: configName.trim(),
          description: configDescription.trim() || null,
          retention_days: Number(retentionDays),
          basis: retentionBasis,
        };
        if (configEditingId) {
          const updated = await apiFetch<RetentionPolicyItem>(
            `/api/core/document-retention-policies/${encodeURIComponent(configEditingId)}`,
            { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
          );
          setRetentionPolicies((current) => current.map((item) => item.id === updated.id ? updated : item));
          setNotice({ tone: "success", text: "سیاست نگهداری به‌روزرسانی شد." });
        } else {
          const created = await apiFetch<RetentionPolicyItem>("/api/core/document-retention-policies", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ organization_id: configOrgId, ...payload }),
          });
          setRetentionPolicies((current) => [...current, created]);
          setNotice({ tone: "success", text: "سیاست نگهداری جدید ایجاد شد." });
        }
      }
      clearConfigEditor();
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  async function toggleConfigItem(kind: ConfigMode, id: string, active: boolean) {
    setBusyAction(`config-${id}`);
    setNotice(null);
    const base = kind === "categories" ? "/api/core/document-categories" : "/api/core/document-retention-policies";
    try {
      if (active) {
        await apiFetch<void>(`${base}/${encodeURIComponent(id)}`, { method: "DELETE" });
      } else {
        await apiFetch(`${base}/${encodeURIComponent(id)}/restore`, { method: "POST" });
      }
      await loadSupportingData();
      setNotice({ tone: "success", text: active ? "مورد انتخابی غیرفعال شد." : "مورد انتخابی دوباره فعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationMessage(error) });
    } finally {
      setBusyAction("");
    }
  }

  return (
    <section className="page-section document-management">
      <div className="page-title management-page-title">
        <div>
          <span>Documents Core</span>
          <h1>مدیریت اسناد</h1>
          <p>جستجو، ثبت، نسخه‌بندی، بایگانی، دانلود و اتصال اسناد در محدوده مجاز سازمانی.</p>
        </div>
        <div className="management-title-actions document-title-actions">
          <div className="count-box"><span>نتیجه فعلی</span><strong>{documents.length.toLocaleString("fa-IR")}</strong></div>
          {canManageAny ? <button className="secondary-action-button" type="button" onClick={() => openConfig("categories")}>دسته‌بندی‌ها</button> : null}
          {canManageAny ? <button className="secondary-action-button" type="button" onClick={() => openConfig("retention")}>نگهداری</button> : null}
          {canManageAny && manageableOrganizationOptions.length > 0 ? <button className="primary-action-button" type="button" onClick={openCreate}>+ سند جدید</button> : null}
        </div>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      <form className="document-filter-bar" onSubmit={(event) => { event.preventDefault(); void loadDocuments(); }}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جستجو در عنوان، نوع و توضیحات…" />
        <select value={organizationFilter} onChange={(event) => setOrganizationFilter(event.target.value)}>
          <option value="">همه سازمان‌ها</option>
          {organizationOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as DocumentStatus | "")}>
          <option value="">همه وضعیت‌ها</option>
          <option value="active">فعال</option><option value="archived">بایگانی‌شده</option><option value="disabled">غیرفعال</option>
        </select>
        <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value as DocumentPriority | "")}>
          <option value="">همه اولویت‌ها</option>
          <option value="low">کم</option><option value="normal">عادی</option><option value="high">بالا</option><option value="critical">بحرانی</option>
        </select>
        <button className="secondary-action-button" type="submit" disabled={loading}>اعمال فیلتر</button>
      </form>

      {loading ? <AsyncState label="در حال دریافت اسناد…" /> : (
        <div className="document-table-shell">
          <div className="document-table" role="table" aria-label="فهرست اسناد">
            <div className="document-table-row document-table-head" role="row">
              <span>سند</span><span>سازمان</span><span>دسته / اولویت</span><span>انقضا</span><span>وضعیت</span>
            </div>
            {documents.map((item) => (
              <button className={`document-table-row document-row-button ${item.status !== "active" ? "is-muted" : ""}`} type="button" role="row" key={item.id} onClick={() => void openDetail(item.id)}>
                <span><strong>{item.title}</strong><small dir="ltr">{item.document_type}</small></span>
                <span>{organizationName(item.organization_id, organizations, assignments)}</span>
                <span><b>{item.category_id ? categoryMap.get(item.category_id)?.name ?? "دسته نامشخص" : "بدون دسته"}</b><small>{documentPriorityLabels[item.priority]}</small></span>
                <span>{formatDocumentDate(item.expires_at)}</span>
                <span><i className={`document-status-dot status-${item.status}`} />{documentStatusLabels[item.status]}</span>
              </button>
            ))}
          </div>
          {documents.length === 0 ? <div className="empty-state">سندی با فیلتر فعلی پیدا نشد.</div> : null}
          {documents.length >= 200 ? <div className="document-result-cap">نمایش فعلی به ۲۰۰ رکورد محدود است؛ برای نتیجه دقیق‌تر از فیلتر استفاده کنید.</div> : null}
        </div>
      )}

      {selectedId ? (
        <div className="management-dialog-layer document-detail-layer">
          <button type="button" className="management-dialog-backdrop" aria-label="بستن جزئیات" onClick={closeDetail} />
          <article className="management-dialog document-detail-dialog">
            <div className="management-dialog-head">
              <div><span>Document Detail</span><h2>{detail?.title ?? "جزئیات سند"}</h2></div>
              <button type="button" onClick={closeDetail}>بستن</button>
            </div>
            {detailLoading && !detail ? <AsyncState label="در حال دریافت جزئیات…" /> : null}
            {detail ? (
              <>
                <div className="document-detail-summary">
                  <span>{organizationName(detail.organization_id, organizations, assignments)}</span>
                  <span>{documentStatusLabels[detail.status]}</span>
                  <span>{documentPriorityLabels[detail.priority]}</span>
                  <span>{detail.versions.length.toLocaleString("fa-IR")} نسخه</span>
                </div>
                <div className="document-detail-actions">
                  <button type="button" className="secondary-action-button" onClick={() => void downloadLatest()} disabled={busyAction === "download" || detail.versions.length === 0}>دانلود آخرین نسخه</button>
                  {canManageDocumentsForOrganization(detail.organization_id, organizations, assignments) && detail.status === "active" ? <button type="button" className="secondary-action-button" onClick={openEdit}>ویرایش مشخصات</button> : null}
                  {canManageDocumentsForOrganization(detail.organization_id, organizations, assignments) && (detail.status === "active" || detail.status === "archived") ? (
                    <button type="button" className={`status-action-button ${detail.status === "archived" ? "success" : "danger"}`} onClick={() => void toggleArchive()} disabled={Boolean(busyAction)}>
                      {detail.status === "archived" ? "بازیابی" : "بایگانی"}
                    </button>
                  ) : null}
                </div>
                <div className="document-detail-tabs" role="tablist">
                  <button type="button" className={detailTab === "metadata" ? "active" : ""} onClick={() => setDetailTab("metadata")}>مشخصات</button>
                  <button type="button" className={detailTab === "versions" ? "active" : ""} onClick={() => setDetailTab("versions")}>نسخه‌ها</button>
                  <button type="button" className={detailTab === "links" ? "active" : ""} onClick={() => setDetailTab("links")}>پیوندها</button>
                  {canAdminDocumentAcl(detail.organization_id) ? <button type="button" className={detailTab === "permissions" ? "active" : ""} onClick={() => void openPermissions()}>دسترسی سند</button> : null}
                  <button type="button" className={detailTab === "timeline" ? "active" : ""} onClick={() => void openTimeline()}>تاریخچه</button>
                </div>
                <div className="document-detail-body">
                  {detailTab === "metadata" ? (
                    <div className="document-metadata-grid">
                      <Info label="نوع سند" value={detail.document_type} ltr />
                      <Info label="دسته‌بندی" value={detail.category_id ? categoryMap.get(detail.category_id)?.name ?? "—" : "—"} />
                      <Info label="تاریخ انقضا" value={formatDocumentDate(detail.expires_at)} />
                      <Info label="سیاست نگهداری" value={detail.retention_policy_id ? policyMap.get(detail.retention_policy_id)?.name ?? "—" : "—"} />
                      <Info label="بررسی نگهداری" value={formatDocumentDate(detail.retention_review_at)} />
                      <Info label="ایجاد" value={formatDocumentDate(detail.created_at)} />
                      <div className="document-description"><span>توضیحات</span><p>{detail.description || "توضیحی ثبت نشده است."}</p></div>
                    </div>
                  ) : null}

                  {detailTab === "versions" ? (
                    <div className="document-version-section">
                      {canManageDocumentsForOrganization(detail.organization_id, organizations, assignments) && detail.status === "active" ? (
                        <form className="document-upload-box" onSubmit={(event) => void uploadVersion(event)}>
                          <label><span>افزودن نسخه جدید</span><input type="file" accept={ALLOWED_UPLOADS} onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} /></label>
                          <button type="submit" className="primary-action-button" disabled={!uploadFile || busyAction === "upload"}>{busyAction === "upload" ? "در حال بارگذاری…" : "ثبت نسخه"}</button>
                          <small>حداکثر ۵۰MB؛ PDF, DOCX, XLSX, PNG, JPG/JPEG</small>
                        </form>
                      ) : null}
                      <div className="document-version-list">
                        {[...detail.versions].reverse().map((version) => (
                          <div className="document-version-row" key={version.id}>
                            <div><strong>نسخه {version.version_number.toLocaleString("fa-IR")}</strong><span>{version.file_name}</span></div>
                            <div><span>{formatFileSize(version.size_bytes)}</span><small>{formatDocumentDate(version.created_at)}</small></div>
                          </div>
                        ))}
                        {detail.versions.length === 0 ? <div className="empty-state compact-empty">هنوز فایلی برای این سند ثبت نشده است.</div> : null}
                      </div>
                    </div>
                  ) : null}

                  {detailTab === "links" ? (
                    <div className="document-link-section">
                      {canManageDocumentsForOrganization(detail.organization_id, organizations, assignments) && detail.status === "active" ? (
                        <form className="document-link-form" onSubmit={(event) => void addLink(event)}>
                          <select value={linkType} onChange={(event) => { setLinkType(event.target.value as DocumentLinkEntityType); setLinkEntityId(""); }}>
                            {canReadPeople ? <option value="person">شخص</option> : null}
                            <option value="organization">سازمان مالک</option>
                          </select>
                          {linkType === "person" ? (
                            <select value={linkEntityId} onChange={(event) => setLinkEntityId(event.target.value)} required>
                              <option value="">انتخاب شخص…</option>
                              {people.filter((person) => person.is_active && person.relationships.some((rel) => rel.is_active && rel.organization_id === detail.organization_id)).map((person) => <option key={person.id} value={person.id}>{person.first_name} {person.last_name}</option>)}
                            </select>
                          ) : (
                            <select value={linkEntityId} onChange={(event) => setLinkEntityId(event.target.value)} required>
                              <option value="">انتخاب سازمان…</option>
                              <option value={detail.organization_id}>{organizationName(detail.organization_id, organizations, assignments)}</option>
                            </select>
                          )}
                          <button type="submit" className="primary-action-button" disabled={!linkEntityId || busyAction === "link"}>افزودن پیوند</button>
                        </form>
                      ) : null}
                      <div className="document-link-list">
                        {detail.links.map((link) => {
                          const label = link.entity_type === "organization"
                            ? organizationName(link.entity_id, organizations, assignments)
                            : people.find((person) => person.id === link.entity_id)
                              ? `${people.find((person) => person.id === link.entity_id)?.first_name} ${people.find((person) => person.id === link.entity_id)?.last_name}`
                              : `شخص ${link.entity_id.slice(0, 8)}`;
                          return <div className="document-link-row" key={link.id}><div><strong>{label}</strong><span>{link.entity_type === "person" ? "شخص" : "سازمان"}</span></div>{canManageDocumentsForOrganization(detail.organization_id, organizations, assignments) && detail.status === "active" ? <button type="button" className="status-action-button danger" disabled={busyAction === `unlink-${link.id}`} onClick={() => void removeLink(link.id)}>حذف پیوند</button> : null}</div>;
                        })}
                        {detail.links.length === 0 ? <div className="empty-state compact-empty">پیوند فعالی برای این سند ثبت نشده است.</div> : null}
                      </div>
                    </div>
                  ) : null}

                  {detailTab === "permissions" ? (
                    detailLoading ? <AsyncState label="در حال دریافت دسترسی‌های سند…" /> : (
                      <div className="document-acl-section">
                        <AppNotice tone="info">
                          {documentPermissions.length === 0
                            ? "این سند فعلاً ACL محدودکننده ندارد و از دسترسی سازمانی ارث می‌برد. اولین ACL باید از نوع مدیریت باشد."
                            : "ACL سند فقط دسترسی سازمانی موجود را محدودتر می‌کند؛ هیچ Roleای با این ACL به سازمان یا سند خارج از Scope خود دسترسی تازه نمی‌گیرد."}
                        </AppNotice>

                        {canReadAccess ? (
                          <form className="document-acl-form" onSubmit={(event) => void grantDocumentAcl(event)}>
                            <label>
                              <span>نوع دسترسی</span>
                              <select
                                value={documentPermissions.length === 0 ? "manage" : aclPermissionType}
                                onChange={(event) => { setAclPermissionType(event.target.value as DocumentPermissionType); setAclRoleId(""); }}
                                disabled={documentPermissions.length === 0}
                              >
                                <option value="manage">مدیریت سند</option>
                                {documentPermissions.length > 0 ? <option value="read">مشاهده سند</option> : null}
                              </select>
                            </label>
                            <label>
                              <span>Role مجاز</span>
                              <select value={aclRoleId} onChange={(event) => setAclRoleId(event.target.value)} required>
                                <option value="">انتخاب Role…</option>
                                {eligibleAclRoles.map((role) => (
                                  <option key={role.id} value={role.id}>{role.name} — {role.organization_name ?? "سیستمی"}</option>
                                ))}
                              </select>
                            </label>
                            <button type="submit" className="primary-action-button" disabled={!aclRoleId || busyAction === "acl-grant"}>
                              {busyAction === "acl-grant" ? "در حال ثبت…" : "افزودن دسترسی"}
                            </button>
                          </form>
                        ) : (
                          <div className="management-form-note">برای انتخاب Role جدید باید مجوز <span dir="ltr">access.read</span> داشته باشید. دسترسی‌های فعلی همچنان قابل مشاهده و لغو هستند.</div>
                        )}

                        <div className="document-acl-list">
                          {documentPermissions.map((permission) => {
                            const role = aclRoles.find((item) => item.id === permission.role_id);
                            return (
                              <div className="document-acl-row" key={permission.id}>
                                <div>
                                  <strong>{role?.name ?? `Role ${permission.role_id.slice(0, 8)}`}</strong>
                                  <span>{permission.permission_type === "manage" ? "مدیریت سند" : "مشاهده سند"}</span>
                                  {role?.organization_name ? <small>{role.organization_name}</small> : null}
                                </div>
                                <button
                                  type="button"
                                  className="status-action-button danger"
                                  onClick={() => void revokeDocumentAcl(permission.id)}
                                  disabled={busyAction === `acl-revoke-${permission.id}`}
                                >
                                  لغو
                                </button>
                              </div>
                            );
                          })}
                          {aclLoaded && documentPermissions.length === 0 ? <div className="empty-state compact-empty">ACL فعالی وجود ندارد؛ دسترسی سند از سطح سازمان ارث می‌برد.</div> : null}
                        </div>
                        <small className="document-acl-recovery-note"><span dir="ltr">access.manage</span> فقط مسیر بازیابی/مدیریت ACL است و به‌تنهایی اجازه مشاهده یا دانلود محتوای سند نمی‌دهد.</small>
                      </div>
                    )
                  ) : null}

                  {detailTab === "timeline" ? (
                    detailLoading ? <AsyncState label="در حال دریافت تاریخچه…" /> : (
                      <div className="document-timeline-list">
                        {timeline.map((event) => <div className="document-timeline-row" key={event.id}><i /><div><strong>{event.action}</strong><span>{event.actor_identifier ?? "system"}</span></div><time>{new Date(event.occurred_at).toLocaleString("fa-IR")}</time></div>)}
                        {timeline.length === 0 ? <div className="empty-state compact-empty">رویدادی برای نمایش وجود ندارد.</div> : null}
                      </div>
                    )
                  ) : null}
                </div>
              </>
            ) : null}
          </article>
        </div>
      ) : null}

      {editorMode ? (
        <div className="management-dialog-layer">
          <button type="button" className="management-dialog-backdrop" aria-label="بستن فرم" onClick={() => !busyAction && setEditorMode(null)} />
          <article className="management-dialog document-editor-dialog">
            <div className="management-dialog-head"><div><span>Documents</span><h2>{editorMode === "create" ? "ثبت سند جدید" : "ویرایش مشخصات سند"}</h2></div><button type="button" onClick={() => setEditorMode(null)} disabled={Boolean(busyAction)}>بستن</button></div>
            <form className="management-form" onSubmit={(event) => void saveDocument(event)}>
              <label><span>عنوان</span><input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} required /></label>
              <div className="management-form-columns">
                <label><span>نوع سند</span><input value={documentType} onChange={(event) => setDocumentType(event.target.value)} maxLength={100} placeholder="contract / invoice / report" required /></label>
                {editorMode === "create" ? <label><span>سازمان مالک</span><select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} required><option value="">انتخاب…</option>{manageableOrganizationOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : null}
              </div>
              {editorMode === "edit" ? (
                <>
                  <label><span>توضیحات</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={4000} rows={4} /></label>
                  <div className="management-form-columns">
                    <label><span>اولویت</span><select value={priority} onChange={(event) => setPriority(event.target.value as DocumentPriority)}><option value="low">کم</option><option value="normal">عادی</option><option value="high">بالا</option><option value="critical">بحرانی</option></select></label>
                    <label><span>دسته‌بندی</span><select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">بدون دسته</option>{selectedCategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                    <label><span>تاریخ انقضا</span><input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} /></label>
                    <label><span>سیاست نگهداری</span><select value={retentionPolicyId} onChange={(event) => setRetentionPolicyId(event.target.value)}><option value="">بدون سیاست</option>{selectedPolicies.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.retention_days.toLocaleString("fa-IR")} روز</option>)}</select></label>
                  </div>
                </>
              ) : <div className="management-form-note">پس از ثبت سند، فایل، توضیحات، دسته‌بندی، تاریخ انقضا و سیاست نگهداری از صفحه جزئیات قابل اضافه‌کردن است.</div>}
              <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setEditorMode(null)} disabled={Boolean(busyAction)}>انصراف</button><button type="submit" className="primary-action-button" disabled={busyAction === "save-document" || !title.trim() || !documentType.trim() || (editorMode === "create" && !organizationId)}>{busyAction === "save-document" ? "در حال ذخیره…" : "ذخیره"}</button></div>
            </form>
          </article>
        </div>
      ) : null}

      {configMode ? (
        <div className="management-dialog-layer">
          <button type="button" className="management-dialog-backdrop" aria-label="بستن تنظیمات" onClick={() => !busyAction && setConfigMode(null)} />
          <article className="management-dialog document-config-dialog">
            <div className="management-dialog-head"><div><span>Document Settings</span><h2>{configMode === "categories" ? "دسته‌بندی اسناد" : "سیاست‌های نگهداری"}</h2></div><button type="button" onClick={() => setConfigMode(null)} disabled={Boolean(busyAction)}>بستن</button></div>
            <form className="management-form document-config-create" onSubmit={(event) => void createConfig(event)}>
              <label><span>سازمان</span><select value={configOrgId} onChange={(event) => { setConfigOrgId(event.target.value); setCategoryParentId(""); }} required disabled={Boolean(configEditingId)}><option value="">انتخاب…</option>{manageableOrganizationOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <div className="management-form-columns"><label><span>کد</span><input value={configCode} onChange={(event) => setConfigCode(event.target.value)} pattern="[A-Za-z0-9._-]+" required /></label><label><span>نام</span><input value={configName} onChange={(event) => setConfigName(event.target.value)} required /></label></div>
              <label><span>توضیحات</span><input value={configDescription} onChange={(event) => setConfigDescription(event.target.value)} /></label>
              {configMode === "categories" ? <label><span>دسته والد</span><select value={categoryParentId} onChange={(event) => setCategoryParentId(event.target.value)}><option value="">بدون والد</option>{categories.filter((item) => item.organization_id === configOrgId && item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : <div className="management-form-columns"><label><span>مدت نگهداری (روز)</span><input type="number" min={1} max={36500} value={retentionDays} onChange={(event) => setRetentionDays(event.target.value)} required /></label><label><span>مبنای محاسبه</span><select value={retentionBasis} onChange={(event) => setRetentionBasis(event.target.value as RetentionBasis)}><option value="created_at">تاریخ ایجاد</option><option value="expires_at">تاریخ انقضا</option></select></label></div>}
              <div className="management-form-actions">{configEditingId ? <button type="button" className="secondary-action-button" onClick={clearConfigEditor} disabled={Boolean(busyAction)}>لغو ویرایش</button> : null}<button type="submit" className="primary-action-button" disabled={busyAction === "config-create" || !configOrgId || !configCode.trim() || !configName.trim()}>{configEditingId ? "ذخیره تغییرات" : "ایجاد"}</button></div>
            </form>
            <div className="document-config-list">
              {(configMode === "categories" ? categories : retentionPolicies).map((item) => (
                <div className={`document-config-row ${item.is_active ? "" : "is-muted"}`} key={item.id}>
                  <div><strong>{item.name}</strong><span dir="ltr">{item.code}</span><small>{organizationName(item.organization_id, organizations, assignments)}</small></div>
                  <div className="document-config-actions">{item.is_active ? <button type="button" className="secondary-action-button" onClick={() => beginConfigEdit(item)} disabled={Boolean(busyAction)}>ویرایش</button> : null}<button type="button" className={`status-action-button ${item.is_active ? "danger" : "success"}`} onClick={() => void toggleConfigItem(configMode, item.id, item.is_active)} disabled={Boolean(busyAction)}>{item.is_active ? "غیرفعال" : "بازیابی"}</button></div>
                </div>
              ))}
            </div>
          </article>
        </div>
      ) : null}
    </section>
  );
}

function Info({ label, value, ltr = false }: { label: string; value: string; ltr?: boolean }) {
  return <div className="document-info"><span>{label}</span><strong dir={ltr ? "ltr" : undefined}>{value}</strong></div>;
}
