import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ profileId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { profileId } = await context.params;
  return proxyAuthenticatedRequest(`/hr/job-profiles/${encodeURIComponent(profileId)}`, request);
}
