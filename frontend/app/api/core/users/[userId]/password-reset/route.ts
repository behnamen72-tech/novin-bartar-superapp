import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ userId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { userId } = await context.params;
  return proxyAuthenticatedRequest(`/users/${encodeURIComponent(userId)}/password-reset`, request);
}
