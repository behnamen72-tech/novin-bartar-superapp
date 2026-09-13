# C3 Test Results — Search Core

Verified on the C3 working tree.

## Backend
- `pytest -q`: **129 passed**
- `python -m compileall -q app scripts tests`: passed
- OpenAPI: **69 paths total**
- Search API: **1 path**
- Alembic PostgreSQL offline upgrade through `20260911_0014`: generated successfully
- C3 adds no database migration

C3 backend coverage includes:
- authentication required
- cross-company Organization/Person/Document isolation
- SQL-first People relationship scoping before limit
- B5.4 Document ACL preservation in Search
- entity-type filtering
- query minimum and per-type limit validation
- safe internal action paths in unified results

## Frontend deterministic checks
- B6.3 navigation: **13 assertions passed** (updated for the intentional always-visible Search item)
- B6.4 dashboard: 11 passed
- B6.5 organizations: 18 passed
- B6.6 people/users: 37 passed
- B6.7 documents: 40 passed
- B6.8 access: 36 passed
- C1 workflow: 43 passed
- C2 notifications: 29 passed
- C3 search: **20 assertions passed**
- TypeScript/TSX syntax transpile sweep: **102 files, 0 syntax diagnostics**

## Frontend dependency limitation
`npm install --prefer-offline --no-audit --no-fund` was attempted and timed out in this
environment. Therefore a real project `npm run typecheck`, `npm run lint`, and `npm run build`
are **not** claimed as passed. Running global `tsc --noEmit` without installed Next/React type
packages fails dependency resolution and is not treated as a valid project typecheck.
