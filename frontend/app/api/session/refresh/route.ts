import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { rejectCrossSiteMutation } from "@/lib/request-security";
import {
  clearSessionCookies,
  getRefreshToken,
  isSessionTokenPayload,
  setSessionCookies,
} from "@/lib/session";

function failedRefresh(status = 401): NextResponse {
  const response = NextResponse.json(
    { detail: "نشست کاربری معتبر نیست." },
    { status, headers: { "Cache-Control": "no-store" } },
  );
  clearSessionCookies(response);
  return response;
}

export async function POST(request: NextRequest) {
  const rejected = rejectCrossSiteMutation(request);
  if (rejected) return rejected;

  const refreshToken = await getRefreshToken();
  if (!refreshToken) return failedRefresh();

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    return NextResponse.json(
      { detail: "سرویس نشست در حال حاضر در دسترس نیست." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }

  if (backendResponse.status === 401) return failedRefresh();
  if (!backendResponse.ok) {
    return NextResponse.json(
      { detail: "سرویس نشست در حال حاضر در دسترس نیست." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }

  const payload: unknown = await backendResponse.json().catch(() => null);
  if (!isSessionTokenPayload(payload)) return failedRefresh(502);

  const response = NextResponse.json(
    { ok: true },
    { headers: { "Cache-Control": "no-store" } },
  );
  setSessionCookies(response, payload);
  return response;
}
