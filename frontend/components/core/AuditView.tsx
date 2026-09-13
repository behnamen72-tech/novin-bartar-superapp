import type { AuditEventItem } from "@/lib/core-types";
import { auditActionLabel } from "@/lib/core-labels";
export type { AuditEventItem } from "@/lib/core-types";

export function AuditView({ events }: { events: AuditEventItem[] }) {
  return (
    <section className="page-section">
      <div className="page-title">
        <div>
          <span>Audit Core</span>
          <h1>تاریخچه فعالیت‌ها</h1>
          <p>
            این رویدادها فقط قابل مشاهده‌اند و امکان ویرایش یا حذف از برنامه
            ندارند. نمایش آن‌ها بر اساس audit.read و محدوده سازمانی فیلتر می‌شود.
          </p>
        </div>
        <div className="count-box">
          <span>رویداد قابل مشاهده</span>
          <strong>{events.length}</strong>
        </div>
      </div>

      <div className="audit-list">
        {events.map((event) => (
          <article className="audit-card" key={event.id}>
            <div className="audit-card-head">
              <div>
                <span className="tiny-label">عملیات</span>
                <strong>{auditActionLabel(event.action)}</strong>
                <small>{event.action}</small>
              </div>
              <time>
                {new Date(event.occurred_at).toLocaleString("fa-IR")}
              </time>
            </div>

            <div className="audit-grid">
              <div>
                <span>کاربر</span>
                <strong dir="ltr">{event.actor_identifier ?? "system"}</strong>
              </div>
              <div>
                <span>نوع رکورد</span>
                <strong>{event.resource_type}</strong>
              </div>
              <div>
                <span>شناسه رکورد</span>
                <strong dir="ltr">{event.resource_id}</strong>
              </div>
              <div>
                <span>منبع</span>
                <strong>{event.source}</strong>
              </div>
            </div>

            {(event.before_state || event.after_state) ? (
              <details className="audit-details">
                <summary>مشاهده جزئیات تغییر</summary>
                <div className="audit-state-grid">
                  <pre>
                    {JSON.stringify(event.before_state, null, 2) || "null"}
                  </pre>
                  <pre>
                    {JSON.stringify(event.after_state, null, 2) || "null"}
                  </pre>
                </div>
              </details>
            ) : null}
          </article>
        ))}

        {events.length === 0 ? (
          <div className="empty-state">
            رویداد قابل مشاهده‌ای در محدوده دسترسی شما وجود ندارد.
          </div>
        ) : null}
      </div>
    </section>
  );
}
