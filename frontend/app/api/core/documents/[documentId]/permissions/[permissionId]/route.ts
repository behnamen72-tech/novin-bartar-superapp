import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ documentId: string; permissionId: string }> };

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { documentId, permissionId } = await context.params;
  return proxyAuthenticatedRequest(`/documents/${encodeURIComponent(documentId)}/permissions/${encodeURIComponent(permissionId)}`, request);
}
