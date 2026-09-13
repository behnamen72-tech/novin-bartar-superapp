import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ positionId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { positionId } = await context.params;
  return proxyAuthenticatedRequest(`/hr/positions/${encodeURIComponent(positionId)}/status`, request);
}
