import { NextRequest, NextResponse } from "next/server";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function rejectCrossSiteMutation(request: NextRequest): NextResponse | null {
  if (!UNSAFE_METHODS.has(request.method.toUpperCase())) return null;

  const secFetchSite = request.headers.get("sec-fetch-site");
  if (secFetchSite && secFetchSite !== "same-origin" && secFetchSite !== "none") {
    return NextResponse.json({ detail: "Cross-site request rejected." }, { status: 403 });
  }

  const origin = request.headers.get("origin");
  if (!origin) {
    if (secFetchSite === "same-origin" || secFetchSite === "none") return null;
    return NextResponse.json({ detail: "Request origin is required." }, { status: 403 });
  }

  try {
    if (new URL(origin).origin !== request.nextUrl.origin) {
      return NextResponse.json({ detail: "Cross-site request rejected." }, { status: 403 });
    }
  } catch {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  }

  return null;
}
