# Phase B6.1 — Frontend Foundation

B6.1 starts the operational user-experience phase on top of the Claude-approved B5.6 backend.

## Scope delivered

- Existing Persian RTL demo UI preserved as the starting surface.
- Shared browser API client with typed `ApiError` and safe JSON/204 handling.
- Generalized authenticated Next.js BFF proxy for future read/write routes.
  - JWT remains server-side in the HttpOnly cookie.
  - Only safe request headers are forwarded.
  - Expected backend 4xx statuses are preserved.
  - Arbitrary backend 5xx response bodies are not exposed to the browser.
  - Query strings are preserved for upcoming pagination/filtering work.
- Backend fetch timeout is configurable with `BACKEND_REQUEST_TIMEOUT_MS` (default 10 seconds).
- Shared Core frontend types and permission helpers created.
- Navigation now hides Core areas for which the signed-in user has neither read nor manage permission.
  This is UX hardening only; backend authorization remains authoritative.
- Reusable UI states added for errors, loading, success/info notices, 404, and route-level crashes.
- Baseline security response headers added in Next.js.
- Reduced-motion accessibility support and consistent focus-visible styling added.

## Security boundary

B6.1 does not move authorization into the frontend. The browser may hide unavailable navigation,
but every protected operation must still be authorized by the FastAPI service layer through B3/B5.6.

The frontend never stores the access token in localStorage or exposes it to client components.

## Deliberately deferred

- B6.2: login/session UX hardening and session lifecycle improvements.
- B6.3: production application shell/navigation including mobile navigation.
- B6.4+: operational dashboards and write-capable Organization/People/User/Access/Documents screens.

## Environment

`frontend/.env.local.example` now supports:

```env
BACKEND_API_URL=http://127.0.0.1:8000/api/v1
BACKEND_REQUEST_TIMEOUT_MS=10000
```
