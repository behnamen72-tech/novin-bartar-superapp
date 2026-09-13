import { NextRequest } from "next/server";
import { proxyAuthenticatedGet } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ documentId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { documentId } = await context.params;
  return proxyAuthenticatedGet(`/documents/${encodeURIComponent(documentId)}`, request);
}
