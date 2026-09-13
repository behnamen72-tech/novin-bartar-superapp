import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ documentId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { documentId } = await context.params;
  return proxyAuthenticatedGet(`/documents/${encodeURIComponent(documentId)}/permissions`, request);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { documentId } = await context.params;
  return proxyAuthenticatedRequest(`/documents/${encodeURIComponent(documentId)}/permissions`, request);
}
