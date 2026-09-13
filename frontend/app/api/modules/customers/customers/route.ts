import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

export async function GET(request: NextRequest) {
  return proxyAuthenticatedGet("/crm/customers", request);
}

export async function POST(request: NextRequest) {
  return proxyAuthenticatedRequest("/crm/customers", request);
}
