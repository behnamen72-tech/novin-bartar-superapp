# Claude Review Request — B6.1 to B6.3 UI Checkpoint

Please review the actual cumulative code in this package. This is the preferred UI checkpoint before B6.4 Dashboard and the write-capable Core screens are layered on top.

## Baseline

- B1–B5.6 Core was previously approved.
- B6.1 added the frontend/BFF foundation.
- B6.2 added rotating persistent sessions.
- B6.3 adds the reusable authenticated application shell and permission-aware navigation.

## Highest-priority review areas

### 1. B6.2 session/BFF security (still important at this checkpoint)

Please re-check:

- `frontend/lib/session.ts`
- `frontend/lib/request-security.ts`
- `frontend/lib/api-client.ts`
- `frontend/lib/authenticated-backend.ts`
- `frontend/app/api/session/*`
- backend refresh-token/session code and migration 0012

Focus on refresh rotation, cookie scope, CSRF boundary, one-retry behavior for writes, logout/revocation, and failure handling.

### 2. B6.3 navigation authorization boundary

Primary files:

- `frontend/lib/navigation.ts`
- `frontend/components/app/AppShell.tsx`
- `frontend/app/page.tsx`

Expected property:

Navigation visibility is only UX. Backend B3/B5.6 authorization remains authoritative. A user who manipulates `?view=` must not gain any permission; known but unavailable views fall back to Dashboard, while BFF/backend checks still protect data independently.

Please verify there is no accidental client-side trust boundary.

### 3. Browser history / deep-link behavior

B6.3 intentionally keeps the existing single authenticated workspace and synchronizes view state with a non-sensitive query parameter:

- `/` -> dashboard
- `/?view=people` -> people

Please check for loops/stale-state hazards around:

- initial session restoration
- `activateView`
- `loadViewData`
- `popstate`
- permission changes after session revalidation

### 4. Responsive shell and accessibility

Please review:

- mobile drawer open/close behavior
- Escape and backdrop dismissal
- `aria-current`
- skip link
- focus/navigation concerns
- whether the CSS ordering correctly overrides the legacy mobile rule that used to hide `.sidebar`

### 5. Refactor regressions

B6.3 extracts the previous monolithic UI into:

- `components/session/LoginScreen.tsx`
- `components/dashboard/Dashboard.tsx`
- `components/core/CoreViews.tsx`
- `components/app/AppShell.tsx`

Please confirm B6.2 login/session semantics and the existing read-only Core views were preserved during this extraction.

## Verification performed

See `B6.3_TEST_RESULTS.md`.

Current results:

- Backend pytest: **99 passed**
- Backend compileall: **passed**
- OpenAPI: **48 paths**
- PostgreSQL Alembic offline SQL through 0012: **passed**
- TS/TSX syntax: **32 files, 0 diagnostics**
- strict repository-local semantic TypeScript check with temporary dependency stubs: **passed**
- B6.3 navigation runtime test: **12 assertions passed**

`npm install` timed out in the isolated runtime, so no claim is made for real dependency-installed Next.js typecheck/lint/build.

## Requested response format

Please separate:

1. **Blockers** — must fix before B6.4
2. **Non-blocking improvements** — can enter Technical Debt or later B6 hardening
3. **Approval / reject** for continuing to B6.4
