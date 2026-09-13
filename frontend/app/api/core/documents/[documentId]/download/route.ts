import { NextRequest } from "next/server";
import { proxyAuthenticatedDownload } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ documentId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { documentId } = await context.params;
  return proxyAuthenticatedDownload(`/documents/${encodeURIComponent(documentId)}/download`, request);
}
