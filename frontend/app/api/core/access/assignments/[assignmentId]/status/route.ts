import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ assignmentId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { assignmentId } = await context.params;
  return proxyAuthenticatedRequest(`/access/assignments/${encodeURIComponent(assignmentId)}/status`, request);
}
