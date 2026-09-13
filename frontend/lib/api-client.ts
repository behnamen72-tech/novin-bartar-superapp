export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type ErrorPayload = {
  detail?: unknown;
};

type RefreshResult = "refreshed" | "expired" | "unavailable";

let refreshInFlight: Promise<RefreshResult> | null = null;

function detailFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as ErrorPayload).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            const msg = (item as { msg?: unknown }).msg;
            return typeof msg === "string" ? msg : "";
          }
          return "";
        })
        .filter(Boolean)
        .join("، ") || fallback;
    }
  }

  return fallback;
}

function announceExpiredSession(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("novin-bartar:session-expired"));
  }
}

async function refreshBrowserSession(): Promise<RefreshResult> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch("/api/session/refresh", {
        method: "POST",
        cache: "no-store",
      });
      if (response.ok) return "refreshed";
      if (response.status === 401) return "expired";
      return "unavailable";
    } catch {
      return "unavailable";
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function performFetch(
  input: RequestInfo | URL,
  init: RequestInit,
): Promise<Response> {
  return fetch(input, { ...init, cache: "no-store" });
}

export async function apiFetch<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<T> {
  let response = await performFetch(input, init);

  if (response.status === 401 && response.headers.get("X-Session-State") !== "none") {
    const refreshResult = await refreshBrowserSession();
    if (refreshResult === "refreshed") {
      response = await performFetch(input, init);
    } else if (refreshResult === "expired") {
      announceExpiredSession();
    } else {
      throw new ApiError(503, "Session service is temporarily unavailable.");
    }

    if (response.status === 401) {
      announceExpiredSession();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");

  if (!response.ok) {
    throw new ApiError(
      response.status,
      detailFromPayload(payload, `Request failed: ${response.status}`),
    );
  }

  return payload as T;
}

export type DownloadPayload = {
  blob: Blob;
  fileName: string;
};

function fileNameFromDisposition(value: string | null): string {
  if (!value) return "document";

  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1].replace(/^"|"$/g, ""));
    } catch {
      return utf8[1].replace(/^"|"$/g, "");
    }
  }

  const plain = value.match(/filename="?([^";]+)"?/i);
  return plain?.[1]?.trim() || "document";
}

export async function apiDownload(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<DownloadPayload> {
  let response = await performFetch(input, init);

  if (response.status === 401 && response.headers.get("X-Session-State") !== "none") {
    const refreshResult = await refreshBrowserSession();
    if (refreshResult === "refreshed") {
      response = await performFetch(input, init);
    } else if (refreshResult === "expired") {
      announceExpiredSession();
    } else {
      throw new ApiError(503, "Session service is temporarily unavailable.");
    }

    if (response.status === 401) announceExpiredSession();
  }

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json")
      ? await response.json().catch(() => null)
      : await response.text().catch(() => "");
    throw new ApiError(
      response.status,
      detailFromPayload(payload, `Request failed: ${response.status}`),
    );
  }

  return {
    blob: await response.blob(),
    fileName: fileNameFromDisposition(response.headers.get("content-disposition")),
  };
}

