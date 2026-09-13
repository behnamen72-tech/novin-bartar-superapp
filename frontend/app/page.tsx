"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app/AppShell";
import { AuditCoreView } from "@/components/core/CoreViews";
import { PeopleManagementView } from "@/components/core/PeopleManagementView";
import { UserManagementView } from "@/components/core/UserManagementView";
import { OrganizationManagementView } from "@/components/core/OrganizationManagementView";
import { DocumentManagementView } from "@/components/core/DocumentManagementView";
import { AccessManagementView } from "@/components/core/AccessManagementView";
import { WorkflowManagementView } from "@/components/core/WorkflowManagementView";
import { NotificationManagementView } from "@/components/core/NotificationManagementView";
import { SearchManagementView } from "@/components/core/SearchManagementView";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { HRFoundationView } from "@/components/modules/HRFoundationView";
import { CustomerCRMView } from "@/components/modules/CustomerCRMView";
import { SupplierFoundationView } from "@/components/modules/SupplierFoundationView";
import { LoginScreen } from "@/components/session/LoginScreen";
import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  AccessOverviewItem,
  OrganizationItem,
  PersonItem,
  SessionSnapshot,
  UserItem,
  NotificationUnreadCount,
} from "@/lib/core-types";
import {
  isViewVisible,
  locationForView,
  type ViewKey,
  viewFromLocation,
} from "@/lib/navigation";
import type { AuditEventItem } from "@/components/core/AuditView";

type SessionState =
  | { status: "loading" }
  | { status: "signed_out" }
  | {
      status: "signed_in";
      user: SessionSnapshot["user"];
      assignments: SessionSnapshot["assignments"];
    };

export default function Home() {
  const [session, setSession] = useState<SessionState>({ status: "loading" });
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  const [organizations, setOrganizations] = useState<OrganizationItem[] | null>(null);
  const [people, setPeople] = useState<PersonItem[] | null>(null);
  const [users, setUsers] = useState<UserItem[] | null>(null);
  const [accessOverview, setAccessOverview] = useState<AccessOverviewItem[] | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[] | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState("");
  const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);

  const allPermissions = useMemo(() => {
    if (session.status !== "signed_in") return [];
    return Array.from(
      new Set(session.assignments.flatMap((item) => item.permissions)),
    ).sort();
  }, [session]);

  const clearLoadedData = useCallback(() => {
    setOrganizations(null);
    setPeople(null);
    setUsers(null);
    setAccessOverview(null);
    setAuditEvents(null);
    setActiveView("dashboard");
    setViewError("");
    setNotificationUnreadCount(0);
    if (typeof window !== "undefined") {
      window.history.replaceState({ view: "dashboard" }, "", "/");
    }
  }, []);

  const loadNotificationUnreadCount = useCallback(async () => {
    try {
      const result = await apiFetch<NotificationUnreadCount>(
        "/api/core/notifications/unread-count",
      );
      setNotificationUnreadCount(result.unread_count);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return;
      // Notification count is supplemental UI; a transient failure must not block the app shell.
    }
  }, []);

  const loadSession = useCallback(async () => {
    try {
      const snapshot = await apiFetch<SessionSnapshot>("/api/session/state");
      setSession({
        status: "signed_in",
        user: snapshot.user,
        assignments: snapshot.assignments,
      });
      setMessage("");
      void loadNotificationUnreadCount();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearLoadedData();
        setSession({ status: "signed_out" });
        return;
      }

      setMessage("ارتباط با Backend برقرار نشد. مطمئن شوید Backend اجرا شده است.");
      setSession({ status: "signed_out" });
    }
  }, [clearLoadedData, loadNotificationUnreadCount]);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  useEffect(() => {
    function handleSessionExpired() {
      clearLoadedData();
      setSession({ status: "signed_out" });
      setMessage("نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.");
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "visible" && session.status === "signed_in") {
        void loadSession();
        void loadNotificationUnreadCount();
      }
    }

    window.addEventListener("novin-bartar:session-expired", handleSessionExpired);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("novin-bartar:session-expired", handleSessionExpired);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [clearLoadedData, loadNotificationUnreadCount, loadSession, session.status]);

  useEffect(() => {
    if (session.status !== "signed_in") return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadNotificationUnreadCount();
      }
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [loadNotificationUnreadCount, session.status]);

  const loadViewData = useCallback(
    async (view: ViewKey) => {
      if (view === "dashboard") return;
      setViewLoading(true);
      setViewError("");

      try {
        if (view === "organizations" && organizations === null) {
          const includeInactive = allPermissions.includes("organization.manage");
          const path = includeInactive
            ? "/api/core/organizations?include_inactive=true"
            : "/api/core/organizations";
          setOrganizations(await apiFetch<OrganizationItem[]>(path));
        } else if (view === "people") {
          if (people === null) {
            setPeople(await apiFetch<PersonItem[]>("/api/core/people"));
          }
          if (organizations === null && allPermissions.includes("organization.read")) {
            setOrganizations(await apiFetch<OrganizationItem[]>("/api/core/organizations"));
          }
        } else if (view === "users") {
          if (users === null) {
            setUsers(await apiFetch<UserItem[]>("/api/core/users"));
          }
          if (people === null && (allPermissions.includes("people.read") || allPermissions.includes("people.manage"))) {
            setPeople(await apiFetch<PersonItem[]>("/api/core/people"));
          }
          if (organizations === null && (allPermissions.includes("organization.read") || allPermissions.includes("organization.manage"))) {
            setOrganizations(await apiFetch<OrganizationItem[]>("/api/core/organizations"));
          }
        } else if (view === "documents") {
          const requests: Promise<void>[] = [];
          if (organizations === null && (allPermissions.includes("organization.read") || allPermissions.includes("organization.manage"))) {
            requests.push(apiFetch<OrganizationItem[]>("/api/core/organizations?include_inactive=true").then(setOrganizations));
          }
          if (people === null && (allPermissions.includes("people.read") || allPermissions.includes("people.manage"))) {
            requests.push(apiFetch<PersonItem[]>("/api/core/people").then(setPeople));
          }
          await Promise.all(requests);
        } else if (view === "access") {
          const requests: Promise<void>[] = [];
          if (accessOverview === null) {
            requests.push(apiFetch<AccessOverviewItem[]>("/api/core/access-overview").then(setAccessOverview));
          }
          if (organizations === null && (allPermissions.includes("organization.read") || allPermissions.includes("organization.manage"))) {
            requests.push(apiFetch<OrganizationItem[]>("/api/core/organizations?include_inactive=true").then(setOrganizations));
          }
          if (people === null && (allPermissions.includes("people.read") || allPermissions.includes("people.manage"))) {
            requests.push(apiFetch<PersonItem[]>("/api/core/people").then(setPeople));
          }
          if (users === null && (allPermissions.includes("users.read") || allPermissions.includes("users.manage"))) {
            requests.push(apiFetch<UserItem[]>("/api/core/users").then(setUsers));
          }
          await Promise.all(requests);
        } else if (view === "audit" && auditEvents === null) {
          setAuditEvents(await apiFetch<AuditEventItem[]>("/api/core/audit"));
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 403) {
          setViewError("برای مشاهده این بخش مجوز کافی ندارید.");
        } else if (error instanceof ApiError && error.status === 401) {
          setSession({ status: "signed_out" });
          setViewError("");
        } else {
          setViewError("دریافت اطلاعات این بخش ناموفق بود. ارتباط با Backend را بررسی کنید.");
        }
      } finally {
        setViewLoading(false);
      }
    },
    [accessOverview, allPermissions, auditEvents, organizations, people, users],
  );

  const activateView = useCallback(
    (requested: ViewKey, historyMode: "push" | "replace" | "none" = "push") => {
      const allowed = isViewVisible(requested, allPermissions);
      const nextView = allowed ? requested : "dashboard";
      setActiveView(nextView);
      setViewError(
        allowed ? "" : "این بخش در محدوده دسترسی فعلی شما قابل مشاهده نیست.",
      );

      if (typeof window !== "undefined" && historyMode !== "none") {
        const url = locationForView(nextView);
        const state = { view: nextView };
        if (historyMode === "replace") {
          window.history.replaceState(state, "", url);
        } else {
          window.history.pushState(state, "", url);
        }
      }

      if (allowed) void loadViewData(nextView);
    },
    [allPermissions, loadViewData],
  );

  useEffect(() => {
    if (session.status !== "signed_in") return;

    const initialView = viewFromLocation(window.location.search);
    activateView(initialView, "replace");

    function handlePopState() {
      const requested = viewFromLocation(window.location.search);
      activateView(requested, "none");
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [activateView, session.status]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");

    try {
      const response = await fetch("/api/session/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
      });

      if (!response.ok) {
        const body = (await response.json()) as { detail?: string };
        setMessage(body.detail ?? "ورود ناموفق بود.");
        return;
      }

      setPassword("");
      await loadSession();
    } catch {
      setMessage("امکان ارتباط با برنامه وجود ندارد.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    setSubmitting(true);
    try {
      await fetch("/api/session/logout", { method: "POST" });
    } finally {
      clearLoadedData();
      setSession({ status: "signed_out" });
      setPassword("");
      setMessage("");
      setSubmitting(false);
    }
  }

  if (session.status === "loading") {
    return (
      <main className="loading-screen">
        <div className="brand-mark">NB</div>
        <AsyncState label="در حال آماده‌سازی سوپر اپ…" />
      </main>
    );
  }

  if (session.status === "signed_out") {
    return (
      <LoginScreen
        login={login}
        password={password}
        submitting={submitting}
        message={message}
        onLoginChange={setLogin}
        onPasswordChange={setPassword}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <AppShell
      user={session.user}
      assignments={session.assignments}
      permissions={allPermissions}
      activeView={activeView}
      busy={submitting}
      notificationUnreadCount={notificationUnreadCount}
      onNavigate={(view) => activateView(view, "push")}
      onLogout={() => void handleLogout()}
    >
      {viewError ? <AppNotice tone="error">{viewError}</AppNotice> : null}
      {viewLoading ? <AsyncState label="در حال دریافت اطلاعات…" /> : null}

      {!viewLoading && activeView === "dashboard" ? (
        <Dashboard
          assignments={session.assignments}
          allPermissions={allPermissions}
          onNavigate={(view) => activateView(view, "push")}
        />
      ) : null}
      {!viewLoading && activeView === "organizations" ? (
        <OrganizationManagementView
          organizations={organizations ?? []}
          assignments={session.assignments}
          onOrganizationChanged={(organization, created) => {
            setOrganizations((current) => {
              const items = current ?? [];
              if (created) return [...items, organization];
              return items.map((item) =>
                item.id === organization.id ? organization : item,
              );
            });
          }}
        />
      ) : null}
      {!viewLoading && activeView === "people" ? (
        <PeopleManagementView
          people={people ?? []}
          organizations={organizations ?? []}
          assignments={session.assignments}
          currentUser={session.user}
          onPersonChanged={(person, created) => {
            setPeople((current) => {
              const items = current ?? [];
              if (created) return [...items, person];
              return items.map((item) => item.id === person.id ? person : item);
            });
          }}
        />
      ) : null}
      {!viewLoading && activeView === "users" ? (
        <UserManagementView
          users={users ?? []}
          people={people ?? []}
          organizations={organizations ?? []}
          assignments={session.assignments}
          currentUser={session.user}
          onUserChanged={(user, created) => {
            setUsers((current) => {
              const items = current ?? [];
              if (created) return [...items, user];
              return items.map((item) => item.id === user.id ? user : item);
            });
          }}
        />
      ) : null}
      {!viewLoading && activeView === "documents" ? (
        <DocumentManagementView
          organizations={organizations ?? []}
          people={people ?? []}
          assignments={session.assignments}
          allPermissions={allPermissions}
        />
      ) : null}
      {!viewLoading && activeView === "workflow" ? (
        <WorkflowManagementView />
      ) : null}
      {!viewLoading && activeView === "notifications" ? (
        <NotificationManagementView
          onUnreadCountChanged={setNotificationUnreadCount}
        />
      ) : null}
      {!viewLoading && activeView === "search" ? (
        <SearchManagementView
          onNavigate={(view) => activateView(view, "push")}
        />
      ) : null}
      {!viewLoading && activeView === "hr" ? (
        <HRFoundationView />
      ) : null}
      {!viewLoading && activeView === "customers" ? (
        <CustomerCRMView />
      ) : null}
      {!viewLoading && activeView === "suppliers" ? (
        <SupplierFoundationView />
      ) : null}
      {!viewLoading && activeView === "access" ? (
        <AccessManagementView
          overview={accessOverview ?? []}
          organizations={organizations ?? []}
          people={people ?? []}
          users={users ?? []}
          assignments={session.assignments}
          allPermissions={allPermissions}
          onOverviewChanged={setAccessOverview}
        />
      ) : null}
      {!viewLoading && activeView === "audit" ? (
        <AuditCoreView events={auditEvents ?? []} />
      ) : null}
    </AppShell>
  );
}
