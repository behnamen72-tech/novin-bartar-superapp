import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ customerId: string; tagId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { customerId, tagId } = await context.params;
  return proxyAuthenticatedRequest(`/crm/customers/${encodeURIComponent(customerId)}/tags/${encodeURIComponent(tagId)}`, request);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { customerId, tagId } = await context.params;
  return proxyAuthenticatedRequest(`/crm/customers/${encodeURIComponent(customerId)}/tags/${encodeURIComponent(tagId)}`, request);
}
