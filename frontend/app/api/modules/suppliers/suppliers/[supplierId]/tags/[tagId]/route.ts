import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";
type RouteContext = { params: Promise<{ supplierId: string; tagId: string }> };
export async function POST(request: NextRequest, context: RouteContext) { const { supplierId, tagId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/tags/${encodeURIComponent(tagId)}`, request); }
export async function DELETE(request: NextRequest, context: RouteContext) { const { supplierId, tagId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/tags/${encodeURIComponent(tagId)}`, request); }
