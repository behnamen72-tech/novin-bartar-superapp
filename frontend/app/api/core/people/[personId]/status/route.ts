import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ personId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { personId } = await context.params;
  return proxyAuthenticatedRequest(`/people/${encodeURIComponent(personId)}/status`, request);
}
