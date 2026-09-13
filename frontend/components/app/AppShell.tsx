"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { AccessAssignment, CurrentUser } from "@/lib/core-types";
import {
  getVisibleNavigation,
  navigationItems,
  type ViewKey,
} from "@/lib/navigation";

type AppShellProps = {
  user: CurrentUser;
  assignments: AccessAssignment[];
  permissions: string[];
  activeView: ViewKey;
  busy?: boolean;
  notificationUnreadCount?: number;
  children: ReactNode;
  onNavigate: (view: ViewKey) => void;
  onLogout: () => void;
};

export function AppShell({
  user,
  assignments,
  permissions,
  activeView,
  busy = false,
  notificationUnreadCount = 0,
  children,
  onNavigate,
  onLogout,
}: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const sections = useMemo(
    () => getVisibleNavigation(permissions),
    [permissions],
  );
  const currentItem =
    navigationItems.find((item) => item.key === activeView) ?? navigationItems[0];
  const organizations = new Set(assignments.map((item) => item.organization_id)).size;
  const identity = user.username ?? user.email;

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMobileOpen(false);
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [activeView]);

  function navigate(view: ViewKey) {
    setMobileOpen(false);
    onNavigate(view);
  }

  return (
    <main className="app-shell b63-shell">
      <a className="skip-link" href="#main-workspace">
        رفتن به محتوای اصلی
      </a>

      <aside className="sidebar desktop-sidebar" aria-label="منوی اصلی">
        <SidebarContent
          activeView={activeView}
          sections={sections}
          organizations={organizations}
          busy={busy}
          onNavigate={navigate}
        />
      </aside>

      {mobileOpen ? (
        <div className="mobile-nav-layer" role="presentation">
          <button
            type="button"
            className="mobile-nav-backdrop"
            aria-label="بستن منو"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="sidebar mobile-sidebar" aria-label="منوی اصلی موبایل">
            <div className="mobile-sidebar-head">
              <span>منوی مدیریت</span>
              <button type="button" onClick={() => setMobileOpen(false)}>
                بستن
              </button>
            </div>
            <SidebarContent
              activeView={activeView}
              sections={sections}
              organizations={organizations}
              busy={busy}
              onNavigate={navigate}
            />
          </aside>
        </div>
      ) : null}

      <section className="workspace" id="main-workspace" tabIndex={-1}>
        <header className="topbar b63-topbar">
          <div className="topbar-title-group">
            <button
              type="button"
              className="mobile-menu-button"
              aria-label="باز کردن منوی اصلی"
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(true)}
            >
              ☰
            </button>
            <div>
              <div className="breadcrumb" aria-label="مسیر صفحه">
                <span>نوین برتر</span>
                <b aria-hidden="true">/</b>
                <span>{currentItem.shortLabel}</span>
              </div>
              <h2>{currentItem.label}</h2>
              <p>{currentItem.eyebrow}</p>
            </div>
          </div>

          <div className="topbar-actions">
            <button
              type="button"
              className="global-search-button"
              aria-label="جستجوی سراسری"
              title="جستجوی سراسری"
              onClick={() => navigate("search")}
            >
              <span aria-hidden="true">⌕</span>
            </button>
            <button
              type="button"
              className={`notification-bell ${notificationUnreadCount > 0 ? "has-unread" : ""}`}
              aria-label={notificationUnreadCount > 0 ? `${notificationUnreadCount} اعلان خوانده‌نشده` : "اعلان‌ها"}
              title="اعلان‌ها"
              onClick={() => navigate("notifications")}
            >
              <span aria-hidden="true">🔔</span>
              {notificationUnreadCount > 0 ? (
                <b>{notificationUnreadCount > 99 ? "۹۹+" : notificationUnreadCount.toLocaleString("fa-IR")}</b>
              ) : null}
            </button>
            <div className="session-health" title="نشست کاربری فعال است">
              <i aria-hidden="true" />
              <span>نشست فعال</span>
            </div>
            <div className="user-chip">
              <div className="avatar" aria-hidden="true">
                {identity.slice(0, 2).toUpperCase()}
              </div>
              <div className="user-chip-copy">
                <strong>{user.username ?? "کاربر سیستم"}</strong>
                <span>{user.email}</span>
              </div>
              <button type="button" onClick={onLogout} disabled={busy}>
                خروج
              </button>
            </div>
          </div>
        </header>

        <div className="workspace-context">
          <span>Core Management</span>
          <b>•</b>
          <span>{organizations.toLocaleString("fa-IR")} محدوده سازمانی</span>
          <b>•</b>
          <span>{permissions.length.toLocaleString("fa-IR")} مجوز فعال</span>
        </div>

        <div className="workspace-body">{children}</div>
      </section>
    </main>
  );
}

type SidebarContentProps = {
  activeView: ViewKey;
  sections: ReturnType<typeof getVisibleNavigation>;
  organizations: number;
  busy: boolean;
  onNavigate: (view: ViewKey) => void;
};

function SidebarContent({
  activeView,
  sections,
  organizations,
  busy,
  onNavigate,
}: SidebarContentProps) {
  return (
    <>
      <div className="brand-row sidebar-brand">
        <div className="brand-mark small">NB</div>
        <div>
          <strong>انفرادی مارکت</strong>
          <span>مرکز مدیریت نوین برتر</span>
        </div>
      </div>

      <div className="sidebar-scope-card">
        <span>محدوده‌های قابل مدیریت</span>
        <strong>{organizations.toLocaleString("fa-IR")}</strong>
        <small>بر اساس Role و Organization Scope</small>
      </div>

      <nav>
        {sections.map((section) => (
          <div className="nav-section" key={section.label}>
            <span className="nav-section-label">{section.label}</span>
            <div className="nav-section-items">
              {section.items.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`nav-item ${activeView === item.key ? "active" : ""}`}
                  aria-current={activeView === item.key ? "page" : undefined}
                  disabled={busy && activeView !== item.key}
                  onClick={() => onNavigate(item.key)}
                >
                  <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                  <span>{item.shortLabel}</span>
                  {activeView === item.key ? (
                    <i className="active-nav-mark" aria-hidden="true" />
                  ) : null}
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span>نسخه توسعه</span>
        <strong>D3</strong>
      </div>
    </>
  );
}
