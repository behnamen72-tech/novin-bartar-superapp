# Claude Review Request — B6.4 Operational Dashboard

Please review the cumulative code in this package after your B6.3 UI checkpoint review. B6.4 is deliberately frontend/BFF-only; it does not change backend authorization, models, migrations, or business writes.

## Baseline

- B1–B5.6 Core previously approved.
- B6.1: frontend/BFF foundation.
- B6.2: rotating persistent session model.
- B6.3: authenticated application shell + permission-aware navigation.
- B6.4: live operational Core dashboard.

## Primary files

Please focus on:

- `frontend/components/dashboard/Dashboard.tsx`
- `frontend/lib/dashboard.ts`
- `frontend/lib/core-labels.ts`
- `frontend/lib/core-types.ts`
- `frontend/app/api/core/documents/route.ts`
- `frontend/app/api/core/documents/expiring/route.ts`
- `frontend/components/core/AuditView.tsx`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`

Supporting documentation:

- `docs/phase-b6.4-operational-dashboard.md`
- `B6.4_TEST_RESULTS.md`

## Expected authorization boundary

Dashboard capability gating is UX/network optimization only.

The client checks the exact READ permissions before issuing each dataset request:

- organization -> `organization.read`
- people -> `people.read`
- users -> `users.read`
- documents -> `documents.read`
- audit -> `audit.read`

Please verify this does not create a new trust boundary. A tampered client can still call BFF routes, but the BFF only forwards the HttpOnly-held access JWT and FastAPI must continue to enforce B3 Organization Scope plus B5 document ACL filtering.

## Specific review questions

### 1. Permission-aware concurrent loading

Please check `Dashboard.loadDashboard()` for:

- stale-state/race hazards
- unexpected 401 behavior with B6.2 `apiFetch()` single-flight refresh
- partial-failure correctness
- whether any failed request could incorrectly expose or preserve stale data
- unnecessary cross-permission requests

### 2. Documents attention path

New BFF routes are GET-only wrappers around the existing authenticated backend proxy.
Please confirm:

- tokens remain server-only
- query parameters are only forwarded, not treated as authorization evidence
- FastAPI document list/expiring authorization and restrictive ACL semantics remain authoritative
- the 200-row dashboard cap is represented honestly as a lower bound (`200+`) rather than an exact total

### 3. Dashboard counts

Organization, People, and User totals currently come from the already-authorized list APIs. This intentionally avoids adding a duplicate counting authorization implementation during B6.4.

Please classify any scalability concern as non-blocking unless you see a correctness/security issue. A future permission-aware aggregate endpoint is documented in Technical Debt.

### 4. Audit presentation

Audit labels were moved to `lib/core-labels.ts` so Dashboard and the full Audit view share the same user-facing action labels. The underlying Audit payload/immutability behavior is unchanged.

Please check that this refactor did not change Audit authorization or accidentally introduce sensitive payload rendering on the Dashboard. Dashboard shows only action label, resource type, actor identifier, and event time.

### 5. UI/accessibility/responsive behavior

Please review:

- metric buttons vs non-interactive cards
- keyboard/focus behavior
- refresh button state
- RTL layout
- small-screen stacking
- whether partial-error and loading states are understandable without hiding working sections

## Verification performed

See `B6.4_TEST_RESULTS.md`.

Current results:

- Backend pytest: **99 passed**
- Backend compileall: **passed**
- OpenAPI: **48 paths**
- PostgreSQL Alembic offline SQL through 0012: **passed**
- B6.3 navigation test: **12 assertions passed**
- B6.4 dashboard test: **11 assertions passed**
- TS/TSX syntax: **36 files, 0 diagnostics**
- strict repository-local semantic TypeScript check with temporary dependency stubs: **passed**

`npm install` timed out in this isolated runtime, so no claim is made for real Next.js dependency-installed typecheck/lint/build.

## Requested response format

Please separate:

1. **Blockers** — must fix before B6.5 Organization Management UI
2. **Non-blocking improvements** — can be tracked for later B6/production hardening
3. **Approval / reject** for continuing to B6.5
