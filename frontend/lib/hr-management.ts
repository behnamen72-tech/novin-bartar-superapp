import type { HREmploymentType, HRPositionItem } from "@/lib/core-types";

export const hrEmploymentTypeLabels: Record<HREmploymentType, string> = {
  permanent: "دائم",
  fixed_term: "مدت‌دار",
  part_time: "پاره‌وقت",
  contractor: "پیمانکاری",
  intern: "کارآموز",
  other: "سایر",
};

export const hrScopeLabels = {
  self: "فقط همین سازمان",
  self_and_descendants: "این سازمان و زیرمجموعه‌ها",
} as const;

export function hrPositionLabel(position: HRPositionItem): string {
  return position.name?.trim() || position.job_profile.title || position.code;
}

export function normalizeHrCode(value: string): string {
  return value.trim().toUpperCase().replace(/\s+/g, "-");
}
