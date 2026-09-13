import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { getAccessToken } from "@/lib/session";
import { rejectCrossSiteMutation } from "@/lib/request-security";

const SAFE_FORWARD_HEADERS = ["content-type", "accept"] as const;

function safeBackendDetail(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      return fallback;
    }
  }
  return fallback;
}

async function backendResponseToNext(response: Response): Promise<NextResponse> {
  if (response.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");

  if (response.ok) {
    if (isJson) {
      return NextResponse.json(payload, { status: response.status });
    }
    return new NextResponse(typeof payload === "string" ? payload : "", {
      status: response.status,
      headers: contentType ? { "Content-Type": contentType } : undefined,
    });
  }

  // Preserve expected client errors from the backend, but never relay arbitrary
  // internal 5xx bodies to the browser.
  if (response.status >= 400 && response.status < 500) {
    const fallback =
      response.status === 401
        ? "Unauthorized"
        : response.status === 403
          ? "Forbidden"
          : response.status === 404
            ? "Not found"
            : "Request rejected.";

    return NextResponse.json(
      { detail: safeBackendDetail(payload, fallback) },
      { status: response.status },
    );
  }

  return NextResponse.json(
    { detail: "Backend service is temporarily unavailable." },
    { status: 502 },
  );
}

function appendSearch(path: string, request?: NextRequest): string {
  if (!request || !request.nextUrl.search) {
    return path;
  }
  return `${path}${request.nextUrl.search}`;
}

export async function proxyAuthenticatedRequest(
  path: string,
  request: NextRequest,
): Promise<NextResponse> {
  const rejected = rejectCrossSiteMutation(request);
  if (rejected) return rejected;

  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);

  for (const header of SAFE_FORWARD_HEADERS) {
    const value = request.headers.get(header);
    if (value) headers.set(header, value);
  }

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  const body = hasBody ? await request.arrayBuffer() : undefined;

  try {
    const response = await backendFetch(appendSearch(path, request), {
      method,
      headers,
      body: body && body.byteLength > 0 ? body : undefined,
    });

    return backendResponseToNext(response);
  } catch {
    return NextResponse.json(
      { detail: "Backend service is temporarily unavailable." },
      { status: 502 },
    );
  }
}

export async function proxyAuthenticatedGet(
  path: string,
  request?: NextRequest,
): Promise<NextResponse> {
  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  try {
    const response = await backendFetch(appendSearch(path, request), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    return backendResponseToNext(response);
  } catch {
    return NextResponse.json(
      { detail: "Backend service is temporarily unavailable." },
      { status: 502 },
    );
  }
}

export async function proxyAuthenticatedDownload(
  path: string,
  request?: NextRequest,
): Promise<NextResponse> {
  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  try {
    const response = await backendFetch(appendSearch(path, request), {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/octet-stream, */*",
      },
    });

    if (!response.ok) {
      return backendResponseToNext(response);
    }

    const body = await response.arrayBuffer();
    const headers = new Headers();
    const contentType = response.headers.get("content-type");
    const contentDisposition = response.headers.get("content-disposition");
    const nosniff = response.headers.get("x-content-type-options");
    if (contentType) headers.set("Content-Type", contentType);
    if (contentDisposition) headers.set("Content-Disposition", contentDisposition);
    headers.set("Cache-Control", "no-store, private");
    headers.set("X-Content-Type-Options", nosniff ?? "nosniff");

    return new NextResponse(body, { status: response.status, headers });
  } catch {
    return NextResponse.json(
      { detail: "Backend service is temporarily unavailable." },
      { status: 502 },
    );
  }
}
