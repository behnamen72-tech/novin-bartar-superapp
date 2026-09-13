"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  AccessAssignment,
  CurrentUser,
  OrganizationItem,
  PersonItem,
  PersonRelationshipItem,
} from "@/lib/core-types";
import {
  canManageOrganizationForPermission,
  canManagePersonGlobally,
  manageableOrganizationsForPermission,
  normalizedOptionalText,
} from "@/lib/people-user-management";

type Props = {
  people: PersonItem[];
  organizations: OrganizationItem[];
  assignments: AccessAssignment[];
  currentUser: CurrentUser;
  onPersonChanged: (person: PersonItem, created: boolean) => void;
};

type Editor =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; person: PersonItem }
  | { mode: "relationship"; person: PersonItem };

const relationshipOptions = [
  ["manager", "مدیر"],
  ["employee", "کارمند"],
  ["contractor", "پیمانکار"],
  ["customer_contact", "رابط مشتری"],
] as const;

function relationshipLabel(code: string): string {
  return relationshipOptions.find(([value]) => value === code)?.[1] ?? code;
}

function mutationErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Person not found.": "شخص موردنظر پیدا نشد یا در محدوده دسترسی شما نیست.",
    "Organization not found.": "سازمان موردنظر پیدا نشد یا قابل استفاده نیست.",
    "An active matching relationship already exists.": "این رابطه فعال از قبل برای شخص ثبت شده است.",
    "Deactivate access assignments rooted at this organization before deactivating the person's relationship.":
      "ابتدا دسترسی‌های فعال کاربر در این سازمان را غیرفعال کنید، سپس رابطه شخص را ببندید.",
    "Administrators cannot deactivate their own Person through this endpoint.":
      "برای جلوگیری از قطع دسترسی، Person متصل به حساب فعلی از این صفحه غیرفعال نمی‌شود.",
  };
  return known[error.detail] ?? error.detail ?? "عملیات انجام نشد.";
}

export function PeopleManagementView({ people, organizations, assignments, currentUser, onPersonChanged }: Props) {
  const [editor, setEditor] = useState<Editor>({ mode: "closed" });
  const [notice, setNotice] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [relationshipCode, setRelationshipCode] = useState("employee");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const manageableOrganizations = useMemo(
    () => manageableOrganizationsForPermission("people.manage", organizations, assignments),
    [organizations, assignments],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("fa");
    if (!needle) return people;
    return people.filter((person) => {
      const haystack = [
        person.first_name,
        person.last_name,
        person.email ?? "",
        person.phone ?? "",
        ...person.relationships.flatMap((relationship) => [
          relationship.organization_name,
          relationship.relationship_code,
        ]),
      ]
        .join(" ")
        .toLocaleLowerCase("fa");
      return haystack.includes(needle);
    });
  }, [people, query]);

  function resetForm() {
    setFirstName("");
    setLastName("");
    setEmail("");
    setPhone("");
    setOrganizationId(manageableOrganizations[0]?.id ?? "");
    setRelationshipCode("employee");
    setStartDate("");
    setEndDate("");
  }

  function openCreate() {
    resetForm();
    setNotice(null);
    setEditor({ mode: "create" });
  }

  function openEdit(person: PersonItem) {
    setFirstName(person.first_name);
    setLastName(person.last_name);
    setEmail(person.email ?? "");
    setPhone(person.phone ?? "");
    setNotice(null);
    setEditor({ mode: "edit", person });
  }

  function openRelationship(person: PersonItem) {
    setOrganizationId(manageableOrganizations[0]?.id ?? "");
    setRelationshipCode("employee");
    setStartDate("");
    setEndDate("");
    setNotice(null);
    setEditor({ mode: "relationship", person });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setNotice(null);
    try {
      if (editor.mode === "create") {
        const created = await apiFetch<PersonItem>("/api/core/people", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            organization_id: organizationId,
            relationship_code: relationshipCode.trim(),
            first_name: firstName.trim(),
            last_name: lastName.trim(),
            email: normalizedOptionalText(email),
            phone: normalizedOptionalText(phone),
            start_date: startDate || null,
            end_date: endDate || null,
          }),
        });
        onPersonChanged(created, true);
        setEditor({ mode: "closed" });
        setNotice({ tone: "success", text: "شخص جدید با موفقیت ثبت شد." });
      } else if (editor.mode === "edit") {
        const updated = await apiFetch<PersonItem>(
          `/api/core/people/${encodeURIComponent(editor.person.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              first_name: firstName.trim(),
              last_name: lastName.trim(),
              email: normalizedOptionalText(email),
              phone: normalizedOptionalText(phone),
            }),
          },
        );
        onPersonChanged(updated, false);
        setEditor({ mode: "closed" });
        setNotice({ tone: "success", text: "اطلاعات شخص به‌روزرسانی شد." });
      } else if (editor.mode === "relationship") {
        const relationship = await apiFetch<PersonRelationshipItem>(
          `/api/core/people/${encodeURIComponent(editor.person.id)}/relationships`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              organization_id: organizationId,
              relationship_code: relationshipCode.trim(),
              start_date: startDate || null,
              end_date: endDate || null,
            }),
          },
        );
        onPersonChanged(
          { ...editor.person, relationships: [...editor.person.relationships, relationship] },
          false,
        );
        setEditor({ mode: "closed" });
        setNotice({ tone: "success", text: "رابطه سازمانی جدید ثبت شد." });
      }
    } catch (error) {
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function togglePersonStatus(person: PersonItem) {
    const nextActive = !person.is_active;
    if (!window.confirm(nextActive ? `شخص «${person.first_name} ${person.last_name}» فعال شود؟` : `شخص «${person.first_name} ${person.last_name}» غیرفعال شود؟`)) return;
    setBusyKey(`person:${person.id}`);
    setNotice(null);
    try {
      const updated = await apiFetch<PersonItem>(
        `/api/core/people/${encodeURIComponent(person.id)}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: nextActive }),
        },
      );
      onPersonChanged(updated, false);
      setNotice({ tone: "success", text: nextActive ? "شخص فعال شد." : "شخص غیرفعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setBusyKey(null);
    }
  }

  async function toggleRelationship(person: PersonItem, relationship: PersonRelationshipItem) {
    const nextActive = !relationship.is_active;
    if (!window.confirm(nextActive ? "این رابطه سازمانی دوباره فعال شود؟" : "این رابطه سازمانی غیرفعال شود؟")) return;
    setBusyKey(`relationship:${relationship.id}`);
    setNotice(null);
    try {
      const updatedRelationship = await apiFetch<PersonRelationshipItem>(
        `/api/core/people/${encodeURIComponent(person.id)}/relationships/${encodeURIComponent(relationship.id)}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: nextActive }),
        },
      );
      onPersonChanged(
        {
          ...person,
          relationships: person.relationships.map((item) =>
            item.id === updatedRelationship.id ? updatedRelationship : item,
          ),
        },
        false,
      );
      setNotice({ tone: "success", text: nextActive ? "رابطه فعال شد." : "رابطه غیرفعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <section className="page-section people-management">
      <div className="page-title management-page-title">
        <div>
          <span>People Core</span>
          <h1>اشخاص</h1>
          <p>مدیریت اطلاعات شخص، وضعیت و روابط سازمانی. تغییر اطلاعات مشترک Person فقط وقتی ممکن است که Backend تمام Scopeهای مرتبط را مجاز بداند.</p>
        </div>
        <div className="management-title-actions">
          <div className="count-box"><span>قابل مشاهده</span><strong>{people.length.toLocaleString("fa-IR")}</strong></div>
          {manageableOrganizations.length > 0 ? <button type="button" className="primary-action-button" onClick={openCreate}>+ شخص جدید</button> : null}
        </div>
      </div>

      <div className="management-toolbar">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جستجو در نام، ایمیل، تلفن یا سازمان…" />
        <span>{filtered.length.toLocaleString("fa-IR")} نتیجه</span>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}
      {manageableOrganizations.length === 0 ? <AppNotice tone="info">در Scope فعلی مجوز people.manage برای ایجاد شخص جدید وجود ندارد؛ داده‌های مجاز همچنان قابل مشاهده‌اند.</AppNotice> : null}

      <div className="people-management-grid">
        {filtered.map((person) => {
          const globallyManageable = canManagePersonGlobally(person, "people.manage", organizations, assignments);
          const ownPerson = person.id === currentUser.person_id;
          return (
            <article className={`entity-card management-entity-card ${person.is_active ? "" : "is-muted"}`} key={person.id}>
              <div className="entity-card-head">
                <div className="person-avatar">{person.first_name.slice(0, 1)}{person.last_name.slice(0, 1)}</div>
                <div className="entity-card-identity">
                  <strong>{person.first_name} {person.last_name}</strong>
                  <span>{person.email ?? "ایمیل ثبت نشده"}</span>
                  <small dir="ltr">{person.phone ?? "—"}</small>
                </div>
                <span className={`status-badge ${person.is_active ? "is-active" : "is-inactive"}`}>{person.is_active ? "فعال" : "غیرفعال"}</span>
              </div>

              <div className="relationship-management-list">
                {person.relationships.map((relationship) => {
                  const relManageable = canManageOrganizationForPermission(
                    relationship.organization_id,
                    "people.manage",
                    organizations,
                    assignments,
                  );
                  return (
                    <div className={`relationship-management-row ${relationship.is_active ? "" : "is-muted"}`} key={relationship.id}>
                      <div>
                        <strong>{relationshipLabel(relationship.relationship_code)}</strong>
                        <span>{relationship.organization_name}</span>
                        {(relationship.start_date || relationship.end_date) ? <small>{relationship.start_date ?? "—"} تا {relationship.end_date ?? "—"}</small> : null}
                      </div>
                      <span className={`status-badge ${relationship.is_active ? "is-active" : "is-inactive"}`}>{relationship.is_active ? "فعال" : "غیرفعال"}</span>
                      {relManageable ? (
                        <button type="button" className={`status-action-button ${relationship.is_active ? "danger" : "success"}`} disabled={busyKey === `relationship:${relationship.id}`} onClick={() => void toggleRelationship(person, relationship)}>
                          {busyKey === `relationship:${relationship.id}` ? "در حال ثبت…" : relationship.is_active ? "بستن رابطه" : "فعال‌سازی"}
                        </button>
                      ) : null}
                    </div>
                  );
                })}
                {person.relationships.length === 0 ? <div className="empty-state compact-empty">رابطه سازمانی قابل مشاهده‌ای وجود ندارد.</div> : null}
              </div>

              <div className="management-card-actions">
                {manageableOrganizations.length > 0 ? <button type="button" className="secondary-action-button" onClick={() => openRelationship(person)}>+ رابطه سازمانی</button> : null}
                {globallyManageable ? (
                  <>
                    <button type="button" className="secondary-action-button" onClick={() => openEdit(person)}>ویرایش</button>
                    <button type="button" className={`status-action-button ${person.is_active ? "danger" : "success"}`} disabled={busyKey === `person:${person.id}` || (ownPerson && person.is_active)} onClick={() => void togglePersonStatus(person)} title={ownPerson && person.is_active ? "Person حساب فعلی از این صفحه غیرفعال نمی‌شود." : undefined}>
                      {busyKey === `person:${person.id}` ? "در حال ثبت…" : person.is_active ? "غیرفعال" : "فعال‌سازی"}
                    </button>
                  </>
                ) : <span className="read-only-label">ویرایش اطلاعات مشترک در Scope فعلی مجاز نیست</span>}
              </div>
            </article>
          );
        })}
        {filtered.length === 0 ? <div className="empty-state">شخصی با این فیلتر پیدا نشد.</div> : null}
      </div>

      {editor.mode !== "closed" ? (
        <div className="management-dialog-layer" role="presentation">
          <button type="button" className="management-dialog-backdrop" aria-label="بستن پنجره" onClick={() => !saving && setEditor({ mode: "closed" })} />
          <div className="management-dialog" role="dialog" aria-modal="true" aria-labelledby="people-editor-title">
            <div className="management-dialog-head">
              <div><span>People Management</span><h2 id="people-editor-title">{editor.mode === "create" ? "ثبت شخص جدید" : editor.mode === "edit" ? "ویرایش شخص" : "افزودن رابطه سازمانی"}</h2></div>
              <button type="button" onClick={() => setEditor({ mode: "closed" })} disabled={saving}>بستن</button>
            </div>
            <form className="management-form" onSubmit={(event) => void submit(event)}>
              {editor.mode !== "relationship" ? (
                <>
                  <label><span>نام</span><input value={firstName} onChange={(event) => setFirstName(event.target.value)} required maxLength={100} autoFocus /></label>
                  <label><span>نام خانوادگی</span><input value={lastName} onChange={(event) => setLastName(event.target.value)} required maxLength={100} /></label>
                  <label><span>ایمیل</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} maxLength={320} dir="ltr" /></label>
                  <label><span>تلفن</span><input value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={50} dir="ltr" /></label>
                </>
              ) : null}

              {editor.mode === "create" || editor.mode === "relationship" ? (
                <>
                  <label><span>سازمان</span><select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} required>{manageableOrganizations.map((organization) => <option value={organization.id} key={organization.id}>{organization.name}</option>)}</select></label>
                  <label><span>نوع رابطه</span><select value={relationshipCode} onChange={(event) => setRelationshipCode(event.target.value)}>{relationshipOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                  <div className="management-form-columns">
                    <label><span>شروع رابطه</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
                    <label><span>پایان رابطه</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} min={startDate || undefined} /></label>
                  </div>
                </>
              ) : null}

              {editor.mode === "edit" ? <div className="management-form-note">Person یک رکورد مشترک بین سازمان‌هاست؛ Backend قبل از ذخیره کنترل می‌کند که شما روی تمام روابط سازمانی لازم مجوز people.manage داشته باشید.</div> : null}
              <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setEditor({ mode: "closed" })} disabled={saving}>انصراف</button><button type="submit" className="primary-action-button" disabled={saving || ((editor.mode === "create" || editor.mode === "relationship") && !organizationId)}>{saving ? "در حال ذخیره…" : "ذخیره"}</button></div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
