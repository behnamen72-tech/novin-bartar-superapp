import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ categoryId: string }> };

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { categoryId } = await context.params;
  return proxyAuthenticatedRequest(`/document-categories/${encodeURIComponent(categoryId)}`, request);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { categoryId } = await context.params;
  return proxyAuthenticatedRequest(`/document-categories/${encodeURIComponent(categoryId)}`, request);
}
