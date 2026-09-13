import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ definitionId: string; transitionId: string }> };

async function forward(request: NextRequest, context: RouteContext) {
  const { definitionId, transitionId } = await context.params;
  return proxyAuthenticatedRequest(
    `/workflow/definitions/${encodeURIComponent(definitionId)}/transitions/${encodeURIComponent(transitionId)}`,
    request,
  );
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return forward(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return forward(request, context);
}
