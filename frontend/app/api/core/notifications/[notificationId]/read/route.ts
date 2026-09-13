import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

type RouteContext = { params: Promise<{ notificationId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  const { notificationId } = await context.params;
  return proxyAuthenticatedRequest(
    `/notifications/${encodeURIComponent(notificationId)}/read`,
    request,
  );
}
