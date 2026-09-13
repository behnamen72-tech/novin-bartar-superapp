"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  SupplierAssigneeOption,
  SupplierCommercialStatus,
  SupplierExternalReferenceItem,
  SupplierExternalSystem,
  SupplierItem,
  SupplierKind,
  SupplierNoteItem,
  SupplierOrganizationCapability,
  SupplierRepresentativeItem,
  SupplierSource,
  SupplierTagItem,
} from "@/lib/core-types";

const kindLabels: Record<SupplierKind, string> = {
  company: "شرکت",
  individual: "شخص حقیقی",
  other: "سایر",
};
const statusLabels: Record<SupplierCommercialStatus, string> = {
  prospect: "در حال بررسی",
  active: "فعال",
  inactive: "غیرفعال",
  suspended: "تعلیق همکاری",
  archived: "آرشیو",
};
const sourceLabels: Record<SupplierSource, string> = {
  manual: "ثبت دستی",
  import: "ورود اطلاعات",
  accounting_reference: "مرجع حسابداری",
  procurement_reference: "مرجع خرید",
  other: "سایر",
};
const externalSystemLabels: Record<SupplierExternalSystem, string> = {
  accounting: "حسابداری",
  erp: "ERP",
  procurement: "خرید",
  other: "سایر",
};

function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Supplier not found.": "تأمین‌کننده پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Supplier representative not found.": "نماینده پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Supplier note not found.": "یادداشت پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Supplier tag not found.": "برچسب پیدا نشد یا متعلق به این سازمان نیست.",
    "Supplier external reference not found.": "مرجع خارجی پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Supplier already has an active primary representative.": "این تأمین‌کننده از قبل یک نماینده اصلی فعال دارد.",
    "External reference already exists in this organization and system.": "این شناسه خارجی قبلاً در همین سازمان و سیستم ثبت شده است.",
    "Supplier was modified by another request.": "این رکورد هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی کنید.",
    "Supplier representative was modified by another request.": "این نماینده هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی کنید.",
    "Supplier note was modified by another request.": "این یادداشت هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی کنید.",
    "Assigned owner is not an active internal user.": "مسئول انتخاب‌شده کاربر داخلی فعال نیست.",
    "Assigned owner cannot access this organization supplier context.": "مسئول انتخاب‌شده به حوزه تأمین‌کنندگان این سازمان دسترسی ندارد.",
  };
  return known[error.detail] ?? error.detail ?? "عملیات انجام نشد.";
}

function dateLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function hasSupplierCapability(item: SupplierOrganizationCapability): boolean {
  return Object.entries(item).some(([key, value]) => key.startsWith("can_") && value === true);
}

export function SupplierFoundationView() {
  const [organizations, setOrganizations] = useState<SupplierOrganizationCapability[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [suppliers, setSuppliers] = useState<SupplierItem[]>([]);
  const [tags, setTags] = useState<SupplierTagItem[]>([]);
  const [assignees, setAssignees] = useState<SupplierAssigneeOption[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [representatives, setRepresentatives] = useState<SupplierRepresentativeItem[]>([]);
  const [notes, setNotes] = useState<SupplierNoteItem[]>([]);
  const [externalReferences, setExternalReferences] = useState<SupplierExternalReferenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [search, setSearch] = useState("");

  const [createName, setCreateName] = useState("");
  const [createKind, setCreateKind] = useState<SupplierKind>("company");
  const [createStatus, setCreateStatus] = useState<SupplierCommercialStatus>("prospect");
  const [createSource, setCreateSource] = useState<SupplierSource>("manual");
  const [editName, setEditName] = useState("");
  const [editKind, setEditKind] = useState<SupplierKind>("company");
  const [editStatus, setEditStatus] = useState<SupplierCommercialStatus>("prospect");
  const [editSource, setEditSource] = useState<SupplierSource>("manual");
  const [ownerId, setOwnerId] = useState("");

  const [repName, setRepName] = useState("");
  const [repTitle, setRepTitle] = useState("");
  const [repPhone, setRepPhone] = useState("");
  const [repEmail, setRepEmail] = useState("");
  const [repPrimary, setRepPrimary] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [externalSystem, setExternalSystem] = useState<SupplierExternalSystem>("accounting");
  const [externalId, setExternalId] = useState("");

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === organizationId),
    [organizationId, organizations],
  );
  const selectedSupplier = useMemo(
    () => suppliers.find((item) => item.id === selectedSupplierId),
    [selectedSupplierId, suppliers],
  );
  const filteredSuppliers = useMemo(() => {
    const q = search.trim().toLocaleLowerCase("fa");
    if (!q) return suppliers;
    return suppliers.filter((item) => item.display_name.toLocaleLowerCase("fa").includes(q));
  }, [search, suppliers]);

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const items = await apiFetch<SupplierOrganizationCapability[]>("/api/modules/suppliers/organizations");
      setOrganizations(items);
      setOrganizationId((current) => {
        if (current && items.some((item) => item.id === current && hasSupplierCapability(item))) return current;
        return items.find(hasSupplierCapability)?.id ?? "";
      });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrganizationData = useCallback(async (targetId: string) => {
    const capability = organizations.find((item) => item.id === targetId);
    if (!capability) return;
    setRefreshing(true);
    setSelectedSupplierId("");
    setRepresentatives([]);
    setNotes([]);
    setExternalReferences([]);
    try {
      const work: Promise<void>[] = [];
      if (capability.can_read) {
        work.push(
          apiFetch<SupplierItem[]>(`/api/modules/suppliers/suppliers?organization_id=${encodeURIComponent(targetId)}&include_inactive=${capability.can_manage ? "true" : "false"}&limit=200`).then(setSuppliers),
        );
      } else setSuppliers([]);
      if (capability.can_read || capability.can_manage_tag_catalog || capability.can_assign_tags) {
        work.push(apiFetch<SupplierTagItem[]>(`/api/modules/suppliers/tags/catalog?organization_id=${encodeURIComponent(targetId)}`).then(setTags));
      } else setTags([]);
      if (capability.can_assign) {
        work.push(apiFetch<SupplierAssigneeOption[]>(`/api/modules/suppliers/assignees?organization_id=${encodeURIComponent(targetId)}`).then(setAssignees));
      } else setAssignees([]);
      await Promise.all(work);
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setRefreshing(false);
    }
  }, [organizations]);

  const loadSupplierDetails = useCallback(async (supplierId: string) => {
    const capability = selectedOrganization;
    if (!capability || !supplierId) return;
    const work: Promise<void>[] = [];
    if (capability.can_read && capability.can_read_representatives) {
      work.push(apiFetch<SupplierRepresentativeItem[]>(`/api/modules/suppliers/suppliers/${encodeURIComponent(supplierId)}/representatives?include_inactive=true`).then(setRepresentatives));
    } else setRepresentatives([]);
    if (capability.can_read && capability.can_read_notes) {
      work.push(apiFetch<SupplierNoteItem[]>(`/api/modules/suppliers/suppliers/${encodeURIComponent(supplierId)}/notes`).then(setNotes));
    } else setNotes([]);
    if (capability.can_read && capability.can_read_external_references) {
      work.push(apiFetch<SupplierExternalReferenceItem[]>(`/api/modules/suppliers/suppliers/${encodeURIComponent(supplierId)}/external-references`).then(setExternalReferences));
    } else setExternalReferences([]);
    try {
      await Promise.all(work);
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    }
  }, [selectedOrganization]);

  useEffect(() => { void loadOrganizations(); }, [loadOrganizations]);
  useEffect(() => { if (organizationId) void loadOrganizationData(organizationId); }, [loadOrganizationData, organizationId]);
  useEffect(() => {
    if (!selectedSupplier) return;
    setEditName(selectedSupplier.display_name);
    setEditKind(selectedSupplier.supplier_kind);
    setEditStatus(selectedSupplier.commercial_status);
    setEditSource(selectedSupplier.source);
    setOwnerId(selectedSupplier.assigned_owner_user_id ?? "");
    void loadSupplierDetails(selectedSupplier.id);
  }, [loadSupplierDetails, selectedSupplier]);

  const replaceSupplier = useCallback((saved: SupplierItem) => {
    setSuppliers((current) => current.map((item) => (item.id === saved.id ? saved : item)));
  }, []);

  async function submitSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization?.can_manage) return;
    setBusy(true); setNotice(null);
    try {
      const saved = await apiFetch<SupplierItem>("/api/modules/suppliers/suppliers", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ organization_id: selectedOrganization.id, display_name: createName.trim(), supplier_kind: createKind, commercial_status: createStatus, source: createSource }),
      });
      setSuppliers((current) => [saved, ...current]);
      setSelectedSupplierId(saved.id); setCreateName("");
      setNotice({ tone: "success", text: "تأمین‌کننده ثبت شد؛ این رکورد هویت داخلی کاربر/سازمان ایجاد نمی‌کند." });
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSupplier || !selectedOrganization?.can_manage) return;
    setBusy(true); setNotice(null);
    try {
      const saved = await apiFetch<SupplierItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_version: selectedSupplier.version, display_name: editName.trim(), supplier_kind: editKind, commercial_status: editStatus, source: editSource }),
      });
      replaceSupplier(saved); setNotice({ tone: "success", text: "اطلاعات تأمین‌کننده به‌روزرسانی شد." });
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function toggleLifecycle() {
    if (!selectedSupplier || !selectedOrganization?.can_manage) return;
    setBusy(true);
    try {
      const saved = await apiFetch<SupplierItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/status`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_version: selectedSupplier.version, is_active: !selectedSupplier.is_active }),
      });
      replaceSupplier(saved); setNotice({ tone: "success", text: saved.is_active ? "تأمین‌کننده بازیابی شد." : "تأمین‌کننده آرشیو شد." });
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function saveOwner() {
    if (!selectedSupplier || !selectedOrganization?.can_assign) return;
    setBusy(true);
    try {
      const path = ownerId ? "assign" : "unassign";
      const payload = ownerId ? { expected_version: selectedSupplier.version, assigned_owner_user_id: ownerId } : { expected_version: selectedSupplier.version };
      const saved = await apiFetch<SupplierItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/${path}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      replaceSupplier(saved); setNotice({ tone: "success", text: "مسئول داخلی به‌روزرسانی شد؛ این تخصیص Permission ایجاد نمی‌کند." });
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function submitRepresentative(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSupplier || !selectedOrganization?.can_manage_representatives) return;
    setBusy(true);
    try {
      const saved = await apiFetch<SupplierRepresentativeItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/representatives`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: repName.trim(), job_title: repTitle.trim() || null, phone: repPhone.trim() || null, email: repEmail.trim() || null, is_primary: repPrimary }),
      });
      setRepresentatives((current) => [saved, ...current]);
      setRepName(""); setRepTitle(""); setRepPhone(""); setRepEmail(""); setRepPrimary(false);
      setNotice({ tone: "success", text: "نماینده ثبت شد. اطلاعات تماس براساس Permission مستقل نمایش داده می‌شود." });
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function patchRepresentative(item: SupplierRepresentativeItem, changes: Partial<Pick<SupplierRepresentativeItem, "is_primary" | "is_active">>) {
    if (!selectedSupplier || !selectedOrganization?.can_manage_representatives) return;
    setBusy(true);
    try {
      const saved = await apiFetch<SupplierRepresentativeItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/representatives/${encodeURIComponent(item.id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: item.version, ...changes }),
      });
      setRepresentatives((current) => current.map((candidate) => candidate.id === saved.id ? saved : candidate));
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function createTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization?.can_manage_tag_catalog) return;
    setBusy(true);
    try {
      const tag = await apiFetch<SupplierTagItem>("/api/modules/suppliers/tags/catalog", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ organization_id: selectedOrganization.id, name: newTagName.trim() }),
      });
      setTags((current) => [...current, tag]); setNewTagName("");
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function toggleTag(tag: SupplierTagItem) {
    if (!selectedSupplier || !selectedOrganization?.can_assign_tags) return;
    const attached = selectedSupplier.tags.some((item) => item.id === tag.id);
    setBusy(true);
    try {
      const saved = await apiFetch<SupplierItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/tags/${encodeURIComponent(tag.id)}`, { method: attached ? "DELETE" : "POST" });
      replaceSupplier(saved);
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function createNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSupplier || !selectedOrganization?.can_manage_notes) return;
    setBusy(true);
    try {
      const saved = await apiFetch<SupplierNoteItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/notes`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body: noteBody.trim() }),
      });
      setNotes((current) => [saved, ...current]); setNoteBody("");
      setNotice({ tone: "success", text: "یادداشت ثبت شد. متن یادداشت وارد Audit payload نمی‌شود." });
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function createExternalReference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSupplier || !selectedOrganization?.can_manage_external_references) return;
    setBusy(true);
    try {
      const saved = await apiFetch<SupplierExternalReferenceItem>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/external-references`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ system: externalSystem, external_id: externalId }),
      });
      setExternalReferences((current) => [...current, saved]); setExternalId("");
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  async function removeExternalReference(item: SupplierExternalReferenceItem) {
    if (!selectedSupplier || !selectedOrganization?.can_manage_external_references) return;
    setBusy(true);
    try {
      await apiFetch<void>(`/api/modules/suppliers/suppliers/${encodeURIComponent(selectedSupplier.id)}/external-references/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      setExternalReferences((current) => current.filter((candidate) => candidate.id !== item.id));
    } catch (error) { setNotice({ tone: "error", text: errorText(error) }); } finally { setBusy(false); }
  }

  if (loading) return <AsyncState title="در حال آماده‌سازی تأمین‌کنندگان..." />;

  return (
    <section className="crm-view" dir="rtl">
      <div className="search-title-row">
        <div><p className="page-eyebrow">Suppliers Foundation · D3</p><h1>تأمین‌کنندگان و ویزیتورها</h1></div>
        <button className="secondary-action" type="button" onClick={() => void loadOrganizations()} disabled={refreshing}>تازه‌سازی</button>
      </div>
      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      <div className="panel-card crm-toolbar">
        <label>سازمان<select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>{organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>جستجو<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="نام تأمین‌کننده" /></label>
        <p className="muted-copy">Supplier یک هویت عملیاتی Back-office است؛ نه User/Person، نه حسابداری و نه موجودی.</p>
      </div>

      <div className="crm-layout">
        <div className="crm-list-stack">
          {selectedOrganization?.can_manage ? (
            <form className="panel-card crm-create-form" onSubmit={submitSupplier}>
              <div className="crm-section-head"><div><p className="page-eyebrow">New Supplier</p><h2>ثبت تأمین‌کننده</h2></div></div>
              <label>نام<input value={createName} onChange={(e) => setCreateName(e.target.value)} maxLength={200} required /></label>
              <div className="crm-form-grid">
                <label>نوع<select value={createKind} onChange={(e) => setCreateKind(e.target.value as SupplierKind)}>{Object.entries(kindLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                <label>وضعیت<select value={createStatus} onChange={(e) => setCreateStatus(e.target.value as SupplierCommercialStatus)}>{Object.entries(statusLabels).filter(([k]) => k !== "archived").map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                <label>منبع<select value={createSource} onChange={(e) => setCreateSource(e.target.value as SupplierSource)}>{Object.entries(sourceLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
              </div>
              <button className="primary-action" disabled={busy || !createName.trim()}>ثبت</button>
            </form>
          ) : null}

          <div className="panel-card crm-customer-list">
            <div className="crm-section-head"><div><p className="page-eyebrow">Supplier Registry</p><h2>فهرست تأمین‌کنندگان</h2></div><span>{filteredSuppliers.length}</span></div>
            {filteredSuppliers.length ? filteredSuppliers.map((item) => (
              <button className="secondary-action" key={item.id} type="button" onClick={() => setSelectedSupplierId(item.id)}>
                <strong>{item.display_name}</strong> · {kindLabels[item.supplier_kind]} · {statusLabels[item.commercial_status]}
              </button>
            )) : <p className="muted-copy">رکوردی برای نمایش وجود ندارد.</p>}
          </div>
        </div>

        <div className="crm-detail-stack">
          {!selectedSupplier ? <div className="panel-card empty-state"><h2>یک تأمین‌کننده را انتخاب کنید</h2><p>جزئیات رابطه عملیاتی، نمایندگان، Tag، یادداشت و External Reference اینجا نمایش داده می‌شود.</p></div> : (
            <>
              <form className="panel-card" onSubmit={submitEdit}>
                <div className="crm-section-head"><div><p className="page-eyebrow">Supplier Detail</p><h2>{selectedSupplier.display_name}</h2></div><span>v{selectedSupplier.version}</span></div>
                <div className="crm-form-grid">
                  <label>نام<input value={editName} onChange={(e) => setEditName(e.target.value)} disabled={!selectedOrganization?.can_manage} /></label>
                  <label>نوع<select value={editKind} onChange={(e) => setEditKind(e.target.value as SupplierKind)} disabled={!selectedOrganization?.can_manage}>{Object.entries(kindLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                  <label>وضعیت<select value={editStatus} onChange={(e) => setEditStatus(e.target.value as SupplierCommercialStatus)} disabled={!selectedOrganization?.can_manage}>{Object.entries(statusLabels).filter(([k]) => k !== "archived").map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                  <label>منبع<select value={editSource} onChange={(e) => setEditSource(e.target.value as SupplierSource)} disabled={!selectedOrganization?.can_manage}>{Object.entries(sourceLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                </div>
                <div className="crm-inline-actions">
                  {selectedOrganization?.can_manage ? <button className="primary-action compact-action" disabled={busy}>ذخیره</button> : null}
                  {selectedOrganization?.can_manage ? <button className="secondary-action compact-action" type="button" onClick={() => void toggleLifecycle()} disabled={busy}>{selectedSupplier.is_active ? "آرشیو" : "بازیابی"}</button> : null}
                </div>
              </form>

              {selectedOrganization?.can_assign ? <div className="panel-card"><div className="crm-section-head"><h3>مسئول داخلی</h3></div><div className="crm-inline-actions"><select value={ownerId} onChange={(e) => setOwnerId(e.target.value)}><option value="">بدون مسئول</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name} · {item.email}</option>)}</select><button className="secondary-action compact-action" type="button" onClick={() => void saveOwner()} disabled={busy}>ثبت مسئول</button></div><p className="muted-copy">Assignment هیچ Authorization جدیدی ایجاد نمی‌کند.</p></div> : null}

              {(selectedOrganization?.can_read_representatives || selectedOrganization?.can_manage_representatives) ? <div className="panel-card">
                <div className="crm-section-head"><div><p className="page-eyebrow">Representatives</p><h3>ویزیتورها / نمایندگان</h3></div></div>
                {selectedOrganization?.can_manage_representatives ? <form className="crm-form-grid" onSubmit={submitRepresentative}><label>نام<input value={repName} onChange={(e) => setRepName(e.target.value)} required /></label><label>عنوان<input value={repTitle} onChange={(e) => setRepTitle(e.target.value)} /></label><label>تلفن<input value={repPhone} onChange={(e) => setRepPhone(e.target.value)} /></label><label>ایمیل<input value={repEmail} onChange={(e) => setRepEmail(e.target.value)} /></label><label><input type="checkbox" checked={repPrimary} onChange={(e) => setRepPrimary(e.target.checked)} /> نماینده اصلی</label><button className="primary-action compact-action" disabled={busy}>افزودن</button></form> : null}
                <div className="crm-list-stack">{representatives.map((item) => <div className="crm-note-card" key={item.id}><strong>{item.display_name}{item.is_primary ? " · اصلی" : ""}</strong><p>{item.job_title ?? "بدون عنوان"}</p><p>{item.phone ?? "—"} · {item.email ?? "—"}{item.contact_masked ? " · اطلاعات تماس Mask شده" : ""}</p>{selectedOrganization?.can_manage_representatives ? <div className="crm-inline-actions"><button type="button" className="secondary-action compact-action" onClick={() => void patchRepresentative(item, { is_primary: !item.is_primary })} disabled={busy}>{item.is_primary ? "لغو اصلی" : "اصلی کردن"}</button><button type="button" className="secondary-action compact-action" onClick={() => void patchRepresentative(item, { is_active: !item.is_active })} disabled={busy}>{item.is_active ? "غیرفعال" : "فعال"}</button></div> : null}</div>)}</div>
              </div> : null}

              {(selectedOrganization?.can_manage_tag_catalog || selectedOrganization?.can_assign_tags || selectedOrganization?.can_read) ? <div className="panel-card"><div className="crm-section-head"><h3>برچسب‌ها</h3></div>{selectedOrganization?.can_manage_tag_catalog ? <form className="crm-inline-actions" onSubmit={createTag}><input value={newTagName} onChange={(e) => setNewTagName(e.target.value)} maxLength={60} placeholder="برچسب جدید" /><button className="secondary-action compact-action" disabled={busy}>ساخت در کاتالوگ</button></form> : null}<div className="crm-tags">{tags.map((tag) => { const attached = selectedSupplier.tags.some((item) => item.id === tag.id); return <button key={tag.id} type="button" className="secondary-action compact-action" onClick={() => void toggleTag(tag)} disabled={!selectedOrganization?.can_assign_tags || busy}>{attached ? "✓ " : "+ "}{tag.name}</button>; })}</div><p className="muted-copy">ساخت Tag و اختصاص Tag دو Permission مستقل دارند.</p></div> : null}

              {(selectedOrganization?.can_read_notes || selectedOrganization?.can_manage_notes) ? <div className="panel-card"><div className="crm-section-head"><h3>یادداشت‌های داخلی</h3></div>{selectedOrganization?.can_manage_notes ? <form onSubmit={createNote}><textarea value={noteBody} onChange={(e) => setNoteBody(e.target.value)} maxLength={4000} placeholder="اطلاعات حساس مالی/رمز/کارت وارد نکنید." /><button className="primary-action compact-action" disabled={busy || !noteBody.trim()}>ثبت یادداشت</button></form> : null}<div className="crm-note-stack">{notes.map((note) => <div className="crm-note-card" key={note.id}><p>{note.body}</p><small>{dateLabel(note.updated_at)} · v{note.version}</small></div>)}</div></div> : null}

              {(selectedOrganization?.can_read_external_references || selectedOrganization?.can_manage_external_references) ? <div className="panel-card"><div className="crm-section-head"><h3>شناسه‌های سیستم‌های خارجی</h3></div>{selectedOrganization?.can_manage_external_references ? <form className="crm-form-grid" onSubmit={createExternalReference}><label>سیستم<select value={externalSystem} onChange={(e) => setExternalSystem(e.target.value as SupplierExternalSystem)}>{Object.entries(externalSystemLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label><label>شناسه<input value={externalId} onChange={(e) => setExternalId(e.target.value)} maxLength={128} required /></label><button className="primary-action compact-action" disabled={busy}>ثبت مرجع</button></form> : null}<div className="crm-list-stack">{externalReferences.map((item) => <div className="crm-note-card" key={item.id}><strong>{externalSystemLabels[item.system]}</strong><p dir="ltr">{item.external_id}</p>{selectedOrganization?.can_manage_external_references ? <button className="secondary-action compact-action" type="button" onClick={() => void removeExternalReference(item)} disabled={busy}>حذف</button> : null}</div>)}</div><p className="muted-copy">External ID فقط NFKC+trim می‌شود و case آن حفظ می‌شود؛ اتصال مستقیم دیتابیس ممنوع است.</p></div> : null}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
