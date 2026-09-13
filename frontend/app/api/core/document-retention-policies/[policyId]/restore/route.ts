import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ policyId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { policyId } = await context.params;
  return proxyAuthenticatedRequest(`/document-retention-policies/${encodeURIComponent(policyId)}/restore`, request);
}
