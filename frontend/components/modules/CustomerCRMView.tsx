"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import {
  customerSourceLabels,
  customerStatusLabels,
  customerTypeLabels,
} from "@/lib/crm-management";
import type {
  CommerceActivityProjection,
  CRMAssigneeOption,
  CRMOrganizationCapability,
  CustomerCommercialStatus,
  CustomerCRMItem,
  CustomerCRMSource,
  CustomerCRMType,
  CustomerNoteItem,
  CustomerTagItem,
} from "@/lib/core-types";

function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Customer not found.": "مشتری پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Customer note not found.": "یادداشت پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Customer tag not found.": "برچسب پیدا نشد یا متعلق به این سازمان نیست.",
    "CRM customer already exists for this organization.": "این مشتری قبلاً در CRM این سازمان ثبت شده است.",
    "Commerce customer reference does not exist.": "شناسه مشتری در فروشگاه مجازی معتبر نیست.",
    "Customer record was modified by another request.": "این رکورد هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی کنید.",
    "Customer note was modified by another request.": "این یادداشت هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی کنید.",
    "Assigned owner is not an active internal user.": "مسئول انتخاب‌شده کاربر داخلی فعال نیست.",
    "Assigned owner cannot access this organization CRM context.": "مسئول انتخاب‌شده به CRM این سازمان دسترسی ندارد.",
  };
  if (error.status === 502 || error.status === 503) {
    return "ارتباط CRM با فروشگاه مجازی موقتاً در دسترس نیست. داده داخلی CRM همچنان قابل استفاده است.";
  }
  return known[error.detail] ?? error.detail ?? "عملیات انجام نشد.";
}

function isoToPersian(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function hasAnyCRMCapability(item: CRMOrganizationCapability): boolean {
  return (
    item.can_read ||
    item.can_manage ||
    item.can_read_notes ||
    item.can_manage_notes ||
    item.can_assign ||
    item.can_manage_tags ||
    item.can_read_commerce_activity
  );
}

export function CustomerCRMView() {
  const [organizations, setOrganizations] = useState<CRMOrganizationCapability[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [customers, setCustomers] = useState<CustomerCRMItem[]>([]);
  const [tags, setTags] = useState<CustomerTagItem[]>([]);
  const [assignees, setAssignees] = useState<CRMAssigneeOption[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [notes, setNotes] = useState<CustomerNoteItem[]>([]);
  const [commerceActivity, setCommerceActivity] = useState<CommerceActivityProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [search, setSearch] = useState("");

  const [createRef, setCreateRef] = useState("");
  const [createLabel, setCreateLabel] = useState("");
  const [createType, setCreateType] = useState<CustomerCRMType>("individual");
  const [createStatus, setCreateStatus] = useState<CustomerCommercialStatus>("prospect");
  const [createSource, setCreateSource] = useState<CustomerCRMSource>("manual");

  const [editLabel, setEditLabel] = useState("");
  const [editType, setEditType] = useState<CustomerCRMType>("individual");
  const [editStatus, setEditStatus] = useState<CustomerCommercialStatus>("prospect");
  const [editSource, setEditSource] = useState<CustomerCRMSource>("manual");
  const [ownerId, setOwnerId] = useState("");
  const [newTagName, setNewTagName] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [editingNoteId, setEditingNoteId] = useState("");
  const [editingNoteBody, setEditingNoteBody] = useState("");

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === organizationId),
    [organizationId, organizations],
  );
  const selectedCustomer = useMemo(
    () => customers.find((item) => item.id === selectedCustomerId),
    [customers, selectedCustomerId],
  );
  const filteredCustomers = useMemo(() => {
    const q = search.trim().toLocaleLowerCase("fa");
    if (!q) return customers;
    return customers.filter(
      (item) =>
        item.display_label.toLocaleLowerCase("fa").includes(q) ||
        item.commerce_customer_ref.toLowerCase().includes(q),
    );
  }, [customers, search]);

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const items = await apiFetch<CRMOrganizationCapability[]>("/api/modules/customers/organizations");
      setOrganizations(items);
      setOrganizationId((current) => {
        if (current && items.some((item) => item.id === current && hasAnyCRMCapability(item))) {
          return current;
        }
        return items.find(hasAnyCRMCapability)?.id ?? "";
      });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrganizationData = useCallback(
    async (targetId: string) => {
      const capability = organizations.find((item) => item.id === targetId);
      if (!capability) return;
      setRefreshing(true);
      setNotice(null);
      setSelectedCustomerId("");
      setNotes([]);
      setCommerceActivity(null);
      try {
        const requests: Promise<void>[] = [];
        if (capability.can_read) {
          const includeInactive = capability.can_manage ? "true" : "false";
          requests.push(
            apiFetch<CustomerCRMItem[]>(
              `/api/modules/customers/customers?organization_id=${encodeURIComponent(targetId)}&include_inactive=${includeInactive}&limit=200`,
            ).then(setCustomers),
          );
        } else {
          setCustomers([]);
        }
        if (capability.can_read || capability.can_manage_tags) {
          requests.push(
            apiFetch<CustomerTagItem[]>(
              `/api/modules/customers/customer-tags?organization_id=${encodeURIComponent(targetId)}&include_inactive=false`,
            ).then(setTags),
          );
        } else {
          setTags([]);
        }
        if (capability.can_assign) {
          requests.push(
            apiFetch<CRMAssigneeOption[]>(
              `/api/modules/customers/assignees?organization_id=${encodeURIComponent(targetId)}`,
            ).then(setAssignees),
          );
        } else {
          setAssignees([]);
        }
        await Promise.all(requests);
      } catch (error) {
        setCustomers([]);
        setTags([]);
        setAssignees([]);
        setNotice({ tone: "error", text: errorText(error) });
      } finally {
        setRefreshing(false);
      }
    },
    [organizations],
  );

  useEffect(() => {
    void loadOrganizations();
  }, [loadOrganizations]);

  useEffect(() => {
    if (organizationId) void loadOrganizationData(organizationId);
  }, [loadOrganizationData, organizationId]);

  useEffect(() => {
    if (!selectedCustomer) return;
    setEditLabel(selectedCustomer.display_label);
    setEditType(selectedCustomer.customer_type);
    setEditStatus(selectedCustomer.commercial_status);
    setEditSource(selectedCustomer.source);
    setOwnerId(selectedCustomer.assigned_owner_user_id ?? "");
    setNotes([]);
    setCommerceActivity(null);
    setEditingNoteId("");
    setEditingNoteBody("");
  }, [selectedCustomer]);

  const refreshCustomer = useCallback((saved: CustomerCRMItem) => {
    setCustomers((current) => current.map((item) => (item.id === saved.id ? saved : item)));
  }, []);

  async function submitCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization?.can_manage) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<CustomerCRMItem>("/api/modules/customers/customers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: selectedOrganization.id,
          commerce_customer_ref: createRef.trim(),
          display_label: createLabel.trim(),
          customer_type: createType,
          commercial_status: createStatus,
          source: createSource,
        }),
      });
      setCustomers((current) => [saved, ...current]);
      setSelectedCustomerId(saved.id);
      setCreateRef("");
      setCreateLabel("");
      setNotice({ tone: "success", text: "رکورد CRM مشتری ساخته شد؛ هویت مشتری همچنان در فروشگاه مجازی باقی می‌ماند." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function submitCustomerEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCustomer || !selectedOrganization?.can_manage) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<CustomerCRMItem>(
        `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expected_version: selectedCustomer.version,
            display_label: editLabel.trim(),
            customer_type: editType,
            commercial_status: editStatus,
            source: editSource,
          }),
        },
      );
      refreshCustomer(saved);
      setNotice({ tone: "success", text: "اطلاعات داخلی CRM به‌روزرسانی شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function toggleCustomerStatus() {
    if (!selectedCustomer || !selectedOrganization?.can_manage) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<CustomerCRMItem>(
        `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/status`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expected_version: selectedCustomer.version,
            is_active: !selectedCustomer.is_active,
          }),
        },
      );
      refreshCustomer(saved);
      setNotice({ tone: "success", text: saved.is_active ? "رکورد CRM بازیابی شد." : "رکورد CRM بایگانی شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function saveOwner() {
    if (!selectedCustomer || !selectedOrganization?.can_assign) return;
    setBusy(true);
    setNotice(null);
    try {
      const path = ownerId
        ? `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/assign`
        : `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/unassign`;
      const body = ownerId
        ? { expected_version: selectedCustomer.version, assigned_owner_user_id: ownerId }
        : { expected_version: selectedCustomer.version };
      const saved = await apiFetch<CustomerCRMItem>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      refreshCustomer(saved);
      setNotice({ tone: "success", text: ownerId ? "مسئول داخلی مشتری تعیین شد." : "تخصیص مسئول حذف شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function createTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization?.can_manage_tags || !newTagName.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      const tag = await apiFetch<CustomerTagItem>("/api/modules/customers/customer-tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ organization_id: selectedOrganization.id, name: newTagName.trim() }),
      });
      setTags((current) => [...current, tag].sort((a, b) => a.name.localeCompare(b.name, "fa")));
      setNewTagName("");
      setNotice({ tone: "success", text: "برچسب CRM ساخته شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function toggleTag(tag: CustomerTagItem) {
    if (!selectedCustomer || !selectedOrganization?.can_manage_tags) return;
    const attached = selectedCustomer.tags.some((item) => item.id === tag.id);
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<CustomerCRMItem>(
        `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/tags/${encodeURIComponent(tag.id)}`,
        { method: attached ? "DELETE" : "POST" },
      );
      refreshCustomer(saved);
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function loadNotes() {
    if (!selectedCustomer || !selectedOrganization?.can_read_notes) return;
    setBusy(true);
    setNotice(null);
    try {
      setNotes(
        await apiFetch<CustomerNoteItem[]>(
          `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/notes`,
        ),
      );
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCustomer || !selectedOrganization?.can_manage_notes || !noteBody.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      const note = await apiFetch<CustomerNoteItem>(
        `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/notes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: noteBody.trim() }),
        },
      );
      setNotes((current) => [note, ...current]);
      setNoteBody("");
      setNotice({ tone: "success", text: "یادداشت ثبت شد. محتوای یادداشت وارد Audit نمی‌شود." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function saveNote(note: CustomerNoteItem) {
    if (!selectedCustomer || !selectedOrganization?.can_manage_notes || !editingNoteBody.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<CustomerNoteItem>(
        `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/notes/${encodeURIComponent(note.id)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_version: note.version, body: editingNoteBody.trim() }),
        },
      );
      setNotes((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      setEditingNoteId("");
      setEditingNoteBody("");
      setNotice({ tone: "success", text: "یادداشت به‌روزرسانی شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function loadCommerceActivity() {
    if (!selectedCustomer || !selectedOrganization?.can_read_commerce_activity) return;
    setBusy(true);
    setNotice(null);
    try {
      setCommerceActivity(
        await apiFetch<CommerceActivityProjection>(
          `/api/modules/customers/customers/${encodeURIComponent(selectedCustomer.id)}/commerce-activity`,
        ),
      );
    } catch (error) {
      setCommerceActivity(null);
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <AsyncState label="در حال آماده‌سازی CRM مشتریان…" />;

  return (
    <section className="crm-view">
      <div className="search-title-row">
        <div>
          <span className="page-eyebrow">Customer Reference / CRM Foundation</span>
          <h1>مشتریان و CRM داخلی</h1>
          <p>
            این بخش فقط مرجع و متادیتای داخلی مشتری را نگه می‌دارد؛ هویت، ورود و رمز مشتری متعلق به فروشگاه مجازی است.
          </p>
        </div>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      <div className="panel-card crm-toolbar">
        <label>
          سازمان
          <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
            <option value="">انتخاب سازمان</option>
            {organizations.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
        <label>
          جستجوی محلی
          <input
            value={search}
            maxLength={100}
            placeholder="نام نمایشی یا شناسه Commerce"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="secondary-action compact-action"
          disabled={!organizationId || refreshing}
          onClick={() => organizationId && void loadOrganizationData(organizationId)}
        >
          {refreshing ? "در حال تازه‌سازی…" : "تازه‌سازی"}
        </button>
      </div>

      {selectedOrganization?.can_manage ? (
        <form className="panel-card crm-create-form" onSubmit={submitCustomer}>
          <h2>ثبت مرجع مشتری</h2>
          <div className="crm-form-grid">
            <label>
              Commerce Customer Ref
              <input value={createRef} maxLength={128} required onChange={(event) => setCreateRef(event.target.value)} />
            </label>
            <label>
              نام نمایشی داخلی
              <input value={createLabel} maxLength={200} required onChange={(event) => setCreateLabel(event.target.value)} />
            </label>
            <label>
              نوع
              <select value={createType} onChange={(event) => setCreateType(event.target.value as CustomerCRMType)}>
                {Object.entries(customerTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              وضعیت تجاری
              <select value={createStatus} onChange={(event) => setCreateStatus(event.target.value as CustomerCommercialStatus)}>
                {Object.entries(customerStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              منبع
              <select value={createSource} onChange={(event) => setCreateSource(event.target.value as CustomerCRMSource)}>
                {Object.entries(customerSourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          </div>
          <p className="muted-copy">ایجاد رکورد فقط پس از اعتبارسنجی شناسه در Commerce Integration API انجام می‌شود.</p>
          <button type="submit" className="primary-action" disabled={busy || !createRef.trim() || !createLabel.trim()}>
            ثبت در CRM
          </button>
        </form>
      ) : null}

      <div className="crm-layout">
        <div className="panel-card crm-customer-list">
          <div className="crm-section-head">
            <h2>مشتریان</h2>
            <span>{filteredCustomers.length.toLocaleString("fa-IR")}</span>
          </div>
          {filteredCustomers.length === 0 ? (
            <p className="muted-copy">رکوردی در محدوده دسترسی فعلی وجود ندارد.</p>
          ) : (
            <div className="crm-list-stack">
              {filteredCustomers.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`crm-customer-row ${selectedCustomerId === item.id ? "is-selected" : ""}`}
                  onClick={() => setSelectedCustomerId(item.id)}
                >
                  <strong>{item.display_label}</strong>
                  <span>{customerStatusLabels[item.commercial_status]} · {customerTypeLabels[item.customer_type]}</span>
                  <small>{item.commerce_customer_ref}</small>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="crm-detail-stack">
          {!selectedCustomer ? (
            <div className="panel-card empty-state">برای مشاهده جزئیات، یک مشتری را انتخاب کنید.</div>
          ) : (
            <>
              <div className="panel-card">
                <div className="crm-section-head">
                  <div>
                    <span className="page-eyebrow">Internal CRM Metadata</span>
                    <h2>{selectedCustomer.display_label}</h2>
                    <p className="muted-copy">{selectedCustomer.commerce_customer_ref}</p>
                  </div>
                  <span className={selectedCustomer.is_active ? "status-pill is-active" : "status-pill"}>
                    {selectedCustomer.is_active ? "فعال" : "بایگانی"}
                  </span>
                </div>

                {selectedOrganization?.can_manage ? (
                  <form className="crm-form-grid" onSubmit={submitCustomerEdit}>
                    <label>
                      نام نمایشی
                      <input value={editLabel} maxLength={200} required onChange={(event) => setEditLabel(event.target.value)} />
                    </label>
                    <label>
                      نوع
                      <select value={editType} onChange={(event) => setEditType(event.target.value as CustomerCRMType)}>
                        {Object.entries(customerTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label>
                      وضعیت تجاری
                      <select value={editStatus} onChange={(event) => setEditStatus(event.target.value as CustomerCommercialStatus)}>
                        {Object.entries(customerStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label>
                      منبع
                      <select value={editSource} onChange={(event) => setEditSource(event.target.value as CustomerCRMSource)}>
                        {Object.entries(customerSourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <div className="crm-inline-actions">
                      <button className="primary-action" type="submit" disabled={busy}>ذخیره تغییرات</button>
                      <button className="secondary-action" type="button" disabled={busy} onClick={() => void toggleCustomerStatus()}>
                        {selectedCustomer.is_active ? "بایگانی" : "بازیابی"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <p className="muted-copy">نسخه رکورد: {selectedCustomer.version.toLocaleString("fa-IR")}</p>
                )}
              </div>

              {selectedOrganization?.can_assign ? (
                <div className="panel-card">
                  <h2>مسئول داخلی</h2>
                  <div className="crm-inline-actions">
                    <select value={ownerId} onChange={(event) => setOwnerId(event.target.value)}>
                      <option value="">بدون مسئول</option>
                      {assignees.map((item) => (
                        <option key={item.id} value={item.id}>{item.display_name} — {item.email}</option>
                      ))}
                    </select>
                    <button type="button" className="primary-action" disabled={busy} onClick={() => void saveOwner()}>
                      ذخیره تخصیص
                    </button>
                  </div>
                  <p className="muted-copy">تخصیص مسئول هیچ مجوز دسترسی جدیدی ایجاد نمی‌کند.</p>
                </div>
              ) : null}

              <div className="panel-card">
                <div className="crm-section-head"><h2>برچسب‌ها</h2><span>{selectedCustomer.tags.length.toLocaleString("fa-IR")}</span></div>
                <div className="crm-tags">
                  {tags.map((tag) => {
                    const attached = selectedCustomer.tags.some((item) => item.id === tag.id);
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        className={`tag-chip ${attached ? "is-selected" : ""}`}
                        disabled={!selectedOrganization?.can_manage_tags || busy}
                        onClick={() => void toggleTag(tag)}
                      >
                        {tag.name}
                      </button>
                    );
                  })}
                </div>
                {selectedOrganization?.can_manage_tags ? (
                  <form className="crm-inline-actions" onSubmit={createTag}>
                    <input value={newTagName} maxLength={60} placeholder="برچسب جدید" onChange={(event) => setNewTagName(event.target.value)} />
                    <button className="secondary-action" type="submit" disabled={busy || !newTagName.trim()}>ساخت برچسب</button>
                  </form>
                ) : null}
              </div>

              {selectedOrganization?.can_read_notes ? (
                <div className="panel-card">
                  <div className="crm-section-head">
                    <h2>یادداشت‌های داخلی</h2>
                    <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => void loadNotes()}>
                      دریافت یادداشت‌ها
                    </button>
                  </div>
                  <AppNotice tone="info">اطلاعات کارت، CVV، رمز، OTP، کد ملی یا داده بانکی را در متن آزاد وارد نکنید. متن یادداشت عمداً وارد Audit نمی‌شود.</AppNotice>
                  {selectedOrganization.can_manage_notes ? (
                    <form onSubmit={addNote}>
                      <textarea value={noteBody} maxLength={4000} rows={3} placeholder="یادداشت داخلی…" onChange={(event) => setNoteBody(event.target.value)} />
                      <button type="submit" className="primary-action" disabled={busy || !noteBody.trim()}>ثبت یادداشت</button>
                    </form>
                  ) : null}
                  <div className="crm-note-stack">
                    {notes.map((note) => (
                      <article key={note.id} className="crm-note-card">
                        {editingNoteId === note.id ? (
                          <>
                            <textarea value={editingNoteBody} maxLength={4000} rows={3} onChange={(event) => setEditingNoteBody(event.target.value)} />
                            <div className="crm-inline-actions">
                              <button type="button" className="primary-action compact-action" disabled={busy} onClick={() => void saveNote(note)}>ذخیره</button>
                              <button type="button" className="secondary-action compact-action" onClick={() => setEditingNoteId("")}>انصراف</button>
                            </div>
                          </>
                        ) : (
                          <>
                            <p>{note.body}</p>
                            <small>{isoToPersian(note.updated_at)} · نسخه {note.version.toLocaleString("fa-IR")}</small>
                            {selectedOrganization.can_manage_notes ? (
                              <button
                                type="button"
                                className="secondary-action compact-action"
                                onClick={() => { setEditingNoteId(note.id); setEditingNoteBody(note.body); }}
                              >
                                ویرایش
                              </button>
                            ) : null}
                          </>
                        )}
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {selectedOrganization?.can_read_commerce_activity ? (
                <div className="panel-card">
                  <div className="crm-section-head">
                    <h2>فعالیت اخیر فروشگاه</h2>
                    <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => void loadCommerceActivity()}>
                      دریافت از Commerce
                    </button>
                  </div>
                  <p className="muted-copy">این داده مالکیت CRM نیست و مستقیماً از Integration Contract خوانده می‌شود.</p>
                  {commerceActivity ? (
                    commerceActivity.orders.length ? (
                      <div className="crm-list-stack">
                        {commerceActivity.orders.map((order) => (
                          <div key={order.external_order_ref} className="crm-note-card">
                            <strong>{order.external_order_ref}</strong>
                            <span>{order.status}</span>
                            <small>{isoToPersian(order.occurred_at)}</small>
                          </div>
                        ))}
                      </div>
                    ) : <p className="muted-copy">فعالیت سفارشی برای نمایش وجود ندارد.</p>
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
