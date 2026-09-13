import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = {
  params: Promise<{ organizationId: string }>;
};

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { organizationId } = await context.params;
  return proxyAuthenticatedRequest(
    `/organizations/${encodeURIComponent(organizationId)}/status`,
    request,
  );
}
