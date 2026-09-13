# D1 Test Results — HR Foundation

Verified on the D1 working tree after the final temporal relationship and shared-profile scope checks.

## Backend
- `pytest -q`: **139 passed**
- D1 HR API tests: **10 passed**
- `python -m compileall -q app tests scripts`: passed
- Alembic head: **`20260911_0015`**
- PostgreSQL offline `alembic upgrade head --sql`: generated successfully through D1

D1 backend coverage includes:
- inherited Job Profiles (`SELF` vs `SELF_AND_DESCENDANTS`);
- cross-company list denial and direct resource-ID write hiding;
- shared-profile mutation authorization across actual impacted descendant organizations;
- scope narrowing blocked while active descendant positions depend on the profile;
- same-organization reporting hierarchy, cycle prevention, and deactivation dependencies;
- Person↔Organization relationship prerequisite for employment;
- temporal relationship validation for future planned employment starts;
- future-dated relationships excluded from today's HR Person picker;
- one active employment per Person/organization;
- one active occupant per planned position;
- end/reactivate employment history without hard delete;
- HR organization capability discovery independent from `organization.read`;
- authentication required for HR writes;
- same-transaction Audit assertions on representative writes.

## Frontend deterministic checks
- B6.3 navigation: 13 assertions passed
- B6.4 dashboard: 11 passed
- B6.5 organizations: 18 passed
- B6.6 people/users: 37 passed
- B6.7 documents: 40 passed
- B6.8 access: 36 passed
- C1 workflow: 43 passed
- C2 notifications: 29 passed
- C3 search regression: 19 passed
- D1 HR foundation: **47 assertions passed**
- TypeScript/TSX syntax transpile sweep: **115 files, 0 syntax diagnostics/failures**

## Frontend dependency limitation
Local `frontend/node_modules` is absent in this execution environment. A real project dependency-based check therefore cannot be claimed:
- `npm run typecheck` fails dependency resolution for Next/React type packages;
- `npm run lint` cannot run because local `eslint` is unavailable;
- `npm run build` cannot run because local `next` is unavailable.

These are reported as environment/dependency limitations, **not** as passed checks.
