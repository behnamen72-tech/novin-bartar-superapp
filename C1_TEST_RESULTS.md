# C1 Workflow Core + UI — Test Results

Baseline: Claude-approved B6.8 line.

## Backend
- `pytest -q`: **116 passed**
- `python -m compileall -q app tests scripts`: **passed**
- OpenAPI generation with isolated SQLite config: **62 total path templates**
- Workflow API: **14 path templates**
- PostgreSQL Alembic offline SQL: **passed through `20260911_0013`**

New/expanded C1 coverage includes:
- authenticated Workflow capability discovery
- capability endpoint returns only organizations with effective Workflow permission
- workflow definition create/update/state/transition lifecycle
- publish graph validation and immutable published versions
- version cloning + previous published retirement
- organization-scope enforcement and cross-company non-disclosure
- instance start/transition/cancel lifecycle
- row-locked transition semantics
- append-only transition history
- same-transaction Audit writes

## Frontend
Cumulative repository-local checks:
- B6.3 navigation: **12 assertions passed**
- B6.4 dashboard: **11 assertions passed**
- B6.5 organizations: **18 assertions passed**
- B6.6 people/users: **37 assertions passed**
- B6.7 documents: **40 assertions passed**
- B6.8 access: **36 assertions passed**
- C1 Workflow UI/BFF: **43 assertions passed**
- TypeScript compiler API syntax scan: **93 `.ts`/`.tsx` files, 0 syntax diagnostics**

C1 UI/BFF checks cover:
- permission-aware Workflow navigation
- workflow capability organization selector
- definition/state/transition write routes use centralized authenticated BFF
- instance start/transition/cancel write routes use centralized authenticated BFF
- dynamic identifiers are `encodeURIComponent` encoded
- CSRF/origin mutation guard remains centralized in `authenticated-backend.ts`
- published/draft/retired and active/completed/cancelled UX paths

## Frontend dependency limitation
`node_modules` is not installed in this isolated runtime. `npm run typecheck` was attempted and cannot resolve the real `next`, `react`, and Node type packages, so a real dependency-installed Next.js typecheck/lint/build is **not claimed as passed**.

Run in the normal development environment after `npm install`:
- `npm run typecheck`
- `npm run lint`
- `npm run build`

## Final package verification
The full C1 review archive was extracted into a fresh directory and verified again. The cumulative B6.3-B6.8 frontend invariant scripts and the C1 Workflow script passed, the source Documents storage package remained present, and the B6.8→C1 patch reconstructed the full C1 tree byte-for-byte under the packaging filter.
