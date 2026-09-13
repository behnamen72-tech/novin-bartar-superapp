import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ documentId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { documentId } = await context.params;
  return proxyAuthenticatedRequest(`/documents/${encodeURIComponent(documentId)}/metadata`, request);
}
