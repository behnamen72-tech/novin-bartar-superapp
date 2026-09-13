import type { DocumentExpirationItem } from "@/lib/core-types";

export function auditActionLabel(action: string): string {
  const labels: Record<string, string> = {
    "demo.seed_initialized": "آماده‌سازی داده نمایشی",
    "organization.created": "ایجاد سازمان",
    "organization.updated": "ویرایش سازمان",
    "organization.status.changed": "تغییر وضعیت سازمان",
    "person.created": "ایجاد شخص",
    "person.updated": "ویرایش شخص",
    "person.status.changed": "تغییر وضعیت شخص",
    "person.relationship.created": "افزودن رابطه سازمانی",
    "person.relationship.status.changed": "تغییر وضعیت رابطه سازمانی",
    "user.created": "ایجاد کاربر",
    "user.updated": "ویرایش کاربر",
    "user.status.changed": "تغییر وضعیت کاربر",
    "user.password.reset": "بازنشانی گذرواژه",
    "role.created": "ایجاد نقش",
    "role.updated": "ویرایش نقش",
    "role.status.changed": "تغییر وضعیت نقش",
    "role.assigned": "تخصیص نقش",
    "role.assignment.revoked": "لغو تخصیص نقش",
    "permission.granted": "افزودن مجوز به نقش",
    "permission.revoked": "حذف مجوز از نقش",
    "document.created": "ایجاد سند",
    "document.updated": "ویرایش سند",
    "document.version.created": "ثبت نسخه جدید سند",
    "document.downloaded": "دانلود سند",
    "document.linked": "اتصال سند",
    "document.unlinked": "قطع اتصال سند",
    "document.archived": "بایگانی سند",
    "document.restored": "بازگردانی سند",
    create: "ایجاد",
    update: "ویرایش",
    delete: "حذف",
  };
  return labels[action] ?? action;
}

export function resourceLabel(resourceType: string): string {
  const labels: Record<string, string> = {
    organization: "سازمان",
    person: "شخص",
    user: "کاربر",
    role: "نقش",
    user_role_assignment: "تخصیص نقش",
    document: "سند",
    document_category: "دسته سند",
    retention_policy: "سیاست نگهداری",
  };
  return labels[resourceType] ?? resourceType;
}

export function documentExpirationLabel(item: DocumentExpirationItem): string {
  if (item.expiration_state === "expired") {
    return `${Math.abs(item.days_remaining).toLocaleString("fa-IR")} روز گذشته`;
  }
  if (item.days_remaining === 0) return "امروز";
  if (item.expiration_state === "active") return "فعال";
  return `${item.days_remaining.toLocaleString("fa-IR")} روز مانده`;
}
