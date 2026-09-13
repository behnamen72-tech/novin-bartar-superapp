import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/authenticated-backend";
type RouteContext = { params: Promise<{ supplierId: string; noteId: string }> };
export async function PATCH(request: NextRequest, context: RouteContext) { const { supplierId, noteId } = await context.params; return proxyAuthenticatedRequest(`/suppliers/${encodeURIComponent(supplierId)}/notes/${encodeURIComponent(noteId)}`, request); }
