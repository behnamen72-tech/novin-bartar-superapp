import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { getAccessToken, getRefreshToken } from "@/lib/session";

function sessionError(
  status: number,
  detail: string,
  extraHeaders: Record<string, string> = {},
): NextResponse {
  return NextResponse.json(
    { detail },
    {
      status,
      headers: { "Cache-Control": "no-store", ...extraHeaders },
    },
  );
}

export async function GET() {
  const token = await getAccessToken();
  if (!token) {
    const refreshToken = await getRefreshToken();
    if (!refreshToken) {
      return sessionError(401, "Unauthorized", { "X-Session-State": "none" });
    }
    return sessionError(401, "Unauthorized");
  }

  const headers = { Authorization: `Bearer ${token}` };

  try {
    const meResponse = await backendFetch("/auth/me", { headers });
    if (meResponse.status === 401) return sessionError(401, "Unauthorized");
    if (!meResponse.ok) {
      return sessionError(502, "Backend service is temporarily unavailable.");
    }

    const accessResponse = await backendFetch("/access/me", { headers });
    if (accessResponse.status === 401) return sessionError(401, "Unauthorized");
    if (!accessResponse.ok) {
      return sessionError(502, "Backend service is temporarily unavailable.");
    }

    const [user, assignments] = await Promise.all([
      meResponse.json(),
      accessResponse.json(),
    ]);

    return NextResponse.json(
      { user, assignments },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return sessionError(502, "Backend service is temporarily unavailable.");
  }
}
