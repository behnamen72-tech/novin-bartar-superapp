import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ customerId: string; noteId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { customerId, noteId } = await context.params;
  return proxyAuthenticatedRequest(`/crm/customers/${encodeURIComponent(customerId)}/notes/${encodeURIComponent(noteId)}`, request);
}
