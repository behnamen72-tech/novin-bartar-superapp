import { NextRequest } from "next/server";
import { proxyAuthenticatedGet, proxyAuthenticatedRequest } from "@/lib/authenticated-backend";
type RouteContext = { params: Promise<{ supplierId: string }> };
export async function GET(request: NextRequest, context: RouteContext) { const { supplierId } = await context.params; return proxyAuthenticatedGet(`/suppliers/${encodeURIComponent(supplierId)}/representatives`, request); }
export async function POST(request: NextRequest, context: RouteContext) { const { supplierId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/representatives`, request); }
