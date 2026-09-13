import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ employmentId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { employmentId } = await context.params;
  return proxyAuthenticatedRequest(`/hr/employments/${encodeURIComponent(employmentId)}/status`, request);
}
