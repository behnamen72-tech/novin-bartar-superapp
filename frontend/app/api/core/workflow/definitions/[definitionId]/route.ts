import { NextRequest } from "next/server";
import {
  proxyAuthenticatedGet,
  proxyAuthenticatedRequest,
} from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ definitionId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { definitionId } = await context.params;
  return proxyAuthenticatedGet(
    `/workflow/definitions/${encodeURIComponent(definitionId)}`,
    request,
  );
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { definitionId } = await context.params;
  return proxyAuthenticatedRequest(
    `/workflow/definitions/${encodeURIComponent(definitionId)}`,
    request,
  );
}
