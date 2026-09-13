const BACKEND_API_URL =
  process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000/api/v1";

const DEFAULT_TIMEOUT_MS = 10_000;

function backendTimeoutMs(): number {
  const configured = Number(process.env.BACKEND_REQUEST_TIMEOUT_MS);
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_TIMEOUT_MS;
}

export async function backendFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`${BACKEND_API_URL}${path}`, {
    ...init,
    cache: "no-store",
    signal: init.signal ?? AbortSignal.timeout(backendTimeoutMs()),
  });
}
