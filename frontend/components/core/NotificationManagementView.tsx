"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  NotificationItem,
  NotificationReadAllResult,
  NotificationUnreadCount,
} from "@/lib/core-types";
import {
  notificationSeverityLabel,
  notificationSeverityTone,
  notificationSourceLabel,
} from "@/lib/notification-management";
import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";

type NotificationManagementViewProps = {
  onUnreadCountChanged?: (count: number) => void;
};

type NoticeState = { tone: "success" | "error"; text: string } | null;

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "این اعلان دیگر در دسترس نیست.";
    if (error.status === 401) return "نشست کاربری پایان یافته است.";
  }
  return "انجام عملیات اعلان ناموفق بود.";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function NotificationManagementView({
  onUnreadCountChanged,
}: NotificationManagementViewProps) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState>(null);

  const unreadCount = useMemo(
    () => items.filter((item) => item.read_at === null).length,
    [items],
  );

  const publishUnreadCount = useCallback(
    async (fallback?: number) => {
      try {
        const result = await apiFetch<NotificationUnreadCount>(
          "/api/core/notifications/unread-count",
        );
        onUnreadCountChanged?.(result.unread_count);
      } catch {
        if (fallback !== undefined) onUnreadCountChanged?.(fallback);
      }
    },
    [onUnreadCountChanged],
  );

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const query = unreadOnly ? "?unread_only=true&limit=100" : "?limit=100";
      const result = await apiFetch<NotificationItem[]>(
        `/api/core/notifications${query}`,
      );
      setItems(result);
      await publishUnreadCount(result.filter((item) => item.read_at === null).length);
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [publishUnreadCount, unreadOnly]);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  async function setReadState(item: NotificationItem, read: boolean) {
    setBusyId(item.id);
    setNotice(null);
    try {
      const updated = await apiFetch<NotificationItem>(
        `/api/core/notifications/${encodeURIComponent(item.id)}/${read ? "read" : "unread"}`,
        { method: "POST" },
      );
      setItems((current) => {
        const next = unreadOnly && read
          ? current.filter((candidate) => candidate.id !== item.id)
          : current.map((candidate) => candidate.id === item.id ? updated : candidate);
        const localUnread = next.filter((candidate) => candidate.read_at === null).length;
        onUnreadCountChanged?.(localUnread);
        return next;
      });
      await publishUnreadCount();
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function markAllRead() {
    setBusyId("all");
    setNotice(null);
    try {
      const result = await apiFetch<NotificationReadAllResult>(
        "/api/core/notifications/read-all",
        { method: "POST" },
      );
      setItems((current) => unreadOnly
        ? []
        : current.map((item) => ({
            ...item,
            read_at: item.read_at ?? new Date().toISOString(),
          })),
      );
      onUnreadCountChanged?.(0);
      setNotice({
        tone: "success",
        text: result.marked_read > 0
          ? `${result.marked_read.toLocaleString("fa-IR")} اعلان خوانده شد.`
          : "اعلان خوانده‌نشده‌ای وجود ندارد.",
      });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function openNotification(item: NotificationItem) {
    if (item.read_at === null) {
      await setReadState(item, true);
    }
    if (item.action_path) {
      window.location.assign(item.action_path);
    }
  }

  return (
    <section className="notification-view">
      <div className="management-title notification-title-row">
        <div>
          <span>Notifications Core</span>
          <h1>اعلان‌های من</h1>
          <p>
            اعلان‌ها شخصی هستند؛ هر کاربر فقط اعلان‌های خودش را می‌بیند و مقصد هر اعلان هنگام باز شدن دوباره توسط Backend مجوزسنجی می‌شود.
          </p>
        </div>
        <div className="notification-title-actions">
          <button
            type="button"
            className="secondary-action"
            disabled={loading || busyId !== null}
            onClick={() => void loadNotifications()}
          >
            تازه‌سازی
          </button>
          <button
            type="button"
            className="primary-action"
            disabled={loading || busyId !== null || unreadCount === 0}
            onClick={() => void markAllRead()}
          >
            خواندن همه
          </button>
        </div>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      <div className="notification-toolbar panel-card">
        <div>
          <strong>{unreadCount.toLocaleString("fa-IR")}</strong>
          <span>خوانده‌نشده در این فهرست</span>
        </div>
        <label className="notification-filter-toggle">
          <input
            type="checkbox"
            checked={unreadOnly}
            disabled={loading || busyId !== null}
            onChange={(event) => setUnreadOnly(event.target.checked)}
          />
          <span>فقط خوانده‌نشده‌ها</span>
        </label>
      </div>

      {loading ? <AsyncState label="در حال دریافت اعلان‌ها…" /> : null}

      {!loading && items.length === 0 ? (
        <div className="panel-card empty-state notification-empty-state">
          {unreadOnly ? "اعلان خوانده‌نشده‌ای ندارید." : "هنوز اعلانی برای شما ثبت نشده است."}
        </div>
      ) : null}

      {!loading && items.length > 0 ? (
        <div className="notification-list">
          {items.map((item) => {
            const isUnread = item.read_at === null;
            const tone = notificationSeverityTone(item.severity);
            return (
              <article
                key={item.id}
                className={`panel-card notification-card ${isUnread ? "is-unread" : ""}`}
              >
                <div className={`notification-severity is-${tone}`} aria-hidden="true" />
                <div className="notification-copy">
                  <div className="notification-card-head">
                    <div>
                      <span>{notificationSourceLabel(item.source)}</span>
                      <b>•</b>
                      <span>{notificationSeverityLabel(item.severity)}</span>
                      {isUnread ? <em>جدید</em> : null}
                    </div>
                    <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
                  </div>
                  <h2>{item.title}</h2>
                  {item.body ? <p>{item.body}</p> : null}
                  <div className="notification-meta">
                    <span>{item.event_code}</span>
                    {item.resource_type && item.resource_id ? (
                      <span>{item.resource_type} · {item.resource_id.slice(0, 12)}</span>
                    ) : null}
                  </div>
                  <div className="notification-actions">
                    {item.action_path ? (
                      <button
                        type="button"
                        className="primary-action compact-action"
                        disabled={busyId !== null}
                        onClick={() => void openNotification(item)}
                      >
                        باز کردن
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="secondary-action compact-action"
                      disabled={busyId !== null}
                      onClick={() => void setReadState(item, isUnread)}
                    >
                      {isUnread ? "علامت‌گذاری خوانده‌شده" : "علامت‌گذاری خوانده‌نشده"}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
