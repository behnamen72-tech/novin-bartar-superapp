import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ customerId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { customerId } = await context.params;
  return proxyAuthenticatedGet(`/crm/customers/${encodeURIComponent(customerId)}`, request);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { customerId } = await context.params;
  return proxyAuthenticatedRequest(`/crm/customers/${encodeURIComponent(customerId)}`, request);
}
