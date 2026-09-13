import { proxyAuthenticatedGet } from "@/lib/authenticated-backend";

export async function GET() {
  return proxyAuthenticatedGet("/crm/organizations");
}
