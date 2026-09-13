import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ userId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { userId } = await context.params;
  return proxyAuthenticatedGet(`/users/${encodeURIComponent(userId)}`, request);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { userId } = await context.params;
  return proxyAuthenticatedRequest(`/users/${encodeURIComponent(userId)}`, request);
}
