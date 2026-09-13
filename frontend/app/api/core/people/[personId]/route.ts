import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ personId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { personId } = await context.params;
  return proxyAuthenticatedGet(`/people/${encodeURIComponent(personId)}`, request);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { personId } = await context.params;
  return proxyAuthenticatedRequest(`/people/${encodeURIComponent(personId)}`, request);
}
