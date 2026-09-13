import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";
type RouteContext = { params: Promise<{ supplierId: string; referenceId: string }> };
export async function DELETE(request: NextRequest, context: RouteContext) { const { supplierId, referenceId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/external-references/${encodeURIComponent(referenceId)}`, request); }
