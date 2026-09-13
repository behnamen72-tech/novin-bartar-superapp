import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { rejectCrossSiteMutation } from "@/lib/request-security";
import {
  isSessionTokenPayload,
  setSessionCookies,
} from "@/lib/session";

type LoginBody = {
  login?: unknown;
  password?: unknown;
};

const MAX_LOGIN_BODY_BYTES = 8 * 1024;

function noStoreJson(payload: object, status = 200): NextResponse {
  return NextResponse.json(payload, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(request: NextRequest) {
  const rejected = rejectCrossSiteMutation(request);
  if (rejected) return rejected;

  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes("application/json")) {
    return noStoreJson({ detail: "درخواست ورود نامعتبر است." }, 415);
  }

  const declaredLength = Number(request.headers.get("content-length") ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_LOGIN_BODY_BYTES) {
    return noStoreJson({ detail: "درخواست ورود بیش از حد بزرگ است." }, 413);
  }

  let body: LoginBody;
  try {
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_LOGIN_BODY_BYTES) {
      return noStoreJson({ detail: "درخواست ورود بیش از حد بزرگ است." }, 413);
    }
    body = JSON.parse(raw) as LoginBody;
  } catch {
    return noStoreJson({ detail: "درخواست ورود نامعتبر است." }, 400);
  }

  const login = typeof body.login === "string" ? body.login.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";

  if (!login || !password || login.length > 320 || password.length > 1024) {
    return noStoreJson(
      { detail: "نام کاربری/ایمیل و رمز عبور لازم است." },
      400,
    );
  }

  const form = new URLSearchParams();
  form.set("username", login);
  form.set("password", password);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/auth/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form.toString(),
    });
  } catch {
    return noStoreJson(
      { detail: "سرویس ورود در حال حاضر در دسترس نیست." },
      502,
    );
  }

  if (!backendResponse.ok) {
    return noStoreJson(
      {
        detail:
          backendResponse.status === 401
            ? "اطلاعات ورود صحیح نیست."
            : "سرویس ورود در حال حاضر در دسترس نیست.",
      },
      backendResponse.status === 401 ? 401 : 502,
    );
  }

  const tokenPayload: unknown = await backendResponse.json().catch(() => null);
  if (!isSessionTokenPayload(tokenPayload)) {
    return noStoreJson(
      { detail: "پاسخ سرویس ورود معتبر نیست." },
      502,
    );
  }

  const response = noStoreJson({ ok: true });
  setSessionCookies(response, tokenPayload);
  return response;
}
