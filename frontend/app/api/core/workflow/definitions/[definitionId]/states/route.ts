import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ definitionId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { definitionId } = await context.params;
  return proxyAuthenticatedRequest(
    `/workflow/definitions/${encodeURIComponent(definitionId)}/states`,
    request,
  );
}
