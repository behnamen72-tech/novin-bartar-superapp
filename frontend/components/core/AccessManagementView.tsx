"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  AccessAssignment,
  AccessAssignmentAdminItem,
  AccessOverviewItem,
  DocumentPermissionItem,
  DocumentPermissionType,
  OrganizationItem,
  PermissionCatalogItem,
  PersonItem,
  RoleAdminItem,
  ScopeMode,
  UserItem,
} from "@/lib/core-types";
import { assignmentCoversOrganization } from "@/lib/organization-management";
import { canManageOrganizationForPermission, manageableOrganizationsForPermission } from "@/lib/people-user-management";
import { permissionLabel } from "@/lib/permissions";

type Notice = { tone: "error" | "success" | "info"; text: string } | null;
type Tab = "assignments" | "roles" | "permissions" | "document_acl";
type RoleEditor = { mode: "create" } | { mode: "edit"; role: RoleAdminItem } | null;

type Props = {
  overview: AccessOverviewItem[];
  organizations: OrganizationItem[];
  people: PersonItem[];
  users: UserItem[];
  assignments: AccessAssignment[];
  allPermissions: string[];
  onOverviewChanged: (items: AccessOverviewItem[]) => void;
};

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات اختیار کافی ندارید.",
    "Role code already exists.": "این کد Role قبلاً استفاده شده است.",
    "System and legacy global roles are immutable through the runtime API.": "Role سیستمی یا سراسری از داخل برنامه قابل تغییر نیست.",
    "Matching active access assignment already exists.": "این تخصیص دسترسی از قبل فعال است.",
    "Target user must have an active person relationship with the assignment organization.": "کاربر باید در سازمان انتخاب‌شده رابطه فعال داشته باشد.",
    "Operation would remove the last effective access manager from an organization.": "این تغییر آخرین مدیر دسترسی مؤثر سازمان را حذف می‌کند و مجاز نیست.",
    "Cannot assign an inactive role.": "Role غیرفعال قابل واگذاری نیست.",
    "Cannot reactivate an assignment for an inactive role.": "تا Role غیرفعال است، تخصیص قابل فعال‌سازی نیست.",
    "Document permission is already active for this role.": "این دسترسی سند برای Role انتخاب‌شده از قبل فعال است.",
    "The first document permission must be a manage permission.": "اولین ACL سند باید از نوع مدیریت باشد.",
    "The first manage permission must keep the current manager in control.": "اولین ACL مدیریت باید کنترل مدیر فعلی را حفظ کند.",
    "A restricted document must keep at least one active manage permission.": "سند محدودشده باید حداقل یک دسترسی مدیریت فعال داشته باشد.",
    "Role is not available for this document permission.": "Role انتخاب‌شده برای این دسترسی سند معتبر یا مؤثر نیست.",
    "Document not found.": "سند پیدا نشد یا در محدوده مدیریت ACL شما نیست.",
    "Document permission not found.": "دسترسی سند پیدا نشد یا قبلاً غیرفعال شده است.",
  };
  if (known[error.detail]) return known[error.detail];
  if (error.status === 403) return "Backend این عملیات را به‌دلیل محدوده یا سطح اختیار رد کرد.";
  if (error.status === 409) return "این تغییر با وضعیت فعلی دسترسی‌ها سازگار نیست.";
  if (error.status === 404) return "Role، Permission یا تخصیص موردنظر پیدا نشد.";
  if (error.status === 400 || error.status === 422) return "اطلاعات واردشده معتبر نیست.";
  return error.detail || "عملیات انجام نشد.";
}

function toIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function roleCoversOrganization(role: RoleAdminItem, organizationId: string, organizations: readonly OrganizationItem[]): boolean {
  if (role.organization_id === null) return true;
  return assignmentCoversOrganization(
    {
      role_code: role.code,
      organization_id: role.organization_id,
      organization_name: role.organization_name ?? role.code,
      scope_mode: "self_and_descendants",
      permissions: [],
    },
    organizationId,
    organizations,
  );
}

export function AccessManagementView({
  overview,
  organizations,
  people,
  users,
  assignments,
  allPermissions,
  onOverviewChanged,
}: Props) {
  const canManage = allPermissions.includes("access.manage");
  const [tab, setTab] = useState<Tab>("assignments");
  const [roles, setRoles] = useState<RoleAdminItem[]>([]);
  const [permissionCatalog, setPermissionCatalog] = useState<PermissionCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState("");
  const [query, setQuery] = useState("");
  const [roleEditor, setRoleEditor] = useState<RoleEditor>(null);
  const [permissionRole, setPermissionRole] = useState<RoleAdminItem | null>(null);
  const [assignmentEditor, setAssignmentEditor] = useState(false);
  const [aclDocumentId, setAclDocumentId] = useState("");
  const [recoveryPermissions, setRecoveryPermissions] = useState<DocumentPermissionItem[]>([]);
  const [recoveryLoaded, setRecoveryLoaded] = useState(false);
  const [recoveryRoleId, setRecoveryRoleId] = useState("");
  const [recoveryPermissionType, setRecoveryPermissionType] = useState<DocumentPermissionType>("manage");

  const [roleOrgId, setRoleOrgId] = useState("");
  const [roleCode, setRoleCode] = useState("");
  const [roleName, setRoleName] = useState("");
  const [roleDescription, setRoleDescription] = useState("");

  const [assignmentOrgId, setAssignmentOrgId] = useState("");
  const [assignmentUserId, setAssignmentUserId] = useState("");
  const [assignmentRoleId, setAssignmentRoleId] = useState("");
  const [scopeMode, setScopeMode] = useState<ScopeMode>("self");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");

  const manageableOrganizations = useMemo(
    () => manageableOrganizationsForPermission("access.manage", organizations, assignments),
    [assignments, organizations],
  );

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const [nextRoles, nextPermissions] = await Promise.all([
        apiFetch<RoleAdminItem[]>("/api/core/access/roles"),
        apiFetch<PermissionCatalogItem[]>("/api/core/access/permissions"),
      ]);
      setRoles(nextRoles);
      setPermissionCatalog(nextPermissions);
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key !== "Escape" || busy) return;
      setRoleEditor(null);
      setPermissionRole(null);
      setAssignmentEditor(false);
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [busy]);

  const filteredOverview = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fa");
    if (!normalized) return overview;
    return overview.filter((item) =>
      [item.user_name, item.user_email, item.role_name, item.role_code, item.organization_name]
        .some((value) => value.toLocaleLowerCase("fa").includes(normalized)),
    );
  }, [overview, query]);

  const filteredRoles = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fa");
    if (!normalized) return roles;
    return roles.filter((role) =>
      [role.code, role.name, role.organization_name ?? ""]
        .some((value) => value.toLocaleLowerCase("fa").includes(normalized)),
    );
  }, [query, roles]);

  const assignmentUsers = useMemo(() => {
    if (!assignmentOrgId) return [];
    const personIds = new Set(
      people
        .filter((person) => person.is_active && person.relationships.some((rel) => rel.is_active && rel.organization_id === assignmentOrgId))
        .map((person) => person.id),
    );
    return users.filter((user) => user.is_active && personIds.has(user.person_id));
  }, [assignmentOrgId, people, users]);

  const assignmentRoles = useMemo(
    () => roles.filter((role) => role.is_active && assignmentOrgId && roleCoversOrganization(role, assignmentOrgId, organizations)),
    [assignmentOrgId, organizations, roles],
  );

  const recoveryRoleOptions = useMemo(() => {
    const required = recoveryPermissionType === "manage" ? "documents.manage" : "documents.read";
    return roles.filter((role) => role.is_active && role.permissions.includes(required));
  }, [recoveryPermissionType, roles]);

  async function reloadOverview() {
    const next = await apiFetch<AccessOverviewItem[]>("/api/core/access-overview");
    onOverviewChanged(next);
  }

  function openCreateRole() {
    setRoleOrgId(manageableOrganizations[0]?.id ?? "");
    setRoleCode("");
    setRoleName("");
    setRoleDescription("");
    setRoleEditor({ mode: "create" });
    setNotice(null);
  }

  function openEditRole(role: RoleAdminItem) {
    setRoleOrgId(role.organization_id ?? "");
    setRoleCode(role.code);
    setRoleName(role.name);
    setRoleDescription(role.description ?? "");
    setRoleEditor({ mode: "edit", role });
    setNotice(null);
  }

  async function saveRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!roleEditor) return;
    setBusy("role-save");
    setNotice(null);
    try {
      if (roleEditor.mode === "create") {
        const created = await apiFetch<RoleAdminItem>("/api/core/access/roles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            organization_id: roleOrgId,
            code: roleCode.trim().toLowerCase(),
            name: roleName.trim(),
            description: roleDescription.trim() || null,
          }),
        });
        setRoles((current) => [...current, created].sort((a, b) => a.code.localeCompare(b.code)));
        setNotice({ tone: "success", text: "Role جدید ایجاد شد. اکنون Permissionهای لازم را به آن اضافه کنید." });
      } else {
        const updated = await apiFetch<RoleAdminItem>(`/api/core/access/roles/${encodeURIComponent(roleEditor.role.id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: roleName.trim(), description: roleDescription.trim() || null }),
        });
        setRoles((current) => current.map((item) => item.id === updated.id ? updated : item));
        setNotice({ tone: "success", text: "Role به‌روزرسانی شد." });
      }
      setRoleEditor(null);
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  async function toggleRole(role: RoleAdminItem) {
    const nextActive = !role.is_active;
    if (!window.confirm(nextActive ? `Role «${role.name}» فعال شود؟` : `Role «${role.name}» غیرفعال شود؟`)) return;
    setBusy(`role-status-${role.id}`);
    setNotice(null);
    try {
      const updated = await apiFetch<RoleAdminItem>(`/api/core/access/roles/${encodeURIComponent(role.id)}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: nextActive }),
      });
      setRoles((current) => current.map((item) => item.id === updated.id ? updated : item));
      await reloadOverview();
      setNotice({ tone: "success", text: nextActive ? "Role فعال شد." : "Role غیرفعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  async function toggleRolePermission(role: RoleAdminItem, permissionCode: string, currentlyGranted: boolean) {
    setBusy(`permission-${role.id}-${permissionCode}`);
    setNotice(null);
    try {
      const updated = await apiFetch<RoleAdminItem>(
        `/api/core/access/roles/${encodeURIComponent(role.id)}/permissions/${encodeURIComponent(permissionCode)}`,
        { method: currentlyGranted ? "DELETE" : "POST" },
      );
      setRoles((current) => current.map((item) => item.id === updated.id ? updated : item));
      setPermissionRole(updated);
      await reloadOverview();
      setNotice({ tone: "success", text: currentlyGranted ? "Permission از Role حذف شد." : "Permission به Role اضافه شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  function openAssignment() {
    const org = manageableOrganizations[0];
    setAssignmentOrgId(org?.id ?? "");
    setAssignmentUserId("");
    setAssignmentRoleId("");
    setScopeMode("self");
    setStartsAt("");
    setEndsAt("");
    setAssignmentEditor(true);
    setNotice(null);
  }

  async function createAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("assignment-create");
    setNotice(null);
    try {
      await apiFetch<AccessAssignmentAdminItem>("/api/core/access/assignments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: assignmentUserId,
          role_id: assignmentRoleId,
          organization_id: assignmentOrgId,
          scope_mode: scopeMode,
          starts_at: toIso(startsAt),
          ends_at: toIso(endsAt),
        }),
      });
      await reloadOverview();
      setAssignmentEditor(false);
      setNotice({ tone: "success", text: "Role در محدوده انتخاب‌شده به کاربر واگذار شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  async function toggleAssignment(item: AccessOverviewItem) {
    const nextActive = !item.is_active;
    if (!window.confirm(nextActive ? "این تخصیص دسترسی دوباره فعال شود؟" : "این تخصیص دسترسی غیرفعال شود؟")) return;
    setBusy(`assignment-${item.id}`);
    setNotice(null);
    try {
      await apiFetch<AccessAssignmentAdminItem>(`/api/core/access/assignments/${encodeURIComponent(item.id)}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: nextActive }),
      });
      await reloadOverview();
      setNotice({ tone: "success", text: nextActive ? "تخصیص فعال شد." : "تخصیص غیرفعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  async function loadRecoveryAcl(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const documentId = aclDocumentId.trim();
    if (!documentId) return;
    setBusy("acl-recovery-load");
    setNotice(null);
    try {
      const permissions = await apiFetch<DocumentPermissionItem[]>(
        `/api/core/documents/${encodeURIComponent(documentId)}/permissions`,
      );
      setRecoveryPermissions(permissions);
      setRecoveryLoaded(true);
      setRecoveryRoleId("");
      setRecoveryPermissionType(permissions.length === 0 ? "manage" : "read");
      setNotice({ tone: "success", text: permissions.length === 0 ? "سند ACL فعالی ندارد و دسترسی سازمانی را به ارث می‌برد." : "ACL سند برای مدیریت بازیابی بارگذاری شد." });
    } catch (error) {
      setRecoveryPermissions([]);
      setRecoveryLoaded(false);
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  async function grantRecoveryAcl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const documentId = aclDocumentId.trim();
    if (!documentId || !recoveryRoleId) return;
    setBusy("acl-recovery-grant");
    setNotice(null);
    try {
      await apiFetch<DocumentPermissionItem>(
        `/api/core/documents/${encodeURIComponent(documentId)}/permissions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role_id: recoveryRoleId, permission_type: recoveryPermissionType }),
        },
      );
      const permissions = await apiFetch<DocumentPermissionItem[]>(`/api/core/documents/${encodeURIComponent(documentId)}/permissions`);
      setRecoveryPermissions(permissions);
      setRecoveryLoaded(true);
      setRecoveryRoleId("");
      setRecoveryPermissionType(permissions.length === 0 ? "manage" : "read");
      setNotice({ tone: "success", text: "ACL سند به‌روزرسانی شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  async function revokeRecoveryAcl(permissionId: string) {
    const documentId = aclDocumentId.trim();
    if (!documentId || !window.confirm("این ACL از سند لغو شود؟")) return;
    setBusy(`acl-recovery-revoke-${permissionId}`);
    setNotice(null);
    try {
      await apiFetch<void>(
        `/api/core/documents/${encodeURIComponent(documentId)}/permissions/${encodeURIComponent(permissionId)}`,
        { method: "DELETE" },
      );
      const permissions = await apiFetch<DocumentPermissionItem[]>(`/api/core/documents/${encodeURIComponent(documentId)}/permissions`);
      setRecoveryPermissions(permissions);
      setRecoveryLoaded(true);
      setRecoveryPermissionType(permissions.length === 0 ? "manage" : "read");
      setNotice({ tone: "success", text: permissions.length === 0 ? "آخرین ACL لغو شد؛ سند دوباره از دسترسی سازمانی ارث می‌برد." : "ACL سند لغو شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="page-section access-management">
      <div className="page-title management-page-title">
        <div>
          <span>Authorization Core</span>
          <h1>مدیریت دسترسی‌ها</h1>
          <p>Role، Permission و Organization Scope. تمام تغییرات حساس دوباره در Backend بررسی و Audit می‌شوند.</p>
        </div>
        <div className="management-title-actions">
          <div className="count-box"><span>تخصیص‌ها</span><strong>{overview.length.toLocaleString("fa-IR")}</strong></div>
          {canManage && manageableOrganizations.length > 0 ? <button type="button" className="primary-action-button" onClick={openAssignment}>+ واگذاری Role</button> : null}
        </div>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}
      {canManage ? <AppNotice tone="info">Frontend فقط عملیات قابل‌انتظار را نمایش می‌دهد؛ جلوگیری از Privilege Escalation و حفظ آخرین Access Manager کاملاً در Backend انجام می‌شود.</AppNotice> : null}

      <div className="access-management-tabs">
        <button type="button" className={tab === "assignments" ? "active" : ""} onClick={() => setTab("assignments")}>تخصیص‌ها</button>
        <button type="button" className={tab === "roles" ? "active" : ""} onClick={() => setTab("roles")}>Roleها</button>
        <button type="button" className={tab === "permissions" ? "active" : ""} onClick={() => setTab("permissions")}>Permission Catalog</button>
        {canManage ? <button type="button" className={tab === "document_acl" ? "active" : ""} onClick={() => setTab("document_acl")}>بازیابی ACL سند</button> : null}
      </div>

      {tab !== "document_acl" ? <div className="management-toolbar">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جستجو در کاربر، Role یا سازمان…" />
        <span>{tab === "assignments" ? filteredOverview.length : tab === "roles" ? filteredRoles.length : permissionCatalog.length} مورد</span>
      </div> : null}

      {loading ? <AsyncState label="در حال دریافت ساختار دسترسی…" /> : null}

      {!loading && tab === "assignments" ? (
        <div className="access-admin-list">
          {filteredOverview.map((item) => (
            <article className={`access-admin-assignment ${item.is_active ? "" : "is-muted"}`} key={item.id}>
              <div><span>کاربر</span><strong>{item.user_name}</strong><small dir="ltr">{item.user_email}</small></div>
              <div><span>Role</span><strong>{item.role_name}</strong><small dir="ltr">{item.role_code}</small></div>
              <div><span>Scope</span><strong>{item.organization_name}</strong><small>{item.scope_mode === "self_and_descendants" ? "سازمان + زیرمجموعه‌ها" : "فقط همان سازمان"}</small></div>
              <div className="access-admin-permissions">{item.permissions.slice(0, 5).map((permission) => <span key={permission}>{permissionLabel(permission)}</span>)}{item.permissions.length > 5 ? <span>+{(item.permissions.length - 5).toLocaleString("fa-IR")}</span> : null}</div>
              {canManageOrganizationForPermission(item.organization_id, "access.manage", organizations, assignments) ? <button type="button" className={`status-action-button ${item.is_active ? "danger" : "success"}`} disabled={Boolean(busy)} onClick={() => void toggleAssignment(item)}>{item.is_active ? "غیرفعال‌کردن" : "فعال‌کردن"}</button> : <span className="read-only-label">فقط مشاهده</span>}
            </article>
          ))}
          {filteredOverview.length === 0 ? <div className="empty-state">تخصیصی با فیلتر فعلی پیدا نشد.</div> : null}
        </div>
      ) : null}

      {!loading && tab === "roles" ? (
        <>
          {canManage && manageableOrganizations.length > 0 ? <div className="access-role-toolbar"><button type="button" className="primary-action-button" onClick={openCreateRole}>+ Role جدید</button></div> : null}
          <div className="access-role-grid">
            {filteredRoles.map((role) => {
              const mutable = canManage && !role.is_system && role.organization_id !== null && canManageOrganizationForPermission(role.organization_id, "access.manage", organizations, assignments);
              return <article className={`access-role-admin-card ${role.is_active ? "" : "is-muted"}`} key={role.id}>
                <div className="access-role-admin-head"><div><span>{role.is_system ? "SYSTEM ROLE" : "CUSTOM ROLE"}</span><strong>{role.name}</strong><small dir="ltr">{role.code}</small></div><span className={`status-badge ${role.is_active ? "is-active" : "is-inactive"}`}>{role.is_active ? "فعال" : "غیرفعال"}</span></div>
                <p>{role.description || "توضیحی ثبت نشده است."}</p>
                <div className="access-role-owner"><span>مالک Role</span><strong>{role.organization_name ?? "Global / Legacy"}</strong></div>
                <div className="access-admin-permissions">{role.permissions.map((permission) => <span key={permission}>{permissionLabel(permission)}</span>)}{role.permissions.length === 0 ? <small>بدون Permission</small> : null}</div>
                <div className="management-card-actions">{mutable ? <><button type="button" className="secondary-action-button" onClick={() => openEditRole(role)}>ویرایش</button><button type="button" className="secondary-action-button" onClick={() => setPermissionRole(role)}>Permissionها</button><button type="button" className={`status-action-button ${role.is_active ? "danger" : "success"}`} disabled={Boolean(busy)} onClick={() => void toggleRole(role)}>{role.is_active ? "غیرفعال" : "فعال"}</button></> : <span className="read-only-label">فقط مشاهده / خارج محدوده مدیریت</span>}</div>
              </article>;
            })}
          </div>
        </>
      ) : null}

      {!loading && tab === "permissions" ? (
        <div className="permission-catalog-grid">
          {permissionCatalog.map((permission) => <article className={`permission-catalog-card ${permission.is_active ? "" : "is-muted"}`} key={permission.id}><span dir="ltr">{permission.code}</span><strong>{permissionLabel(permission.code)}</strong><p>{permission.description || permission.name}</p></article>)}
        </div>
      ) : null}

      {!loading && tab === "document_acl" ? (
        <div className="access-document-acl-recovery">
          <AppNotice tone="info">این ابزار فقط برای مدیریت/بازیابی ACL با <span dir="ltr">access.manage</span> است و محتوای سند، عنوان یا فایل را نمایش نمی‌دهد. داشتن این مجوز به‌تنهایی حق مشاهده یا دانلود سند ایجاد نمی‌کند.</AppNotice>
          <form className="access-document-id-form" onSubmit={(event) => void loadRecoveryAcl(event)}>
            <label><span>شناسه UUID سند</span><input dir="ltr" value={aclDocumentId} onChange={(event) => { setAclDocumentId(event.target.value); setRecoveryLoaded(false); setRecoveryPermissions([]); setRecoveryRoleId(""); }} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required /></label>
            <button type="submit" className="primary-action-button" disabled={!aclDocumentId.trim() || busy === "acl-recovery-load"}>{busy === "acl-recovery-load" ? "در حال بررسی…" : "بارگذاری ACL"}</button>
          </form>

          {recoveryLoaded ? (
            <div className="document-acl-section access-document-acl-result">
              <AppNotice tone="info">{recoveryPermissions.length === 0 ? "ACL فعال نیست؛ سند از مجوزهای سازمانی ارث می‌برد. برای ورود به حالت محدود، اولین ACL باید «مدیریت سند» باشد." : "حالت ACL محدودکننده فعال است. Backend اجازه حذف آخرین Manager در حالی که ACLهای دیگر باقی مانده‌اند را نمی‌دهد."}</AppNotice>
              {roles.length > 0 ? (
                <form className="document-acl-form" onSubmit={(event) => void grantRecoveryAcl(event)}>
                  <label><span>نوع دسترسی</span><select value={recoveryPermissions.length === 0 ? "manage" : recoveryPermissionType} onChange={(event) => { setRecoveryPermissionType(event.target.value as DocumentPermissionType); setRecoveryRoleId(""); }} disabled={recoveryPermissions.length === 0}><option value="manage">مدیریت سند</option>{recoveryPermissions.length > 0 ? <option value="read">مشاهده سند</option> : null}</select></label>
                  <label><span>Role</span><select value={recoveryRoleId} onChange={(event) => setRecoveryRoleId(event.target.value)} required><option value="">انتخاب Role…</option>{recoveryRoleOptions.map((role) => <option key={role.id} value={role.id}>{role.name} — {role.organization_name ?? "سیستمی"}</option>)}</select></label>
                  <button type="submit" className="primary-action-button" disabled={!recoveryRoleId || busy === "acl-recovery-grant"}>{busy === "acl-recovery-grant" ? "در حال ثبت…" : "افزودن ACL"}</button>
                </form>
              ) : <div className="management-form-note">برای انتخاب Role باید <span dir="ltr">access.read</span> نیز در محدوده مناسب داشته باشید. Backend همچنان اجازه لغو ACL موجود را طبق قواعد بازیابی بررسی می‌کند.</div>}
              <div className="document-acl-list">
                {recoveryPermissions.map((permission) => { const role = roles.find((item) => item.id === permission.role_id); return <div className="document-acl-row" key={permission.id}><div><strong>{role?.name ?? `Role ${permission.role_id.slice(0, 8)}`}</strong><span>{permission.permission_type === "manage" ? "مدیریت سند" : "مشاهده سند"}</span>{role?.organization_name ? <small>{role.organization_name}</small> : null}</div><button type="button" className="status-action-button danger" disabled={busy === `acl-recovery-revoke-${permission.id}`} onClick={() => void revokeRecoveryAcl(permission.id)}>لغو</button></div>; })}
                {recoveryPermissions.length === 0 ? <div className="empty-state compact-empty">ACL فعالی برای این شناسه وجود ندارد.</div> : null}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {roleEditor ? (
        <div className="management-dialog-layer"><button type="button" className="management-dialog-backdrop" aria-label="بستن فرم Role" onClick={() => !busy && setRoleEditor(null)} /><article className="management-dialog"><div className="management-dialog-head"><div><span>Access Role</span><h2>{roleEditor.mode === "create" ? "ساخت Role" : "ویرایش Role"}</h2></div><button type="button" onClick={() => setRoleEditor(null)} disabled={Boolean(busy)}>بستن</button></div><form className="management-form" onSubmit={(event) => void saveRole(event)}>{roleEditor.mode === "create" ? <label><span>سازمان مالک</span><select value={roleOrgId} onChange={(event) => setRoleOrgId(event.target.value)} required><option value="">انتخاب…</option>{manageableOrganizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label> : <div className="management-form-note">مالک و کد Role بعد از ایجاد تغییر نمی‌کند؛ فقط نام و توضیحات قابل ویرایش است.</div>}<div className="management-form-columns">{roleEditor.mode === "create" ? <label><span>کد Role</span><input value={roleCode} onChange={(event) => setRoleCode(event.target.value)} maxLength={100} required /></label> : null}<label><span>نام Role</span><input value={roleName} onChange={(event) => setRoleName(event.target.value)} maxLength={160} required /></label></div><label><span>توضیحات</span><textarea value={roleDescription} onChange={(event) => setRoleDescription(event.target.value)} maxLength={500} rows={3} /></label><div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setRoleEditor(null)} disabled={Boolean(busy)}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy === "role-save" || !roleName.trim() || (roleEditor.mode === "create" && (!roleOrgId || !roleCode.trim()))}>{busy === "role-save" ? "در حال ذخیره…" : "ذخیره"}</button></div></form></article></div>
      ) : null}

      {permissionRole ? (
        <div className="management-dialog-layer"><button type="button" className="management-dialog-backdrop" aria-label="بستن Permissionها" onClick={() => !busy && setPermissionRole(null)} /><article className="management-dialog access-permission-dialog"><div className="management-dialog-head"><div><span>Role Permissions</span><h2>{permissionRole.name}</h2></div><button type="button" onClick={() => setPermissionRole(null)} disabled={Boolean(busy)}>بستن</button></div><div className="access-permission-list">{permissionCatalog.filter((permission) => permission.is_active).map((permission) => { const granted = permissionRole.permissions.includes(permission.code); const actorHasSomewhere = allPermissions.includes(permission.code); return <div className="access-permission-row" key={permission.id}><div><strong>{permissionLabel(permission.code)}</strong><span dir="ltr">{permission.code}</span></div><button type="button" className={granted ? "status-action-button danger" : "status-action-button success"} disabled={Boolean(busy) || (!granted && !actorHasSomewhere)} title={!granted && !actorHasSomewhere ? "این Permission در دسترسی مؤثر فعلی شما وجود ندارد" : undefined} onClick={() => void toggleRolePermission(permissionRole, permission.code, granted)}>{granted ? "حذف" : "افزودن"}</button></div>; })}</div></article></div>
      ) : null}

      {assignmentEditor ? (
        <div className="management-dialog-layer"><button type="button" className="management-dialog-backdrop" aria-label="بستن فرم تخصیص" onClick={() => !busy && setAssignmentEditor(false)} /><article className="management-dialog access-assignment-dialog"><div className="management-dialog-head"><div><span>Role Assignment</span><h2>واگذاری دسترسی</h2></div><button type="button" onClick={() => setAssignmentEditor(false)} disabled={Boolean(busy)}>بستن</button></div><form className="management-form" onSubmit={(event) => void createAssignment(event)}><label><span>سازمان مبنای Scope</span><select value={assignmentOrgId} onChange={(event) => { setAssignmentOrgId(event.target.value); setAssignmentUserId(""); setAssignmentRoleId(""); }} required><option value="">انتخاب…</option>{manageableOrganizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label><div className="management-form-columns"><label><span>کاربر</span><select value={assignmentUserId} onChange={(event) => setAssignmentUserId(event.target.value)} required><option value="">انتخاب…</option>{assignmentUsers.map((user) => <option key={user.id} value={user.id}>{user.person_name} — {user.email}</option>)}</select><small>فقط کاربران دارای رابطه فعال در همین سازمان نمایش داده می‌شوند.</small></label><label><span>Role</span><select value={assignmentRoleId} onChange={(event) => setAssignmentRoleId(event.target.value)} required><option value="">انتخاب…</option>{assignmentRoles.map((role) => <option key={role.id} value={role.id}>{role.name} ({role.code})</option>)}</select></label><label><span>Scope</span><select value={scopeMode} onChange={(event) => setScopeMode(event.target.value as ScopeMode)}><option value="self">فقط همان سازمان</option><option value="self_and_descendants">سازمان + زیرمجموعه‌ها</option></select></label></div><div className="management-form-columns"><label><span>شروع اختیاری</span><input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label><label><span>پایان اختیاری</span><input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label></div><div className="management-form-note">Backend بررسی می‌کند که شما تمام Permissionهای Role را در کل Scope انتخاب‌شده قابل واگذاری داشته باشید؛ UI این کنترل امنیتی را جایگزین نمی‌کند.</div><div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setAssignmentEditor(false)} disabled={Boolean(busy)}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy === "assignment-create" || !assignmentOrgId || !assignmentUserId || !assignmentRoleId}>{busy === "assignment-create" ? "در حال واگذاری…" : "واگذاری Role"}</button></div></form></article></div>
      ) : null}
    </section>
  );
}
