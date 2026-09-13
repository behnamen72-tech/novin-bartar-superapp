import type {
  CustomerCommercialStatus,
  CustomerCRMSource,
  CustomerCRMType,
} from "@/lib/core-types";

export const customerTypeLabels: Record<CustomerCRMType, string> = {
  individual: "فردی",
  household: "خانوار",
  business: "کسب‌وکار",
  retail: "خرده‌فروش",
  wholesale: "عمده‌فروش",
  other: "سایر",
};

export const customerStatusLabels: Record<CustomerCommercialStatus, string> = {
  prospect: "سرنخ",
  active: "فعال",
  inactive: "غیرفعال",
  blocked: "مسدود CRM",
  archived: "بایگانی",
};

export const customerSourceLabels: Record<CustomerCRMSource, string> = {
  manual: "دستی",
  commerce_activity: "فعالیت فروشگاه",
  phone_order: "سفارش تلفنی",
  import: "ورود گروهی",
  other: "سایر",
};
