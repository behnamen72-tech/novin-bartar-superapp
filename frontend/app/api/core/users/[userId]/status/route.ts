import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ userId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { userId } = await context.params;
  return proxyAuthenticatedRequest(`/users/${encodeURIComponent(userId)}/status`, request);
}
