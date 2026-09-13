import { NextRequest } from "next/server";
import { proxyAuthenticatedGet } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ instanceId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { instanceId } = await context.params;
  return proxyAuthenticatedGet(
    `/workflow/instances/${encodeURIComponent(instanceId)}`,
    request,
  );
}
