# Claude Review Request — B6.1 Frontend Foundation

Baseline: B5.6 approved final.
Scope: frontend foundation only; no new backend business/domain behavior.

Please review the actual implementation, especially:

1. `frontend/lib/authenticated-backend.ts`
   - HttpOnly-cookie JWT remains server-side.
   - generalized authenticated BFF helper for future write routes.
   - query-string forwarding.
   - only `content-type` and `accept` are forwarded from browser requests.
   - expected backend 4xx statuses are preserved.
   - arbitrary backend 5xx bodies are replaced by a safe 502 response.
   - network/timeout failures return safe 502 responses.
2. `frontend/lib/backend.ts`
   - configurable request timeout, default 10s.
3. `frontend/lib/api-client.ts`
   - typed browser error handling and FastAPI validation-detail normalization.
4. `frontend/lib/core-types.ts` and `frontend/lib/permissions.ts`
   - shared types/helpers for upcoming B6 operational screens.
5. `frontend/app/page.tsx`
   - existing demo functionality preserved.
   - navigation visibility is permission-aware UX only; backend remains authoritative.
6. `frontend/next.config.ts`
   - baseline response security headers.
7. `frontend/app/error.tsx`, `loading.tsx`, `not-found.tsx`, and `components/ui/*`
   - reusable failure/loading states and accessibility behavior.

Verification completed in ChatGPT runtime:
- Backend pytest: 90 passed.
- Backend compileall: passed.
- OpenAPI: 46 paths.
- Alembic PostgreSQL offline SQL through 0011: passed.
- TS/TSX syntax parse: 24 files, 0 syntax diagnostics.

Important limitation:
- `npm install` timed out in the isolated runtime, so `npm run typecheck`, `npm run lint`, and `npm run build` are not claimed as passed here. Please run them in a normal Node environment with dependencies installed.

Please report blockers separately from non-blocking production-hardening recommendations.
