import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const ACCESS_TOKEN_COOKIE = "novin_bartar_access_token";
export const REFRESH_TOKEN_COOKIE = "novin_bartar_refresh_token";

export type SessionTokenPayload = {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  refresh_expires_in: number;
};

const isProduction = process.env.NODE_ENV === "production";

function baseCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: isProduction,
    maxAge,
  };
}

export async function getAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(ACCESS_TOKEN_COOKIE)?.value ?? null;
}

export async function getRefreshToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(REFRESH_TOKEN_COOKIE)?.value ?? null;
}

export function setSessionCookies(
  response: NextResponse,
  token: SessionTokenPayload,
): void {
  response.cookies.set(ACCESS_TOKEN_COOKIE, token.access_token, {
    ...baseCookieOptions(token.expires_in),
    path: "/",
  });
  response.cookies.set(REFRESH_TOKEN_COOKIE, token.refresh_token, {
    ...baseCookieOptions(token.refresh_expires_in),
    // The refresh credential is only sent to session-management routes, not to
    // ordinary Core BFF endpoints.
    path: "/api/session",
  });
}

export function clearSessionCookies(response: NextResponse): void {
  response.cookies.set(ACCESS_TOKEN_COOKIE, "", {
    ...baseCookieOptions(0),
    path: "/",
  });
  response.cookies.set(REFRESH_TOKEN_COOKIE, "", {
    ...baseCookieOptions(0),
    path: "/api/session",
  });
}

export function isSessionTokenPayload(value: unknown): value is SessionTokenPayload {
  if (!value || typeof value !== "object") return false;
  const payload = value as Partial<SessionTokenPayload>;
  return (
    typeof payload.access_token === "string" &&
    payload.access_token.length > 0 &&
    payload.token_type === "bearer" &&
    Number.isInteger(payload.expires_in) &&
    (payload.expires_in ?? 0) > 0 &&
    typeof payload.refresh_token === "string" &&
    payload.refresh_token.length > 0 &&
    Number.isInteger(payload.refresh_expires_in) &&
    (payload.refresh_expires_in ?? 0) > 0
  );
}
