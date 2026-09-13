import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ instanceId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { instanceId } = await context.params;
  return proxyAuthenticatedRequest(
    `/workflow/instances/${encodeURIComponent(instanceId)}/cancel`,
    request,
  );
}
