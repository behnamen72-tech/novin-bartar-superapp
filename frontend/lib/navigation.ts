import { hasAnyPermission } from "@/lib/permissions";

export type ViewKey =
  | "dashboard"
  | "organizations"
  | "people"
  | "users"
  | "documents"
  | "workflow"
  | "notifications"
  | "search"
  | "hr"
  | "customers"
  | "suppliers"
  | "access"
  | "audit";

export type NavigationItem = {
  key: ViewKey;
  label: string;
  eyebrow: string;
  shortLabel: string;
  icon: string;
  requiredAny?: readonly string[];
};

export type NavigationSection = {
  label: string;
  items: readonly NavigationItem[];
};

export const navigationSections: readonly NavigationSection[] = [
  {
    label: "مرکز مدیریت",
    items: [
      {
        key: "dashboard",
        label: "داشبورد مدیریت",
        shortLabel: "داشبورد",
        eyebrow: "Management Overview",
        icon: "DB",
      },
      {
        key: "organizations",
        label: "سازمان‌ها",
        shortLabel: "سازمان‌ها",
        eyebrow: "Organization Core",
        icon: "OR",
        requiredAny: ["organization.read", "organization.manage"],
      },
      {
        key: "people",
        label: "اشخاص",
        shortLabel: "اشخاص",
        eyebrow: "People Core",
        icon: "PE",
        requiredAny: ["people.read", "people.manage"],
      },
      {
        key: "users",
        label: "کاربران",
        shortLabel: "کاربران",
        eyebrow: "Identity Core",
        icon: "US",
        requiredAny: ["users.read", "users.manage"],
      },
      {
        key: "documents",
        label: "اسناد",
        shortLabel: "اسناد",
        eyebrow: "Documents Core",
        icon: "DO",
        requiredAny: ["documents.read", "documents.manage"],
      },
      {
        key: "workflow",
        label: "گردش‌کار",
        shortLabel: "گردش‌کار",
        eyebrow: "Workflow Core",
        icon: "WF",
        requiredAny: ["workflow.read", "workflow.manage", "workflow.execute"],
      },
      {
        key: "notifications",
        label: "اعلان‌ها",
        shortLabel: "اعلان‌ها",
        eyebrow: "Notifications Core",
        icon: "NT",
      },
      {
        key: "search",
        label: "جستجوی سراسری",
        shortLabel: "جستجو",
        eyebrow: "Search Core",
        icon: "SE",
      },
      {
        key: "access",
        label: "دسترسی‌ها",
        shortLabel: "دسترسی‌ها",
        eyebrow: "Authorization Core",
        icon: "AC",
        requiredAny: ["access.read", "access.manage"],
      },
    ],
  },
  {
    label: "پایه‌های کسب‌وکار",
    items: [
      {
        key: "hr",
        label: "منابع انسانی",
        shortLabel: "منابع انسانی",
        eyebrow: "HR Foundation",
        icon: "HR",
        requiredAny: ["hr.read", "hr.manage"],
      },
      {
        key: "customers",
        label: "مشتریان و CRM",
        shortLabel: "مشتریان",
        eyebrow: "Customer CRM Foundation",
        icon: "CR",
        requiredAny: [
          "crm.customer.read",
          "crm.customer.manage",
          "crm.customer.notes.read",
          "crm.customer.notes.manage",
          "crm.customer.assign",
          "crm.customer.tags.manage",
          "crm.customer.commerce_activity.read",
        ],
      },
      {
        key: "suppliers",
        label: "تأمین‌کنندگان",
        shortLabel: "تأمین‌کنندگان",
        eyebrow: "Suppliers Foundation",
        icon: "SP",
        requiredAny: [
          "supplier.read",
          "supplier.manage",
          "supplier.representative.read",
          "supplier.representative.manage",
          "supplier.representative.contact.read",
          "supplier.notes.read",
          "supplier.notes.manage",
          "supplier.assign",
          "supplier.tags.catalog.manage",
          "supplier.tags.assign",
          "supplier.external_reference.read",
          "supplier.external_reference.manage",
        ],
      },
    ],
  },
  {
    label: "نظارت",
    items: [
      {
        key: "audit",
        label: "تاریخچه فعالیت",
        shortLabel: "تاریخچه",
        eyebrow: "Immutable Audit",
        icon: "AU",
        requiredAny: ["audit.read"],
      },
    ],
  },
];

export const navigationItems = navigationSections.flatMap((section) => section.items);

export const viewLabels: Record<ViewKey, string> = Object.fromEntries(
  navigationItems.map((item) => [item.key, item.label]),
) as Record<ViewKey, string>;

export function isViewKey(value: string | null): value is ViewKey {
  return navigationItems.some((item) => item.key === value);
}

export function getVisibleNavigation(
  permissions: readonly string[],
): NavigationSection[] {
  return navigationSections
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) =>
          !item.requiredAny || hasAnyPermission(permissions, item.requiredAny),
      ),
    }))
    .filter((section) => section.items.length > 0);
}

export function isViewVisible(view: ViewKey, permissions: readonly string[]): boolean {
  const item = navigationItems.find((candidate) => candidate.key === view);
  if (!item) return false;
  return !item.requiredAny || hasAnyPermission(permissions, item.requiredAny);
}

export function viewFromLocation(search: string): ViewKey {
  const requested = new URLSearchParams(search).get("view");
  return isViewKey(requested) ? requested : "dashboard";
}

export function locationForView(view: ViewKey): string {
  return view === "dashboard" ? "/" : `/?view=${encodeURIComponent(view)}`;
}
