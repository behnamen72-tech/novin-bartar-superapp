import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ personId: string; relationshipId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { personId, relationshipId } = await context.params;
  return proxyAuthenticatedRequest(
    `/people/${encodeURIComponent(personId)}/relationships/${encodeURIComponent(relationshipId)}/status`,
    request,
  );
}
