"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import {
  hrEmploymentTypeLabels,
  hrPositionLabel,
  hrScopeLabels,
  normalizeHrCode,
} from "@/lib/hr-management";
import type {
  HREmploymentItem,
  HREmploymentType,
  HRJobProfileItem,
  HROrganizationCapability,
  HRPersonOption,
  HRPositionItem,
  ScopeMode,
} from "@/lib/core-types";

type Tab = "profiles" | "positions" | "employments";
type Editor =
  | { type: "closed" }
  | { type: "profile"; mode: "create" | "edit"; item?: HRJobProfileItem }
  | { type: "position"; mode: "create" | "edit"; item?: HRPositionItem }
  | { type: "employment"; mode: "create" | "edit"; item?: HREmploymentItem };

function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Job profile not found.": "عنوان شغلی پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Position not found.": "پست سازمانی پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Employment record not found.": "رکورد همکاری پیدا نشد یا خارج از محدوده دسترسی شماست.",
    "Job profile code already exists in this organization.": "این کد عنوان شغلی در سازمان انتخاب‌شده تکراری است.",
    "Position code already exists in this organization.": "این کد پست سازمانی در سازمان انتخاب‌شده تکراری است.",
    "Employment number already exists in this organization.": "شماره پرسنلی در این سازمان تکراری است.",
    "Person already has an active employment in this organization.": "برای این شخص در این سازمان یک همکاری فعال وجود دارد.",
    "Position already has an active employment.": "این پست سازمانی در حال حاضر اشغال است.",
    "Person must have an active relationship with the organization before an employment record can be created.":
      "شخص باید ابتدا در بخش اشخاص، یک ارتباط فعال با این سازمان داشته باشد.",
    "Deactivate active positions using this job profile first.":
      "ابتدا پست‌های فعال وابسته به این عنوان شغلی را غیرفعال کنید.",
    "Deactivate descendant positions using this profile before narrowing its scope.":
      "قبل از محدودکردن دامنه، پست‌های فعال زیرمجموعه که از این عنوان استفاده می‌کنند باید غیرفعال شوند.",
    "End the active employment occupying this position first.":
      "ابتدا همکاری فعالِ مستقر در این پست را پایان دهید.",
    "Reassign active child positions before deactivating this position.":
      "قبل از غیرفعال‌کردن، پست‌های زیرمجموعه را به سرپرست دیگری متصل کنید.",
    "Position reporting hierarchy cannot contain a cycle.": "چرخه در ساختار گزارش‌دهی پست‌ها مجاز نیست.",
  };
  return known[error.detail] ?? error.detail ?? "عملیات انجام نشد.";
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function HRFoundationView() {
  const [tab, setTab] = useState<Tab>("profiles");
  const [organizations, setOrganizations] = useState<HROrganizationCapability[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [profiles, setProfiles] = useState<HRJobProfileItem[]>([]);
  const [positions, setPositions] = useState<HRPositionItem[]>([]);
  const [people, setPeople] = useState<HRPersonOption[]>([]);
  const [employments, setEmployments] = useState<HREmploymentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [editor, setEditor] = useState<Editor>({ type: "closed" });

  const [profileCode, setProfileCode] = useState("");
  const [profileTitle, setProfileTitle] = useState("");
  const [profileDescription, setProfileDescription] = useState("");
  const [profileScope, setProfileScope] = useState<ScopeMode>("self");

  const [positionCode, setPositionCode] = useState("");
  const [positionName, setPositionName] = useState("");
  const [positionProfileId, setPositionProfileId] = useState("");
  const [reportsToPositionId, setReportsToPositionId] = useState("");

  const [employmentPersonId, setEmploymentPersonId] = useState("");
  const [employmentPositionId, setEmploymentPositionId] = useState("");
  const [employmentNumber, setEmploymentNumber] = useState("");
  const [employmentType, setEmploymentType] = useState<HREmploymentType>("other");
  const [employmentStartDate, setEmploymentStartDate] = useState(todayIso());

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === organizationId),
    [organizationId, organizations],
  );
  const activeProfiles = useMemo(() => profiles.filter((item) => item.is_active), [profiles]);
  const activePositions = useMemo(() => positions.filter((item) => item.is_active), [positions]);
  const occupiedPositionIds = useMemo(
    () => new Set(employments.filter((item) => item.is_active && item.position_id).map((item) => item.position_id as string)),
    [employments],
  );
  const activePersonIds = useMemo(
    () => new Set(employments.filter((item) => item.is_active).map((item) => item.person_id)),
    [employments],
  );

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const items = await apiFetch<HROrganizationCapability[]>("/api/modules/hr/organizations");
      setOrganizations(items);
      setOrganizationId((current) => {
        if (current && items.some((item) => item.id === current && item.can_read)) return current;
        return items.find((item) => item.can_read)?.id ?? "";
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
      if (!capability?.can_read) return;
      setRefreshing(true);
      setNotice(null);
      const inactive = capability.can_manage ? "true" : "false";
      try {
        const [nextProfiles, nextPositions, nextPeople, nextEmployments] = await Promise.all([
          apiFetch<HRJobProfileItem[]>(
            `/api/modules/hr/job-profiles?organization_id=${encodeURIComponent(targetId)}&include_inactive=${inactive}`,
          ),
          apiFetch<HRPositionItem[]>(
            `/api/modules/hr/positions?organization_id=${encodeURIComponent(targetId)}&include_inactive=${inactive}`,
          ),
          apiFetch<HRPersonOption[]>(
            `/api/modules/hr/people?organization_id=${encodeURIComponent(targetId)}`,
          ),
          apiFetch<HREmploymentItem[]>(
            `/api/modules/hr/employments?organization_id=${encodeURIComponent(targetId)}&include_inactive=${inactive}`,
          ),
        ]);
        setProfiles(nextProfiles);
        setPositions(nextPositions);
        setPeople(nextPeople);
        setEmployments(nextEmployments);
      } catch (error) {
        setProfiles([]);
        setPositions([]);
        setPeople([]);
        setEmployments([]);
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

  function openProfile(item?: HRJobProfileItem) {
    setProfileCode(item?.code ?? "");
    setProfileTitle(item?.title ?? "");
    setProfileDescription(item?.description ?? "");
    setProfileScope(item?.scope_mode ?? "self");
    setEditor({ type: "profile", mode: item ? "edit" : "create", item });
  }

  function openPosition(item?: HRPositionItem) {
    setPositionCode(item?.code ?? "");
    setPositionName(item?.name ?? "");
    setPositionProfileId(item?.job_profile_id ?? activeProfiles[0]?.id ?? "");
    setReportsToPositionId(item?.reports_to_position_id ?? "");
    setEditor({ type: "position", mode: item ? "edit" : "create", item });
  }

  function openEmployment(item?: HREmploymentItem) {
    setEmploymentPersonId(item?.person_id ?? people.find((person) => !activePersonIds.has(person.id))?.id ?? "");
    setEmploymentPositionId(item?.position_id ?? "");
    setEmploymentNumber(item?.employment_number ?? "");
    setEmploymentType(item?.employment_type ?? "other");
    setEmploymentStartDate(item?.start_date ?? todayIso());
    setEditor({ type: "employment", mode: item ? "edit" : "create", item });
  }

  async function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization || editor.type !== "profile") return;
    setBusy(true);
    setNotice(null);
    try {
      const editing = editor.mode === "edit" && editor.item;
      const saved = await apiFetch<HRJobProfileItem>(
        editing
          ? `/api/modules/hr/job-profiles/${encodeURIComponent(editor.item!.id)}`
          : "/api/modules/hr/job-profiles",
        {
          method: editing ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            editing
              ? {
                  title: profileTitle.trim(),
                  description: profileDescription.trim() || null,
                  scope_mode: profileScope,
                }
              : {
                  organization_id: selectedOrganization.id,
                  code: normalizeHrCode(profileCode),
                  title: profileTitle.trim(),
                  description: profileDescription.trim() || null,
                  scope_mode: profileScope,
                },
          ),
        },
      );
      setProfiles((current) => {
        const exists = current.some((item) => item.id === saved.id);
        return exists ? current.map((item) => (item.id === saved.id ? saved : item)) : [...current, saved];
      });
      setEditor({ type: "closed" });
      setNotice({ tone: "success", text: editing ? "عنوان شغلی به‌روزرسانی شد." : "عنوان شغلی پایه ساخته شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function submitPosition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization || editor.type !== "position") return;
    setBusy(true);
    setNotice(null);
    try {
      const editing = editor.mode === "edit" && editor.item;
      const body = editing
        ? {
            code: normalizeHrCode(positionCode),
            name: positionName.trim() || null,
            job_profile_id: positionProfileId,
            reports_to_position_id: reportsToPositionId || null,
          }
        : {
            organization_id: selectedOrganization.id,
            code: normalizeHrCode(positionCode),
            name: positionName.trim() || null,
            job_profile_id: positionProfileId,
            reports_to_position_id: reportsToPositionId || null,
          };
      const saved = await apiFetch<HRPositionItem>(
        editing
          ? `/api/modules/hr/positions/${encodeURIComponent(editor.item!.id)}`
          : "/api/modules/hr/positions",
        {
          method: editing ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      setPositions((current) => {
        const exists = current.some((item) => item.id === saved.id);
        return exists ? current.map((item) => (item.id === saved.id ? saved : item)) : [...current, saved];
      });
      setEditor({ type: "closed" });
      setNotice({ tone: "success", text: editing ? "پست سازمانی به‌روزرسانی شد." : "پست سازمانی برنامه‌ریزی شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function submitEmployment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization || editor.type !== "employment") return;
    setBusy(true);
    setNotice(null);
    try {
      const editing = editor.mode === "edit" && editor.item;
      const body = editing
        ? {
            position_id: employmentPositionId || null,
            employment_number: employmentNumber.trim() || null,
            employment_type: employmentType,
            start_date: employmentStartDate,
          }
        : {
            organization_id: selectedOrganization.id,
            person_id: employmentPersonId,
            position_id: employmentPositionId || null,
            employment_number: employmentNumber.trim() || null,
            employment_type: employmentType,
            start_date: employmentStartDate,
          };
      const saved = await apiFetch<HREmploymentItem>(
        editing
          ? `/api/modules/hr/employments/${encodeURIComponent(editor.item!.id)}`
          : "/api/modules/hr/employments",
        {
          method: editing ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      setEmployments((current) => {
        const exists = current.some((item) => item.id === saved.id);
        return exists ? current.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...current];
      });
      setEditor({ type: "closed" });
      setNotice({ tone: "success", text: editing ? "رکورد همکاری به‌روزرسانی شد." : "رکورد همکاری ایجاد شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function toggleProfile(item: HRJobProfileItem) {
    if (!window.confirm(item.is_active ? `عنوان «${item.title}» غیرفعال شود؟` : `عنوان «${item.title}» دوباره فعال شود؟`)) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<HRJobProfileItem>(
        `/api/modules/hr/job-profiles/${encodeURIComponent(item.id)}/status`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: !item.is_active }),
        },
      );
      setProfiles((current) => current.map((entry) => (entry.id === saved.id ? saved : entry)));
      setNotice({ tone: "success", text: "وضعیت عنوان شغلی تغییر کرد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function togglePosition(item: HRPositionItem) {
    if (!window.confirm(item.is_active ? `پست «${hrPositionLabel(item)}» غیرفعال شود؟` : `پست «${hrPositionLabel(item)}» دوباره فعال شود؟`)) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<HRPositionItem>(
        `/api/modules/hr/positions/${encodeURIComponent(item.id)}/status`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: !item.is_active }),
        },
      );
      setPositions((current) => current.map((entry) => (entry.id === saved.id ? saved : entry)));
      setNotice({ tone: "success", text: "وضعیت پست سازمانی تغییر کرد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function toggleEmployment(item: HREmploymentItem) {
    const action = item.is_active ? "پایان همکاری" : "فعال‌سازی دوباره همکاری";
    if (!window.confirm(`${action} برای ${item.person.first_name} ${item.person.last_name} انجام شود؟`)) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await apiFetch<HREmploymentItem>(
        `/api/modules/hr/employments/${encodeURIComponent(item.id)}/status`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item.is_active ? { is_active: false, end_date: todayIso() } : { is_active: true }),
        },
      );
      setEmployments((current) => current.map((entry) => (entry.id === saved.id ? saved : entry)));
      setNotice({ tone: "success", text: item.is_active ? "همکاری پایان یافت و سابقه حفظ شد." : "همکاری دوباره فعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <AsyncState label="در حال آماده‌سازی پایه منابع انسانی…" />;

  return (
    <section className="hr-foundation">
      <div className="hr-title-row">
        <div>
          <span className="page-eyebrow">D1 · HR Foundation</span>
          <h1>پایه منابع انسانی</h1>
          <p>
            این بخش برای طراحی آینده است: عنوان شغلی و پست سازمانی را می‌توان قبل از استخدام افراد ساخت؛ حقوق، حضور و غیاب و استخدام عملیاتی هنوز وارد این فاز نشده‌اند.
          </p>
        </div>
        <div className="hr-title-controls">
          <select
            value={organizationId}
            onChange={(event) => setOrganizationId(event.target.value)}
            aria-label="سازمان منابع انسانی"
          >
            {organizations.filter((item) => item.can_read).map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name} · {organization.code}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="secondary-action-button"
            onClick={() => organizationId && void loadOrganizationData(organizationId)}
            disabled={refreshing || !organizationId}
          >
            {refreshing ? "در حال بروزرسانی…" : "بروزرسانی"}
          </button>
        </div>
      </div>

      {selectedOrganization ? (
        <div className="hr-capability-strip">
          <span>سازمان: <b>{selectedOrganization.name}</b></span>
          <span>مشاهده: <b>{selectedOrganization.can_read ? "مجاز" : "غیرمجاز"}</b></span>
          <span>مدیریت: <b>{selectedOrganization.can_manage ? "مجاز" : "فقط خواندنی"}</b></span>
          <span>پست خالی: <b>{activePositions.filter((item) => !occupiedPositionIds.has(item.id)).length.toLocaleString("fa-IR")}</b></span>
        </div>
      ) : null}

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      {!selectedOrganization ? (
        <div className="panel-card empty-state">هیچ سازمانی در محدوده دسترسی HR این حساب وجود ندارد.</div>
      ) : (
        <>
          <div className="hr-tabs" role="tablist">
            <button className={tab === "profiles" ? "active" : ""} onClick={() => setTab("profiles")} type="button">عنوان‌های شغلی</button>
            <button className={tab === "positions" ? "active" : ""} onClick={() => setTab("positions")} type="button">پست‌های سازمانی</button>
            <button className={tab === "employments" ? "active" : ""} onClick={() => setTab("employments")} type="button">سوابق همکاری</button>
          </div>

          {tab === "profiles" ? (
            <div className="hr-panel panel-card">
              <div className="hr-panel-head">
                <div><strong>عنوان‌های شغلی پایه</strong><small>قابل استفاده برای همین سازمان یا زیرمجموعه‌ها.</small></div>
                {selectedOrganization.can_manage ? <button className="primary-action-button" type="button" onClick={() => openProfile()}>عنوان جدید</button> : null}
              </div>
              <div className="hr-card-grid">
                {profiles.length === 0 ? <div className="empty-state compact">هنوز عنوان شغلی تعریف نشده است.</div> : profiles.map((profile) => (
                  <article key={profile.id} className={`hr-entity-card ${profile.is_active ? "" : "is-muted"}`}>
                    <div className="hr-entity-head">
                      <div><span>{profile.code}</span><strong>{profile.title}</strong></div>
                      <em>{profile.is_active ? "فعال" : "غیرفعال"}</em>
                    </div>
                    <p>{profile.description || "بدون توضیح"}</p>
                    <small>دامنه: {hrScopeLabels[profile.scope_mode]}{profile.organization_id !== selectedOrganization.id ? " · تعریف‌شده در سازمان بالادست" : ""}</small>
                    {selectedOrganization.can_manage && profile.organization_id === selectedOrganization.id ? (
                      <div className="management-card-actions">
                        <button type="button" className="secondary-action-button" onClick={() => openProfile(profile)} disabled={busy}>ویرایش</button>
                        <button type="button" className={`status-action-button ${profile.is_active ? "danger" : "success"}`} onClick={() => void toggleProfile(profile)} disabled={busy}>{profile.is_active ? "غیرفعال" : "فعال"}</button>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {tab === "positions" ? (
            <div className="hr-panel panel-card">
              <div className="hr-panel-head">
                <div><strong>پست‌های سازمانی</strong><small>می‌توانند خالی باشند؛ یعنی قبل از استخدام واقعی ساختار را طراحی می‌کنید.</small></div>
                {selectedOrganization.can_manage ? <button className="primary-action-button" type="button" onClick={() => openPosition()} disabled={activeProfiles.length === 0}>پست جدید</button> : null}
              </div>
              <div className="hr-position-list">
                {positions.length === 0 ? <div className="empty-state compact">هنوز پست سازمانی برنامه‌ریزی نشده است.</div> : positions.map((position) => {
                  const parent = positions.find((item) => item.id === position.reports_to_position_id);
                  const occupied = occupiedPositionIds.has(position.id);
                  return (
                    <article key={position.id} className={`hr-position-row ${position.is_active ? "" : "is-muted"}`}>
                      <div>
                        <span>{position.code}</span>
                        <strong>{hrPositionLabel(position)}</strong>
                        <small>{position.job_profile.title} · گزارش به: {parent ? hrPositionLabel(parent) : "—"}</small>
                      </div>
                      <div className="hr-position-badges">
                        <em className={occupied ? "is-occupied" : "is-open"}>{occupied ? "اشغال" : "خالی"}</em>
                        <em>{position.is_active ? "فعال" : "غیرفعال"}</em>
                      </div>
                      {selectedOrganization.can_manage ? (
                        <div className="management-card-actions">
                          <button type="button" className="secondary-action-button" onClick={() => openPosition(position)} disabled={busy}>ویرایش</button>
                          <button type="button" className={`status-action-button ${position.is_active ? "danger" : "success"}`} onClick={() => void togglePosition(position)} disabled={busy}>{position.is_active ? "غیرفعال" : "فعال"}</button>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </div>
          ) : null}

          {tab === "employments" ? (
            <div className="hr-panel panel-card">
              <div className="hr-panel-head">
                <div><strong>سوابق همکاری</strong><small>Person از Core می‌آید؛ پایان همکاری رکورد را حذف نمی‌کند و سابقه باقی می‌ماند.</small></div>
                {selectedOrganization.can_manage ? <button className="primary-action-button" type="button" onClick={() => openEmployment()} disabled={people.length === 0}>ثبت همکاری</button> : null}
              </div>
              <div className="hr-employment-list">
                {employments.length === 0 ? <div className="empty-state compact">هنوز رکورد همکاری ثبت نشده است.</div> : employments.map((employment) => {
                  const position = positions.find((item) => item.id === employment.position_id);
                  return (
                    <article key={employment.id} className={`hr-employment-row ${employment.is_active ? "" : "is-muted"}`}>
                      <div>
                        <strong>{employment.person.first_name} {employment.person.last_name}</strong>
                        <span>{position ? hrPositionLabel(position) : "بدون پست مشخص"}</span>
                        <small>نوع: {hrEmploymentTypeLabels[employment.employment_type]} · شماره: {employment.employment_number || "—"} · شروع: {employment.start_date}{employment.end_date ? ` · پایان: ${employment.end_date}` : ""}</small>
                      </div>
                      <em>{employment.is_active ? "فعال" : "پایان‌یافته"}</em>
                      {selectedOrganization.can_manage ? (
                        <div className="management-card-actions">
                          <button type="button" className="secondary-action-button" onClick={() => openEmployment(employment)} disabled={busy || !employment.is_active}>ویرایش</button>
                          <button type="button" className={`status-action-button ${employment.is_active ? "danger" : "success"}`} onClick={() => void toggleEmployment(employment)} disabled={busy}>{employment.is_active ? "پایان همکاری" : "فعال‌سازی"}</button>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </div>
          ) : null}
        </>
      )}

      {editor.type !== "closed" ? (
        <div className="management-dialog-layer" role="dialog" aria-modal="true">
          <button className="management-dialog-backdrop" type="button" aria-label="بستن" onClick={() => !busy && setEditor({ type: "closed" })} />
          <div className="management-dialog">
            <div className="management-dialog-head">
              <div>
                <span>D1 · HR Foundation</span>
                <h2>
                  {editor.type === "profile" ? (editor.mode === "create" ? "عنوان شغلی جدید" : "ویرایش عنوان شغلی") : null}
                  {editor.type === "position" ? (editor.mode === "create" ? "پست سازمانی جدید" : "ویرایش پست سازمانی") : null}
                  {editor.type === "employment" ? (editor.mode === "create" ? "ثبت همکاری" : "ویرایش همکاری") : null}
                </h2>
              </div>
              <button type="button" onClick={() => !busy && setEditor({ type: "closed" })}>×</button>
            </div>

            {editor.type === "profile" ? (
              <form className="management-form" onSubmit={submitProfile}>
                <div className="management-form-columns">
                  <label><span>کد عنوان</span><input value={profileCode} disabled={editor.mode === "edit" || busy} required maxLength={100} onChange={(event) => setProfileCode(event.target.value)} placeholder="FIN-MGR" /></label>
                  <label><span>عنوان</span><input value={profileTitle} disabled={busy} required maxLength={180} onChange={(event) => setProfileTitle(event.target.value)} placeholder="مدیر مالی" /></label>
                </div>
                <label><span>دامنه استفاده</span><select value={profileScope} disabled={busy} onChange={(event) => setProfileScope(event.target.value as ScopeMode)}><option value="self">فقط همین سازمان</option><option value="self_and_descendants">این سازمان و زیرمجموعه‌ها</option></select></label>
                <label><span>توضیح</span><textarea value={profileDescription} disabled={busy} maxLength={1000} onChange={(event) => setProfileDescription(event.target.value)} /></label>
                <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setEditor({ type: "closed" })} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy}>{busy ? "در حال ذخیره…" : "ذخیره"}</button></div>
              </form>
            ) : null}

            {editor.type === "position" ? (
              <form className="management-form" onSubmit={submitPosition}>
                <div className="management-form-columns">
                  <label><span>کد پست</span><input value={positionCode} disabled={busy} required maxLength={100} onChange={(event) => setPositionCode(event.target.value)} placeholder="FIN-001" /></label>
                  <label><span>نام نمایشی (اختیاری)</span><input value={positionName} disabled={busy} maxLength={180} onChange={(event) => setPositionName(event.target.value)} placeholder="مدیر مالی شرکت" /></label>
                </div>
                <label><span>عنوان شغلی</span><select value={positionProfileId} disabled={busy} required onChange={(event) => setPositionProfileId(event.target.value)}>{activeProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.title} · {profile.code}</option>)}</select></label>
                <label><span>گزارش به</span><select value={reportsToPositionId} disabled={busy} onChange={(event) => setReportsToPositionId(event.target.value)}><option value="">بدون سرپرست مستقیم</option>{activePositions.filter((position) => position.id !== editor.item?.id).map((position) => <option key={position.id} value={position.id}>{hrPositionLabel(position)} · {position.code}</option>)}</select></label>
                <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setEditor({ type: "closed" })} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy || !positionProfileId}>{busy ? "در حال ذخیره…" : "ذخیره"}</button></div>
              </form>
            ) : null}

            {editor.type === "employment" ? (
              <form className="management-form" onSubmit={submitEmployment}>
                <label><span>شخص</span><select value={employmentPersonId} disabled={busy || editor.mode === "edit"} required onChange={(event) => setEmploymentPersonId(event.target.value)}>{people.map((person) => <option key={person.id} value={person.id} disabled={editor.mode === "create" && activePersonIds.has(person.id)}>{person.first_name} {person.last_name}{activePersonIds.has(person.id) && person.id !== editor.item?.person_id ? " · همکاری فعال دارد" : ""}</option>)}</select></label>
                <div className="management-form-columns">
                  <label><span>پست سازمانی</span><select value={employmentPositionId} disabled={busy} onChange={(event) => setEmploymentPositionId(event.target.value)}><option value="">بدون پست مشخص</option>{activePositions.map((position) => <option key={position.id} value={position.id} disabled={occupiedPositionIds.has(position.id) && position.id !== editor.item?.position_id}>{hrPositionLabel(position)} · {occupiedPositionIds.has(position.id) && position.id !== editor.item?.position_id ? "اشغال" : "خالی"}</option>)}</select></label>
                  <label><span>شماره پرسنلی (اختیاری)</span><input value={employmentNumber} disabled={busy} maxLength={80} onChange={(event) => setEmploymentNumber(event.target.value)} /></label>
                </div>
                <div className="management-form-columns">
                  <label><span>نوع همکاری</span><select value={employmentType} disabled={busy} onChange={(event) => setEmploymentType(event.target.value as HREmploymentType)}>{Object.entries(hrEmploymentTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  <label><span>تاریخ شروع</span><input type="date" value={employmentStartDate} disabled={busy} required onChange={(event) => setEmploymentStartDate(event.target.value)} /></label>
                </div>
                <p className="management-form-note">برای ثبت همکاری، شخص باید قبلاً یک ارتباط فعال با همین سازمان در Core اشخاص داشته باشد.</p>
                <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setEditor({ type: "closed" })} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy || !employmentPersonId}>{busy ? "در حال ذخیره…" : "ذخیره"}</button></div>
              </form>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
