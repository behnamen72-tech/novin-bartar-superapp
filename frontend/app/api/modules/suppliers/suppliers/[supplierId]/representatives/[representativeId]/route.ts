import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";
type RouteContext = { params: Promise<{ supplierId: string; representativeId: string }> };
export async function PATCH(request: NextRequest, context: RouteContext) { const { supplierId, representativeId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/representatives/${encodeURIComponent(representativeId)}`, request); }
