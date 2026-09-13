import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { rejectCrossSiteMutation } from "@/lib/request-security";
import {
  clearSessionCookies,
  getRefreshToken,
} from "@/lib/session";

export async function POST(request: NextRequest) {
  const rejected = rejectCrossSiteMutation(request);
  if (rejected) return rejected;

  const refreshToken = await getRefreshToken();

  if (refreshToken) {
    try {
      await backendFetch("/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Local logout must still succeed if the backend is temporarily unavailable.
      // The server-side refresh token will expire naturally if revocation could not
      // be delivered; the browser credentials are always removed below.
    }
  }

  const response = new NextResponse(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
  clearSessionCookies(response);
  return response;
}
