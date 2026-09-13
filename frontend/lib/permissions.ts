const permissionLabels: Record<string, string> = {
  "organization.read": "مشاهده سازمان‌ها",
  "organization.manage": "مدیریت سازمان‌ها",
  "people.read": "مشاهده اشخاص",
  "people.manage": "مدیریت اشخاص",
  "users.read": "مشاهده کاربران",
  "users.manage": "مدیریت کاربران",
  "access.read": "مشاهده دسترسی‌ها",
  "access.manage": "مدیریت دسترسی‌ها",
  "audit.read": "مشاهده تاریخچه",
  "documents.read": "مشاهده اسناد",
  "documents.manage": "مدیریت اسناد",
  "workflow.read": "مشاهده گردش‌کارها",
  "workflow.manage": "مدیریت گردش‌کارها",
  "workflow.execute": "اجرای گردش‌کارها",
  "crm.customer.read": "مشاهده CRM مشتریان",
  "crm.customer.manage": "مدیریت CRM مشتریان",
  "crm.customer.notes.read": "مشاهده یادداشت مشتریان",
  "crm.customer.notes.manage": "مدیریت یادداشت مشتریان",
  "crm.customer.assign": "تخصیص مسئول مشتری",
  "crm.customer.tags.manage": "مدیریت برچسب مشتری",
  "crm.customer.commerce_activity.read": "مشاهده فعالیت فروشگاه مشتری",
  "supplier.read": "مشاهده تأمین‌کنندگان",
  "supplier.manage": "مدیریت تأمین‌کنندگان",
  "supplier.representative.read": "مشاهده نمایندگان تأمین‌کننده",
  "supplier.representative.manage": "مدیریت نمایندگان تأمین‌کننده",
  "supplier.representative.contact.read": "مشاهده اطلاعات تماس نمایندگان",
  "supplier.notes.read": "مشاهده یادداشت تأمین‌کنندگان",
  "supplier.notes.manage": "مدیریت یادداشت تأمین‌کنندگان",
  "supplier.assign": "تخصیص مسئول تأمین‌کننده",
  "supplier.tags.catalog.manage": "مدیریت کاتالوگ برچسب تأمین‌کننده",
  "supplier.tags.assign": "اختصاص برچسب تأمین‌کننده",
  "supplier.external_reference.read": "مشاهده شناسه‌های خارجی تأمین‌کننده",
  "supplier.external_reference.manage": "مدیریت شناسه‌های خارجی تأمین‌کننده",
};

export function permissionLabel(permission: string): string {
  return permissionLabels[permission] ?? permission;
}

export function hasAnyPermission(
  permissions: readonly string[],
  required: readonly string[],
): boolean {
  const available = new Set(permissions);
  return required.some((permission) => available.has(permission));
}
