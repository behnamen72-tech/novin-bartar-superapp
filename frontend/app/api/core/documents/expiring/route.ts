import { NextRequest } from "next/server";
import { proxyAuthenticatedGet } from "@/lib/authenticated-backend";

export async function GET(request: NextRequest) {
  return proxyAuthenticatedGet("/documents/expiring", request);
}
