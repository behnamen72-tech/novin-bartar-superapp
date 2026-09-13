"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { SearchEntityType, SearchResponse, SearchResultItem } from "@/lib/core-types";
import type { ViewKey } from "@/lib/navigation";

type SearchManagementViewProps = {
  onNavigate: (view: ViewKey) => void;
};

type Filter = "all" | SearchEntityType;

const typeLabels: Record<SearchEntityType, string> = {
  organization: "سازمان",
  person: "شخص",
  document: "سند",
  customer: "مشتری",
  supplier: "تأمین‌کننده",
};

const targetViews: Record<SearchEntityType, ViewKey> = {
  organization: "organizations",
  person: "people",
  document: "documents",
  customer: "customers",
  supplier: "suppliers",
};

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "نشست کاربری پایان یافته است.";
    if (error.status === 422) return "عبارت جستجو باید حداقل دو کاراکتر باشد.";
  }
  return "جستجو انجام نشد. ارتباط با Backend را بررسی کنید.";
}

function SearchResultCard({
  item,
  onNavigate,
}: {
  item: SearchResultItem;
  onNavigate: (view: ViewKey) => void;
}) {
  return (
    <article className="panel-card search-result-card">
      <div className={`search-result-icon is-${item.entity_type}`} aria-hidden="true">
        {item.entity_type === "organization" ? "OR" : item.entity_type === "person" ? "PE" : item.entity_type === "document" ? "DO" : item.entity_type === "customer" ? "CR" : "SP"}
      </div>
      <div className="search-result-copy">
        <div className="search-result-head">
          <span>{typeLabels[item.entity_type]}</span>
          {item.organization_name ? <small>{item.organization_name}</small> : null}
        </div>
        <h2>{item.title}</h2>
        {item.subtitle ? <p>{item.subtitle}</p> : null}
      </div>
      <button
        type="button"
        className="secondary-action compact-action"
        onClick={() => onNavigate(targetViews[item.entity_type])}
      >
        باز کردن بخش
      </button>
    </article>
  );
}

export function SearchManagementView({ onNavigate }: SearchManagementViewProps) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const visibleResults = useMemo(() => {
    if (!response) return [];
    return filter === "all"
      ? response.results
      : response.results.filter((item) => item.entity_type === filter);
  }, [filter, response]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim().replace(/\s+/g, " ");
    if (normalized.length < 2) {
      setError("حداقل دو کاراکتر برای جستجو وارد کنید.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const result = await apiFetch<SearchResponse>(
        `/api/core/search?q=${encodeURIComponent(normalized)}&limit_per_type=12`,
      );
      setResponse(result);
    } catch (searchError) {
      setError(errorText(searchError));
    } finally {
      setLoading(false);
    }
  }

  const total = response?.results.length ?? 0;

  return (
    <section className="search-view">
      <div className="search-title-row">
        <div>
          <span className="page-eyebrow">Search Core</span>
          <h1>جستجوی سراسری</h1>
          <p>
            نتیجه فقط از داده‌هایی برمی‌گردد که حساب فعلی واقعاً مجوز مشاهده آن‌ها را دارد.
          </p>
        </div>
      </div>

      <form className="panel-card search-form" onSubmit={submit}>
        <label htmlFor="global-search-input">عبارت جستجو</label>
        <div>
          <input
            id="global-search-input"
            value={query}
            maxLength={100}
            placeholder="نام شخص، سازمان، سند، مشتری یا تأمین‌کننده…"
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit" className="primary-action" disabled={loading}>
            {loading ? "در حال جستجو…" : "جستجو"}
          </button>
        </div>
        <small>حداقل ۲ کاراکتر؛ حداکثر ۱۲ نتیجه از هر حوزه.</small>
      </form>

      {error ? <AppNotice tone="error">{error}</AppNotice> : null}
      {loading ? <AsyncState label="در حال جستجو در داده‌های مجاز…" /> : null}

      {!loading && response ? (
        <>
          <div className="search-summary panel-card">
            <div>
              <strong>{total.toLocaleString("fa-IR")}</strong>
              <span>نتیجه برای «{response.query}»</span>
            </div>
            <div className="search-filters" role="group" aria-label="فیلتر نوع نتیجه">
              <button
                type="button"
                className={filter === "all" ? "active" : ""}
                onClick={() => setFilter("all")}
              >
                همه
              </button>
              {(["organization", "person", "document", "customer", "supplier"] as SearchEntityType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  className={filter === type ? "active" : ""}
                  onClick={() => setFilter(type)}
                >
                  {typeLabels[type]} ({response.counts[type] ?? 0})
                </button>
              ))}
            </div>
          </div>

          {visibleResults.length === 0 ? (
            <div className="panel-card empty-state search-empty-state">
              نتیجه‌ای در محدوده دسترسی فعلی پیدا نشد.
            </div>
          ) : (
            <div className="search-results">
              {visibleResults.map((item) => (
                <SearchResultCard key={`${item.entity_type}:${item.id}`} item={item} onNavigate={onNavigate} />
              ))}
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
