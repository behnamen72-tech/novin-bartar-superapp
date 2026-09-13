import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ customerId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { customerId } = await context.params;
  return proxyAuthenticatedRequest(`/crm/customers/${encodeURIComponent(customerId)}/status`, request);
}
