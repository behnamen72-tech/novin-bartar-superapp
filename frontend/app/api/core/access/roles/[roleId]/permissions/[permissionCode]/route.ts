import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ roleId: string; permissionCode: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { roleId, permissionCode } = await context.params;
  return proxyAuthenticatedRequest(`/access/roles/${encodeURIComponent(roleId)}/permissions/${encodeURIComponent(permissionCode)}`, request);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { roleId, permissionCode } = await context.params;
  return proxyAuthenticatedRequest(`/access/roles/${encodeURIComponent(roleId)}/permissions/${encodeURIComponent(permissionCode)}`, request);
}
