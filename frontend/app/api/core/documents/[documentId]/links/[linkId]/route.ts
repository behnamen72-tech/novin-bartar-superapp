import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ documentId: string; linkId: string }> };

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { documentId, linkId } = await context.params;
  return proxyAuthenticatedRequest(
    `/documents/${encodeURIComponent(documentId)}/links/${encodeURIComponent(linkId)}`,
    request,
  );
}
