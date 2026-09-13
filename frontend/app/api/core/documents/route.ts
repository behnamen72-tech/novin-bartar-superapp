import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";

export async function GET(request: NextRequest) {
  return proxyAuthenticatedGet("/documents", request);
}

export async function POST(request: NextRequest) {
  return proxyAuthenticatedRequest("/documents", request);
}
