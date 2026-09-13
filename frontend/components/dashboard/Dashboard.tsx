"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  AccessAssignment,
  AuditEventItem,
  DocumentExpirationItem,
  OrganizationItem,
  PersonItem,
  UserItem,
} from "@/lib/core-types";
import {
  getDashboardCapabilities,
  summarizeDashboard,
  type DashboardSnapshot,
} from "@/lib/dashboard";
import {
  auditActionLabel,
  documentExpirationLabel,
  resourceLabel,
} from "@/lib/core-labels";
import { isViewVisible, type ViewKey } from "@/lib/navigation";

const EMPTY_SNAPSHOT: DashboardSnapshot = {
  organizations: [],
  people: [],
  users: [],
  expiringDocuments: [],
  recentAudit: [],
};

const loadLabels = {
  organizations: "سازمان‌ها",
  people: "اشخاص",
  users: "کاربران",
  documents: "اسناد نزدیک انقضا",
  audit: "فعالیت‌های اخیر",
} as const;

type LoadKey = keyof typeof loadLabels;

export function Dashboard({
  assignments,
  allPermissions,
  onNavigate,
}: {
  assignments: AccessAssignment[];
  allPermissions: string[];
  onNavigate: (view: ViewKey) => void;
}) {
  const capabilities = useMemo(
    () => getDashboardCapabilities(allPermissions),
    [allPermissions],
  );
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>(EMPTY_SNAPSHOT);
  const [loading, setLoading] = useState(true);
  const [failedSections, setFailedSections] = useState<LoadKey[]>([]);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setFailedSections([]);

    const next: DashboardSnapshot = {
      organizations: [],
      people: [],
      users: [],
      expiringDocuments: [],
      recentAudit: [],
    };
    const failures: LoadKey[] = [];

    const guarded = async <T,>(
      key: LoadKey,
      request: Promise<T>,
      apply: (value: T) => void,
    ) => {
      try {
        apply(await request);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return;
        }
        failures.push(key);
      }
    };

    const requests: Promise<void>[] = [];

    if (capabilities.organizations) {
      requests.push(
        guarded(
          "organizations",
          apiFetch<OrganizationItem[]>("/api/core/organizations"),
          (value) => {
            next.organizations = value;
          },
        ),
      );
    }
    if (capabilities.people) {
      requests.push(
        guarded("people", apiFetch<PersonItem[]>("/api/core/people"), (value) => {
          next.people = value;
        }),
      );
    }
    if (capabilities.users) {
      requests.push(
        guarded("users", apiFetch<UserItem[]>("/api/core/users"), (value) => {
          next.users = value;
        }),
      );
    }
    if (capabilities.documents) {
      requests.push(
        guarded(
          "documents",
          apiFetch<DocumentExpirationItem[]>(
            "/api/core/documents/expiring?within_days=30&include_expired=true&limit=200",
          ),
          (value) => {
            next.expiringDocuments = value;
          },
        ),
      );
    }
    if (capabilities.audit) {
      requests.push(
        guarded(
          "audit",
          apiFetch<AuditEventItem[]>("/api/core/audit?limit=6&offset=0"),
          (value) => {
            next.recentAudit = value;
          },
        ),
      );
    }

    await Promise.all(requests);
    setSnapshot(next);
    setFailedSections(Array.from(new Set(failures)));
    setRefreshedAt(new Date());
    setLoading(false);
  }, [capabilities]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const summary = useMemo(
    () => summarizeDashboard(snapshot, assignments),
    [assignments, snapshot],
  );

  const quickActions = useMemo(
    () =>
      [
        { view: "organizations" as const, label: "سازمان‌ها", hint: "مشاهده ساختار سازمانی", icon: "OR" },
        { view: "people" as const, label: "اشخاص", hint: "مدیریت افراد و ارتباط‌ها", icon: "PE" },
        { view: "users" as const, label: "کاربران", hint: "حساب‌های کاربری سیستم", icon: "US" },
        { view: "documents" as const, label: "اسناد", hint: "مدیریت اسناد و نسخه‌ها", icon: "DO" },
        { view: "access" as const, label: "دسترسی‌ها", hint: "Role و محدوده‌های دسترسی", icon: "AC" },
        { view: "audit" as const, label: "تاریخچه", hint: "رویدادهای ثبت‌شده Core", icon: "AU" },
      ].filter((item) => isViewVisible(item.view, allPermissions)),
    [allPermissions],
  );

  const failedText = failedSections.map((key) => loadLabels[key]).join("، ");
  const expiringPreview = snapshot.expiringDocuments.slice(0, 6);
  const attentionCount = summary.expiringDocumentCount + summary.expiredDocumentCount;
  const documentResultCapped = snapshot.expiringDocuments.length >= 200;

  function metricValue(key: LoadKey, value: number): number | string {
    if (failedSections.includes(key)) return "—";
    if (loading && refreshedAt === null) return "…";
    return value;
  }

  return (
    <section className="dashboard-v2" aria-labelledby="dashboard-title">
      <div className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="status-pill">داشبورد عملیاتی</span>
          <h1 id="dashboard-title">مرکز مدیریت نوین برتر</h1>
          <p>
            نمای زنده Core بر اساس دسترسی فعلی شما. اعداد و رویدادها از Backend
            دریافت می‌شوند و داده خارج از Organization Scope نمایش داده نمی‌شود.
          </p>
        </div>
        <div className="dashboard-refresh-box">
          <span>آخرین به‌روزرسانی</span>
          <strong>
            {refreshedAt
              ? refreshedAt.toLocaleTimeString("fa-IR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"}
          </strong>
          <button type="button" onClick={() => void loadDashboard()} disabled={loading}>
            {loading ? "در حال دریافت…" : "به‌روزرسانی داشبورد"}
          </button>
        </div>
      </div>

      {failedSections.length > 0 ? (
        <AppNotice tone="error">
          بخشی از داشبورد به‌روزرسانی نشد: {failedText}. سایر بخش‌های سالم همچنان
          قابل استفاده‌اند.
        </AppNotice>
      ) : null}

      {loading && refreshedAt === null ? (
        <AsyncState label="در حال دریافت نمای عملیاتی…" />
      ) : null}

      <div className="dashboard-metric-grid" aria-label="شاخص‌های Core">
        {capabilities.organizations ? (
          <MetricCard
            label="سازمان‌های قابل مشاهده"
            value={metricValue("organizations", summary.organizationCount)}
            detail={
              failedSections.includes("organizations")
                ? "دریافت اطلاعات ناموفق بود"
                : "در محدوده دسترسی فعلی"
            }
            onClick={() => onNavigate("organizations")}
          />
        ) : null}
        {capabilities.people ? (
          <MetricCard
            label="اشخاص"
            value={metricValue("people", summary.peopleCount)}
            detail={
              failedSections.includes("people")
                ? "دریافت اطلاعات ناموفق بود"
                : `${summary.activePeopleCount.toLocaleString("fa-IR")} شخص فعال`
            }
            onClick={() => onNavigate("people")}
          />
        ) : null}
        {capabilities.users ? (
          <MetricCard
            label="کاربران سیستم"
            value={metricValue("users", summary.userCount)}
            detail={
              failedSections.includes("users")
                ? "دریافت اطلاعات ناموفق بود"
                : `${summary.activeUserCount.toLocaleString("fa-IR")} حساب فعال`
            }
            onClick={() => onNavigate("users")}
          />
        ) : null}
        {capabilities.documents ? (
          <MetricCard
            label="اسناد نیازمند توجه"
            onClick={isViewVisible("documents", allPermissions) ? () => onNavigate("documents") : undefined}
            value={
              failedSections.includes("documents")
                ? "—"
                : loading && refreshedAt === null
                  ? "…"
                  : documentResultCapped
                    ? `${attentionCount.toLocaleString("fa-IR")}+`
                    : attentionCount
            }
            detail={
              failedSections.includes("documents")
                ? "دریافت اطلاعات ناموفق بود"
                : documentResultCapped
                  ? "حداقل این تعداد؛ سقف داشبورد ۲۰۰ رکورد است"
                  : `${summary.expiredDocumentCount.toLocaleString("fa-IR")} منقضی‌شده`
            }
          />
        ) : null}
        <MetricCard
          label="Scopeهای دسترسی"
          value={summary.assignmentCount}
          detail={`${summary.roleCount.toLocaleString("fa-IR")} Role فعال`}
          onClick={
            isViewVisible("access", allPermissions)
              ? () => onNavigate("access")
              : undefined
          }
        />
      </div>

      <div className="dashboard-main-grid">
        <article className="panel dashboard-actions-panel">
          <div className="panel-heading dashboard-panel-heading">
            <div>
              <span>دسترسی سریع</span>
              <h3>فضای کاری Core</h3>
            </div>
            <small>فقط بخش‌های مجاز برای شما نمایش داده می‌شوند</small>
          </div>
          <div className="dashboard-quick-grid">
            {quickActions.map((item) => (
              <button
                type="button"
                className="dashboard-quick-action"
                key={item.view}
                onClick={() => onNavigate(item.view)}
              >
                <span className="dashboard-quick-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.hint}</small>
                </span>
                <b aria-hidden="true">←</b>
              </button>
            ))}
          </div>
        </article>

        <article className="panel dashboard-scope-panel">
          <div className="panel-heading dashboard-panel-heading">
            <div>
              <span>Authorization</span>
              <h3>محدوده مدیریت شما</h3>
            </div>
            <small>{allPermissions.length.toLocaleString("fa-IR")} مجوز مؤثر</small>
          </div>
          <div className="dashboard-scope-list">
            {assignments.slice(0, 6).map((assignment) => (
              <div
                className="dashboard-scope-row"
                key={`${assignment.role_code}-${assignment.organization_id}`}
              >
                <div>
                  <strong>{assignment.organization_name}</strong>
                  <span dir="ltr">{assignment.role_code}</span>
                </div>
                <span className="scope-badge">
                  {assignment.scope_mode === "self_and_descendants"
                    ? "سازمان + زیرمجموعه‌ها"
                    : "فقط همین سازمان"}
                </span>
              </div>
            ))}
            {assignments.length === 0 ? (
              <div className="empty-state">Scope فعالی برای این حساب وجود ندارد.</div>
            ) : null}
            {assignments.length > 6 && isViewVisible("access", allPermissions) ? (
              <button
                type="button"
                className="dashboard-text-button"
                onClick={() => onNavigate("access")}
              >
                مشاهده همه محدوده‌ها
              </button>
            ) : null}
          </div>
        </article>
      </div>

      <div className="dashboard-main-grid dashboard-secondary-grid">
        {capabilities.documents ? (
          <article className="panel">
            <div className="panel-heading dashboard-panel-heading">
              <div>
                <span>Documents</span>
                <h3>انقضای اسناد</h3>
              </div>
              <small>۳۰ روز آینده + اسناد منقضی‌شده</small>
            </div>
            <div className="dashboard-attention-list">
              {expiringPreview.map((item) => (
                <div className="dashboard-attention-row" key={item.document.id}>
                  <div>
                    <strong>{item.document.title}</strong>
                    <span>{item.document.document_type}</span>
                  </div>
                  <span
                    className={`attention-badge ${
                      item.expiration_state === "expired" ? "is-overdue" : "is-warning"
                    }`}
                  >
                    {documentExpirationLabel(item)}
                  </span>
                </div>
              ))}
              {expiringPreview.length === 0 ? (
                <div className="dashboard-good-state">در بازه فعلی سند نیازمند توجهی نیست.</div>
              ) : null}
              {snapshot.expiringDocuments.length > expiringPreview.length ? (
                <div className="dashboard-list-footnote">
                  {(
                    snapshot.expiringDocuments.length - expiringPreview.length
                  ).toLocaleString("fa-IR")} مورد دیگر در محدوده دسترسی شما
                </div>
              ) : null}
            </div>
          </article>
        ) : null}

        {capabilities.audit ? (
          <article className="panel">
            <div className="panel-heading dashboard-panel-heading">
              <div>
                <span>Audit</span>
                <h3>آخرین فعالیت‌ها</h3>
              </div>
              <button
                type="button"
                className="dashboard-text-button"
                onClick={() => onNavigate("audit")}
              >
                مشاهده تاریخچه
              </button>
            </div>
            <div className="dashboard-activity-list">
              {snapshot.recentAudit.map((event) => (
                <div className="dashboard-activity-row" key={event.id}>
                  <span className="activity-mark" aria-hidden="true" />
                  <div>
                    <strong>{auditActionLabel(event.action)}</strong>
                    <span>
                      {resourceLabel(event.resource_type)} · {event.actor_identifier ?? "system"}
                    </span>
                  </div>
                  <time dateTime={event.occurred_at}>
                    {new Date(event.occurred_at).toLocaleString("fa-IR", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </div>
              ))}
              {snapshot.recentAudit.length === 0 ? (
                <div className="empty-state">رویداد قابل مشاهده‌ای ثبت نشده است.</div>
              ) : null}
            </div>
          </article>
        ) : null}
      </div>

      {!capabilities.documents && !capabilities.audit ? (
        <div className="dashboard-info-strip">
          داشبورد فقط داده‌هایی را درخواست می‌کند که حساب فعلی مجوز مشاهده آن‌ها را
          دارد. با افزایش دسترسی، بخش‌های مرتبط به‌صورت خودکار ظاهر می‌شوند.
        </div>
      ) : null}
    </section>
  );
}

function MetricCard({
  label,
  value,
  detail,
  onClick,
}: {
  label: string;
  value: number | string;
  detail: string;
  onClick?: () => void;
}) {
  const content = (
    <>
      <span>{label}</span>
      <strong>{typeof value === "number" ? value.toLocaleString("fa-IR") : value}</strong>
      <small>{detail}</small>
    </>
  );

  if (onClick) {
    return (
      <button type="button" className="dashboard-metric-card is-action" onClick={onClick}>
        {content}
      </button>
    );
  }

  return <article className="dashboard-metric-card">{content}</article>;
}
