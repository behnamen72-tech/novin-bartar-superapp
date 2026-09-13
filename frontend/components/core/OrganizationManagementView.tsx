"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  AccessAssignment,
  OrganizationItem,
  OrganizationType,
} from "@/lib/core-types";
import {
  allowedChildTypes,
  canActivateOrganization,
  canCreateChildUnder,
  canManageOrganization,
  hasActiveChildren,
  manageableCreateParents,
  normalizedOrganizationCode,
} from "@/lib/organization-management";

type OrganizationManagementViewProps = {
  organizations: OrganizationItem[];
  assignments: AccessAssignment[];
  onOrganizationChanged: (organization: OrganizationItem, created: boolean) => void;
};

type EditorState =
  | { mode: "closed" }
  | { mode: "create"; parentId: string; organizationType: OrganizationType }
  | { mode: "edit"; organization: OrganizationItem };

const typeLabels: Record<OrganizationType, string> = {
  holding: "هلدینگ",
  company: "شرکت",
  branch: "شعبه",
  unit: "واحد",
};

function mutationErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  }

  const known: Record<string, string> = {
    "Organization code already exists.": "این کد سازمان قبلاً استفاده شده است.",
    "Parent organization is inactive.": "سازمان بالادستی غیرفعال است.",
    "Deactivate active child organizations before deactivating the parent.":
      "قبل از غیرفعال‌کردن این سازمان، زیرمجموعه‌های فعال را غیرفعال کنید.",
    "Cannot activate an organization while its parent is inactive.":
      "تا زمانی که سازمان بالادستی غیرفعال است، این سازمان قابل فعال‌سازی نیست.",
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Organization not found.": "سازمان موردنظر پیدا نشد یا دیگر در دسترس شما نیست.",
  };

  if (known[error.detail]) return known[error.detail];
  if (error.status === 403) return "برای این عملیات مجوز کافی ندارید.";
  if (error.status === 409) return "این تغییر با وضعیت فعلی اطلاعات سازگار نیست.";
  if (error.status === 400) return "اطلاعات واردشده معتبر نیست.";
  return error.detail || "عملیات انجام نشد.";
}

export function OrganizationManagementView({
  organizations,
  assignments,
  onOrganizationChanged,
}: OrganizationManagementViewProps) {
  const [editor, setEditor] = useState<EditorState>({ mode: "closed" });
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [parentId, setParentId] = useState("");
  const [organizationType, setOrganizationType] = useState<OrganizationType>("company");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const byId = useMemo(
    () => new Map(organizations.map((organization) => [organization.id, organization])),
    [organizations],
  );
  const createParents = useMemo(
    () => manageableCreateParents(organizations, assignments),
    [organizations, assignments],
  );
  const manageableCount = useMemo(
    () =>
      organizations.filter((organization) =>
        canManageOrganization(organization.id, organizations, assignments),
      ).length,
    [organizations, assignments],
  );

  function depthOf(item: OrganizationItem): number {
    let depth = 0;
    let current = item;
    const visited = new Set<string>();

    while (current.parent_id && byId.has(current.parent_id) && !visited.has(current.id)) {
      visited.add(current.id);
      const parent = byId.get(current.parent_id);
      if (!parent) break;
      depth += 1;
      current = parent;
    }
    return depth;
  }

  const sorted = useMemo(
    () =>
      [...organizations].sort((a, b) => {
        const depthDiff = depthOf(a) - depthOf(b);
        if (depthDiff !== 0) return depthDiff;
        return a.name.localeCompare(b.name, "fa");
      }),
    // depthOf intentionally derives only from byId/organizations.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [organizations, byId],
  );

  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && editor.mode !== "closed" && !saving) {
        setEditor({ mode: "closed" });
      }
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [editor.mode, saving]);

  function openCreate() {
    const firstParent = createParents[0];
    if (!firstParent) return;
    const firstType = allowedChildTypes(firstParent.organization_type)[0];
    if (!firstType) return;
    setNotice(null);
    setName("");
    setCode("");
    setParentId(firstParent.id);
    setOrganizationType(firstType);
    setEditor({ mode: "create", parentId: firstParent.id, organizationType: firstType });
  }

  function openEdit(organization: OrganizationItem) {
    setNotice(null);
    setName(organization.name);
    setCode(organization.code);
    setEditor({ mode: "edit", organization });
  }

  function changeParent(nextParentId: string) {
    setParentId(nextParentId);
    const parent = byId.get(nextParentId);
    const nextType = parent ? allowedChildTypes(parent.organization_type)[0] : undefined;
    if (nextType) setOrganizationType(nextType);
  }

  async function submitEditor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setNotice(null);

    try {
      if (editor.mode === "create") {
        if (!parentId || !canCreateChildUnder(parentId, organizations, assignments)) {
          throw new ApiError(403, "Permission denied.");
        }

        const created = await apiFetch<OrganizationItem>("/api/core/organizations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name.trim(),
            code: normalizedOrganizationCode(code),
            organization_type: organizationType,
            parent_id: parentId,
          }),
        });
        onOrganizationChanged(created, true);
        setEditor({ mode: "closed" });
        setNotice({ tone: "success", text: "سازمان جدید با موفقیت ایجاد شد." });
      } else if (editor.mode === "edit") {
        const updated = await apiFetch<OrganizationItem>(
          `/api/core/organizations/${encodeURIComponent(editor.organization.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: name.trim(),
              code: normalizedOrganizationCode(code),
            }),
          },
        );
        onOrganizationChanged(updated, false);
        setEditor({ mode: "closed" });
        setNotice({ tone: "success", text: "اطلاعات سازمان به‌روزرسانی شد." });
      }
    } catch (error) {
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(organization: OrganizationItem) {
    const nextActive = !organization.is_active;
    const warning = nextActive
      ? `سازمان «${organization.name}» دوباره فعال شود؟`
      : `سازمان «${organization.name}» غیرفعال شود؟`;
    if (!window.confirm(warning)) return;

    setBusyId(organization.id);
    setNotice(null);
    try {
      const updated = await apiFetch<OrganizationItem>(
        `/api/core/organizations/${encodeURIComponent(organization.id)}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: nextActive }),
        },
      );
      onOrganizationChanged(updated, false);
      setNotice({
        tone: "success",
        text: nextActive ? "سازمان فعال شد." : "سازمان غیرفعال شد.",
      });
    } catch (error) {
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="page-section organization-management">
      <div className="page-title organization-page-title">
        <div>
          <span>Organization Core</span>
          <h1>ساختار سازمانی</h1>
          <p>
            ساختار هلدینگ، شرکت، شعبه و واحد. عملیات مدیریتی فقط در Scope مجاز نمایش داده
            می‌شود و Backend مرجع نهایی مجوزهاست.
          </p>
        </div>
        <div className="organization-title-actions">
          <div className="count-box">
            <span>قابل مشاهده</span>
            <strong>{organizations.length.toLocaleString("fa-IR")}</strong>
          </div>
          {createParents.length > 0 ? (
            <button type="button" className="primary-action-button" onClick={openCreate}>
              + سازمان جدید
            </button>
          ) : null}
        </div>
      </div>

      <div className="organization-management-summary" aria-label="خلاصه مدیریت سازمان">
        <span>{manageableCount.toLocaleString("fa-IR")} سازمان قابل مدیریت</span>
        <span>{createParents.length.toLocaleString("fa-IR")} محل مجاز برای ایجاد زیرمجموعه</span>
        <span>جابجایی Parent و تغییر نوع سازمان در این نسخه عمداً غیرفعال است</span>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      <div className="organization-tree organization-tree-manage">
        {sorted.map((organization) => {
          const manageable = canManageOrganization(
            organization.id,
            organizations,
            assignments,
          );
          const activeChildren = hasActiveChildren(organization.id, organizations);
          const activationAllowed = canActivateOrganization(organization, organizations);
          const rootHolding =
            organization.organization_type === "holding" && organization.parent_id === null;
          const statusDisabled = rootHolding ||
            (organization.is_active ? activeChildren : !activationAllowed);

          return (
            <article
              className={`organization-row organization-row-manage ${
                organization.is_active ? "" : "is-muted"
              }`}
              key={organization.id}
              style={{ marginRight: `${depthOf(organization) * 30}px` }}
            >
              <div className="tree-mark">{depthOf(organization) === 0 ? "●" : "↳"}</div>
              <div className="entity-main">
                <strong>{organization.name}</strong>
                <span dir="ltr">{organization.code}</span>
              </div>
              <span className="entity-type">{typeLabels[organization.organization_type]}</span>
              <span className={`status-badge ${organization.is_active ? "is-active" : "is-inactive"}`}>
                {organization.is_active ? "فعال" : "غیرفعال"}
              </span>
              <div className="organization-row-actions">
                {manageable ? (
                  <>
                    <button
                      type="button"
                      className="secondary-action-button"
                      onClick={() => openEdit(organization)}
                      disabled={busyId === organization.id}
                    >
                      ویرایش
                    </button>
                    <button
                      type="button"
                      className={`status-action-button ${organization.is_active ? "danger" : "success"}`}
                      onClick={() => void toggleStatus(organization)}
                      disabled={busyId === organization.id || statusDisabled}
                      title={
                        rootHolding
                          ? "وضعیت هلدینگ ریشه فقط از مسیر Bootstrap مدیریت می‌شود."
                          : organization.is_active && activeChildren
                            ? "ابتدا زیرمجموعه‌های فعال را غیرفعال کنید."
                            : !organization.is_active && !activationAllowed
                              ? "ابتدا سازمان بالادستی را فعال کنید."
                              : undefined
                      }
                    >
                      {busyId === organization.id
                        ? "در حال ثبت…"
                        : organization.is_active
                          ? "غیرفعال"
                          : "فعال‌سازی"}
                    </button>
                  </>
                ) : (
                  <span className="read-only-label">فقط مشاهده</span>
                )}
              </div>
            </article>
          );
        })}
        {organizations.length === 0 ? (
          <div className="empty-state">داده‌ای در محدوده دسترسی شما وجود ندارد.</div>
        ) : null}
      </div>

      {editor.mode !== "closed" ? (
        <div className="management-dialog-layer" role="presentation">
          <button
            type="button"
            className="management-dialog-backdrop"
            aria-label="بستن پنجره"
            onClick={() => !saving && setEditor({ mode: "closed" })}
          />
          <div
            className="management-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="organization-editor-title"
          >
            <div className="management-dialog-head">
              <div>
                <span>Organization Management</span>
                <h2 id="organization-editor-title">
                  {editor.mode === "create" ? "ایجاد سازمان جدید" : "ویرایش سازمان"}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setEditor({ mode: "closed" })}
                disabled={saving}
              >
                بستن
              </button>
            </div>

            <form className="management-form" onSubmit={(event) => void submitEditor(event)}>
              <label>
                <span>نام سازمان</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  maxLength={200}
                  autoFocus
                />
              </label>

              <label>
                <span>کد سازمان</span>
                <input
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  required
                  maxLength={50}
                  dir="ltr"
                  autoComplete="off"
                />
                <small>کد هنگام ثبت به حروف بزرگ تبدیل می‌شود.</small>
              </label>

              {editor.mode === "create" ? (
                <>
                  <label>
                    <span>سازمان بالادستی</span>
                    <select value={parentId} onChange={(event) => changeParent(event.target.value)}>
                      {createParents.map((organization) => (
                        <option key={organization.id} value={organization.id}>
                          {organization.name} — {typeLabels[organization.organization_type]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>نوع سازمان</span>
                    <select
                      value={organizationType}
                      onChange={(event) => setOrganizationType(event.target.value as OrganizationType)}
                    >
                      {(byId.get(parentId)
                        ? allowedChildTypes(byId.get(parentId)!.organization_type)
                        : []
                      ).map((type) => (
                        <option value={type} key={type}>
                          {typeLabels[type]}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              ) : (
                <div className="management-form-note">
                  نوع سازمان و Parent از این فرم قابل تغییر نیست؛ تغییر ساختار سازمانی یک عملیات
                  امنیتی مستقل خواهد بود.
                </div>
              )}

              <div className="management-form-actions">
                <button
                  type="button"
                  className="secondary-action-button"
                  onClick={() => setEditor({ mode: "closed" })}
                  disabled={saving}
                >
                  انصراف
                </button>
                <button type="submit" className="primary-action-button" disabled={saving}>
                  {saving ? "در حال ذخیره…" : editor.mode === "create" ? "ایجاد سازمان" : "ذخیره تغییرات"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
