import { AuditView, type AuditEventItem } from "@/components/core/AuditView";
import type {
  AccessOverviewItem,
  OrganizationItem,
  PersonItem,
  UserItem,
} from "@/lib/core-types";
import { permissionLabel } from "@/lib/permissions";

export function OrganizationsView({ organizations }: { organizations: OrganizationItem[] }) {
  const byId = new Map(organizations.map((organization) => [organization.id, organization]));

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

  const sorted = [...organizations].sort((a, b) => {
    const depthDiff = depthOf(a) - depthOf(b);
    if (depthDiff !== 0) return depthDiff;
    return a.name.localeCompare(b.name, "fa");
  });

  return (
    <section className="page-section">
      <PageTitle
        eyebrow="Organization Core"
        title="ساختار سازمانی"
        description="فقط سازمان‌هایی نمایش داده می‌شوند که کاربر بر اساس Scope و Permission اجازه مشاهده‌شان را دارد."
        count={organizations.length}
      />
      <div className="organization-tree">
        {sorted.map((organization) => (
          <article
            className="organization-row"
            key={organization.id}
            style={{ marginRight: `${depthOf(organization) * 30}px` }}
          >
            <div className="tree-mark">{depthOf(organization) === 0 ? "●" : "↳"}</div>
            <div className="entity-main">
              <strong>{organization.name}</strong>
              <span dir="ltr">{organization.code}</span>
            </div>
            <span className="entity-type">
              {organizationTypeLabel(organization.organization_type)}
            </span>
            <Status active={organization.is_active} />
          </article>
        ))}
        {organizations.length === 0 ? <EmptyState /> : null}
      </div>
    </section>
  );
}

export function PeopleView({ people }: { people: PersonItem[] }) {
  return (
    <section className="page-section">
      <PageTitle
        eyebrow="People Core"
        title="اشخاص"
        description="Person از User جداست؛ این صفحه انسان‌ها و رابطه تجاری آن‌ها با سازمان را نشان می‌دهد."
        count={people.length}
      />
      <div className="data-grid">
        {people.map((person) => (
          <article className="entity-card" key={person.id}>
            <div className="entity-card-head">
              <div className="person-avatar">
                {person.first_name.slice(0, 1)}
                {person.last_name.slice(0, 1)}
              </div>
              <div>
                <strong>{person.first_name} {person.last_name}</strong>
                <span>{person.email ?? "ایمیل ثبت نشده"}</span>
              </div>
              <Status active={person.is_active} />
            </div>
            <div className="entity-meta">
              <span>تلفن</span>
              <strong dir="ltr">{person.phone ?? "—"}</strong>
            </div>
            <div className="relationship-chips">
              {person.relationships.map((relationship) => (
                <span key={`${relationship.organization_id}-${relationship.relationship_code}`}>
                  {relationshipLabel(relationship.relationship_code)} • {relationship.organization_name}
                </span>
              ))}
            </div>
          </article>
        ))}
        {people.length === 0 ? <EmptyState /> : null}
      </div>
    </section>
  );
}

export function UsersView({ users }: { users: UserItem[] }) {
  return (
    <section className="page-section">
      <PageTitle
        eyebrow="Identity Core"
        title="کاربران سیستم"
        description="User حساب ورود به سیستم است و به یک Person متصل می‌شود. رمز عبور هرگز در این صفحه یا API خروجی داده نمی‌شود."
        count={users.length}
      />
      <div className="table-shell table-scroll-shell">
        <div className="data-table user-table">
          <div className="table-row table-head">
            <span>شخص</span>
            <span>حساب</span>
            <span>سازمان</span>
            <span>وضعیت</span>
          </div>
          {users.map((user) => (
            <div className="table-row" key={user.id}>
              <div>
                <strong>{user.person_name}</strong>
                <small>{user.username ?? "بدون username"}</small>
              </div>
              <div>
                <strong dir="ltr">{user.email}</strong>
                <small>
                  {user.last_login_at
                    ? `آخرین ورود: ${new Date(user.last_login_at).toLocaleString("fa-IR")}`
                    : "هنوز وارد نشده"}
                </small>
              </div>
              <div className="org-tags">
                {user.organization_names.map((name) => <span key={name}>{name}</span>)}
              </div>
              <Status active={user.is_active} />
            </div>
          ))}
        </div>
        {users.length === 0 ? <EmptyState /> : null}
      </div>
    </section>
  );
}

export function AccessView({ assignments }: { assignments: AccessOverviewItem[] }) {
  return (
    <section className="page-section">
      <PageTitle
        eyebrow="Authorization Core"
        title="Role، Permission و Scope"
        description="هر ردیف یک تخصیص Role به User در یک محدوده سازمانی است. اطلاعات بر اساس access.read فیلتر می‌شود."
        count={assignments.length}
      />
      <div className="access-cards">
        {assignments.map((assignment) => (
          <article className="access-card" key={assignment.id}>
            <div className="access-card-top">
              <div>
                <span className="tiny-label">کاربر</span>
                <strong>{assignment.user_name}</strong>
                <small dir="ltr">{assignment.user_email}</small>
              </div>
              <Status active={assignment.is_active} />
            </div>
            <div className="access-role">
              <div>
                <span className="tiny-label">Role</span>
                <strong>{assignment.role_name}</strong>
                <small>{assignment.role_code}</small>
              </div>
              <div>
                <span className="tiny-label">Scope</span>
                <strong>{assignment.organization_name}</strong>
                <small>
                  {assignment.scope_mode === "self_and_descendants"
                    ? "سازمان + زیرمجموعه‌ها"
                    : "فقط همان سازمان"}
                </small>
              </div>
            </div>
            <div className="access-permissions">
              {assignment.permissions.map((permission) => (
                <span key={permission}>{permissionLabel(permission)}</span>
              ))}
            </div>
          </article>
        ))}
        {assignments.length === 0 ? <EmptyState /> : null}
      </div>
    </section>
  );
}

export function AuditCoreView({ events }: { events: AuditEventItem[] }) {
  return <AuditView events={events} />;
}

function PageTitle({
  eyebrow,
  title,
  description,
  count,
}: {
  eyebrow: string;
  title: string;
  description: string;
  count: number;
}) {
  return (
    <div className="page-title">
      <div>
        <span>{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="count-box">
        <span>تعداد قابل مشاهده</span>
        <strong>{count.toLocaleString("fa-IR")}</strong>
      </div>
    </div>
  );
}

function Status({ active }: { active: boolean }) {
  return (
    <span className={`status-badge ${active ? "is-active" : "is-inactive"}`}>
      {active ? "فعال" : "غیرفعال"}
    </span>
  );
}

function EmptyState() {
  return <div className="empty-state">داده‌ای در محدوده دسترسی شما وجود ندارد.</div>;
}

function organizationTypeLabel(type: OrganizationItem["organization_type"]) {
  const labels = {
    holding: "هلدینگ",
    company: "شرکت",
    branch: "شعبه",
    unit: "واحد",
  };
  return labels[type];
}

function relationshipLabel(code: string) {
  const labels: Record<string, string> = {
    manager: "مدیر",
    employee: "کارمند",
    contractor: "پیمانکار",
    customer_contact: "رابط مشتری",
  };
  return labels[code] ?? code;
}
