import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ roleId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { roleId } = await context.params;
  return proxyAuthenticatedRequest(`/access/roles/${encodeURIComponent(roleId)}`, request);
}
