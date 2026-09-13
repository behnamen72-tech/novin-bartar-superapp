"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  AccessAssignment,
  CurrentUser,
  OrganizationItem,
  PersonItem,
  UserItem,
} from "@/lib/core-types";
import {
  canManagePersonGlobally,
  eligiblePeopleForUserCreation,
  normalizedUsername,
} from "@/lib/people-user-management";

type Props = {
  users: UserItem[];
  people: PersonItem[];
  organizations: OrganizationItem[];
  assignments: AccessAssignment[];
  currentUser: CurrentUser;
  onUserChanged: (user: UserItem, created: boolean) => void;
};

type Editor =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; user: UserItem }
  | { mode: "password"; user: UserItem };

function mutationErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "User not found.": "کاربر موردنظر پیدا نشد یا در محدوده دسترسی شما نیست.",
    "Person not found.": "شخص موردنظر پیدا نشد یا در محدوده مدیریت شما نیست.",
    "Person already has a user account.": "برای این شخص از قبل حساب کاربری ساخته شده است.",
    "Cannot create a user for an inactive person.": "برای شخص غیرفعال نمی‌توان حساب کاربری ساخت.",
    "Email or username already exists.": "ایمیل یا نام کاربری واردشده قبلاً استفاده شده است.",
    "Administrators cannot deactivate their own account through this endpoint.":
      "برای جلوگیری از قفل شدن دسترسی، حساب فعلی خودتان را از این صفحه نمی‌توانید غیرفعال کنید.",
  };
  return known[error.detail] ?? error.detail ?? "عملیات انجام نشد.";
}

export function UserManagementView({
  users,
  people,
  organizations,
  assignments,
  currentUser,
  onUserChanged,
}: Props) {
  const [editor, setEditor] = useState<Editor>({ mode: "closed" });
  const [notice, setNotice] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const [personId, setPersonId] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const peopleById = useMemo(() => new Map(people.map((person) => [person.id, person])), [people]);
  const candidates = useMemo(
    () => eligiblePeopleForUserCreation(people, users, organizations, assignments),
    [people, users, organizations, assignments],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("fa");
    if (!needle) return users;
    return users.filter((user) =>
      [user.person_name, user.email, user.username ?? "", ...user.organization_names]
        .join(" ")
        .toLocaleLowerCase("fa")
        .includes(needle),
    );
  }, [query, users]);

  function canManageUser(user: UserItem): boolean {
    const person = peopleById.get(user.person_id);
    if (!person) return false;
    return canManagePersonGlobally(person, "users.manage", organizations, assignments);
  }

  function closeEditor() {
    setPassword("");
    setPasswordConfirm("");
    setEditor({ mode: "closed" });
  }

  function openCreate() {
    const first = candidates[0];
    if (!first) return;
    setPersonId(first.id);
    setEmail(first.email ?? "");
    setUsername("");
    setPassword("");
    setPasswordConfirm("");
    setNotice(null);
    setEditor({ mode: "create" });
  }

  function openEdit(user: UserItem) {
    setEmail(user.email);
    setUsername(user.username ?? "");
    setPassword("");
    setPasswordConfirm("");
    setNotice(null);
    setEditor({ mode: "edit", user });
  }

  function openPassword(user: UserItem) {
    setPassword("");
    setPasswordConfirm("");
    setNotice(null);
    setEditor({ mode: "password", user });
  }

  function onCandidateChange(nextPersonId: string) {
    setPersonId(nextPersonId);
    const person = peopleById.get(nextPersonId);
    setEmail(person?.email ?? "");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);

    if ((editor.mode === "create" || editor.mode === "password") && password !== passwordConfirm) {
      setNotice({ tone: "error", text: "رمز عبور و تکرار آن یکسان نیستند." });
      return;
    }

    setSaving(true);
    try {
      if (editor.mode === "create") {
        const created = await apiFetch<UserItem>("/api/core/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            person_id: personId,
            email: email.trim().toLowerCase(),
            username: normalizedUsername(username),
            password,
          }),
        });
        onUserChanged(created, true);
        setPassword("");
        setPasswordConfirm("");
        closeEditor();
        setNotice({ tone: "success", text: "حساب کاربری با موفقیت ساخته شد." });
      } else if (editor.mode === "edit") {
        const updated = await apiFetch<UserItem>(
          `/api/core/users/${encodeURIComponent(editor.user.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: email.trim().toLowerCase(),
              username: normalizedUsername(username),
            }),
          },
        );
        onUserChanged(updated, false);
        closeEditor();
        setNotice({ tone: "success", text: "اطلاعات حساب کاربری به‌روزرسانی شد." });
      } else if (editor.mode === "password") {
        await apiFetch<void>(
          `/api/core/users/${encodeURIComponent(editor.user.id)}/password-reset`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_password: password }),
          },
        );
        setPassword("");
        setPasswordConfirm("");
        closeEditor();
        setNotice({ tone: "success", text: "رمز عبور جدید ثبت شد. مقدار رمز در UI یا Audit نگهداری نمی‌شود." });
      }
    } catch (error) {
      setPassword("");
      setPasswordConfirm("");
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(user: UserItem) {
    const nextActive = !user.is_active;
    if (!window.confirm(nextActive ? `حساب «${user.person_name}» فعال شود؟` : `حساب «${user.person_name}» غیرفعال شود؟`)) return;
    setBusyId(user.id);
    setNotice(null);
    try {
      const updated = await apiFetch<UserItem>(
        `/api/core/users/${encodeURIComponent(user.id)}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: nextActive }),
        },
      );
      onUserChanged(updated, false);
      setNotice({ tone: "success", text: nextActive ? "حساب کاربری فعال شد." : "حساب کاربری غیرفعال شد." });
    } catch (error) {
      setNotice({ tone: "error", text: mutationErrorMessage(error) });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="page-section user-management">
      <div className="page-title management-page-title">
        <div>
          <span>Identity Core</span>
          <h1>کاربران سیستم</h1>
          <p>ساخت و مدیریت حساب ورود متصل به Person. دسترسی نهایی برای هر تغییر در Backend و بر اساس users.manage و قواعد جلوگیری از privilege escalation کنترل می‌شود.</p>
        </div>
        <div className="management-title-actions">
          <div className="count-box"><span>قابل مشاهده</span><strong>{users.length.toLocaleString("fa-IR")}</strong></div>
          {candidates.length > 0 ? <button type="button" className="primary-action-button" onClick={openCreate}>+ کاربر جدید</button> : null}
        </div>
      </div>

      <div className="management-toolbar">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جستجو در نام، ایمیل، username یا سازمان…" />
        <span>{filtered.length.toLocaleString("fa-IR")} نتیجه</span>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}
      {people.length === 0 && assignments.some((item) => item.permissions.includes("users.manage")) ? (
        <AppNotice tone="info">برای ساخت حساب جدید، فهرست Personهای قابل مشاهده لازم است. مدیریت کاربران موجود همچنان توسط Backend مستقل کنترل می‌شود.</AppNotice>
      ) : null}

      <div className="table-shell table-scroll-shell user-management-table-shell">
        <div className="data-table user-table user-table-manage">
          <div className="table-row table-head"><span>شخص</span><span>حساب</span><span>سازمان</span><span>وضعیت</span><span>عملیات</span></div>
          {filtered.map((user) => {
            const manageable = canManageUser(user);
            const self = user.id === currentUser.id;
            return (
              <div className={`table-row ${user.is_active ? "" : "is-muted"}`} key={user.id}>
                <div><strong>{user.person_name}</strong><small>{user.username ?? "بدون username"}</small></div>
                <div><strong dir="ltr">{user.email}</strong><small>{user.last_login_at ? `آخرین ورود: ${new Date(user.last_login_at).toLocaleString("fa-IR")}` : "هنوز وارد نشده"}</small></div>
                <div className="org-tags">{user.organization_names.map((name) => <span key={name}>{name}</span>)}</div>
                <span className={`status-badge ${user.is_active ? "is-active" : "is-inactive"}`}>{user.is_active ? "فعال" : "غیرفعال"}</span>
                <div className="user-row-actions">
                  {manageable ? (
                    <>
                      <button type="button" className="secondary-action-button" onClick={() => openEdit(user)}>ویرایش</button>
                      <button type="button" className="secondary-action-button" onClick={() => openPassword(user)}>رمز جدید</button>
                      <button type="button" className={`status-action-button ${user.is_active ? "danger" : "success"}`} onClick={() => void toggleStatus(user)} disabled={busyId === user.id || (self && user.is_active)} title={self && user.is_active ? "حساب فعلی از این صفحه غیرفعال نمی‌شود." : undefined}>
                        {busyId === user.id ? "در حال ثبت…" : user.is_active ? "غیرفعال" : "فعال‌سازی"}
                      </button>
                    </>
                  ) : <span className="read-only-label">فقط مشاهده</span>}
                </div>
              </div>
            );
          })}
        </div>
        {filtered.length === 0 ? <div className="empty-state">کاربری با این فیلتر پیدا نشد.</div> : null}
      </div>

      {editor.mode !== "closed" ? (
        <div className="management-dialog-layer" role="presentation">
          <button type="button" className="management-dialog-backdrop" aria-label="بستن پنجره" onClick={() => !saving && closeEditor()} />
          <div className="management-dialog" role="dialog" aria-modal="true" aria-labelledby="user-editor-title">
            <div className="management-dialog-head">
              <div><span>User Management</span><h2 id="user-editor-title">{editor.mode === "create" ? "ساخت حساب کاربری" : editor.mode === "edit" ? "ویرایش حساب" : "تنظیم رمز عبور جدید"}</h2></div>
              <button type="button" onClick={closeEditor} disabled={saving}>بستن</button>
            </div>
            <form className="management-form" onSubmit={(event) => void submit(event)}>
              {editor.mode === "create" ? (
                <label><span>Person</span><select value={personId} onChange={(event) => onCandidateChange(event.target.value)} required>{candidates.map((person) => <option value={person.id} key={person.id}>{person.first_name} {person.last_name}</option>)}</select><small>هر Person فقط یک User می‌تواند داشته باشد.</small></label>
              ) : null}

              {editor.mode === "create" || editor.mode === "edit" ? (
                <>
                  <label><span>ایمیل ورود</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} dir="ltr" autoComplete="off" /></label>
                  <label><span>نام کاربری اختیاری</span><input value={username} onChange={(event) => setUsername(event.target.value)} maxLength={100} dir="ltr" autoComplete="off" /><small>Username نباید شامل @ باشد.</small></label>
                </>
              ) : null}

              {editor.mode === "create" || editor.mode === "password" ? (
                <>
                  <label><span>{editor.mode === "create" ? "رمز عبور اولیه" : "رمز عبور جدید"}</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} maxLength={256} autoComplete="new-password" /></label>
                  <label><span>تکرار رمز عبور</span><input type="password" value={passwordConfirm} onChange={(event) => setPasswordConfirm(event.target.value)} required minLength={12} maxLength={256} autoComplete="new-password" /><small>حداقل ۱۲ کاراکتر. رمز در state فقط تا پایان این عملیات نگه داشته می‌شود و به خروجی API/Audit نمی‌رود.</small></label>
                </>
              ) : null}

              {editor.mode === "edit" ? <div className="management-form-note">ویرایش حساب علاوه بر users.manage به کنترل ضد privilege-escalation در Backend وابسته است؛ ممکن است یک User قابل مشاهده باشد اما قابل ویرایش نباشد.</div> : null}
              <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={closeEditor} disabled={saving}>انصراف</button><button type="submit" className="primary-action-button" disabled={saving || (editor.mode === "create" && !personId)}>{saving ? "در حال ذخیره…" : "ذخیره"}</button></div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
