import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";
type RouteContext = { params: Promise<{ supplierId: string }> };
export async function POST(request: NextRequest, context: RouteContext) { const { supplierId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/status`, request); }
