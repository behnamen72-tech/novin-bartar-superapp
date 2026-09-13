import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

export async function POST(request: NextRequest) {
  return proxyAuthenticatedRequest("/notifications/read-all", request);
}
