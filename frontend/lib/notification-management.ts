import type { NotificationSeverity } from "@/lib/core-types";

export function notificationSeverityLabel(severity: NotificationSeverity): string {
  switch (severity) {
    case "success":
      return "موفق";
    case "warning":
      return "هشدار";
    case "critical":
      return "بحرانی";
    default:
      return "اطلاع";
  }
}

export function notificationSeverityTone(
  severity: NotificationSeverity,
): "info" | "success" | "warning" | "critical" {
  return severity;
}

export function notificationSourceLabel(source: string): string {
  switch (source) {
    case "workflow":
      return "گردش‌کار";
    case "documents":
      return "اسناد";
    case "demo_seed":
      return "نسخه نمایشی";
    case "system":
      return "سیستم";
    default:
      return source;
  }
}
