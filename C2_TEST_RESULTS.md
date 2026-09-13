# C2 Test Results — Notifications Core

Verified on the C2 working tree.

## Backend
- `pytest -q`: **125 passed**
- `python -m compileall -q app scripts tests`: passed
- OpenAPI: **68 paths total**
- Notifications API: **6 paths**
- Alembic PostgreSQL offline upgrade through `20260911_0014`: generated successfully

Covered C2 backend cases include:
- authentication required for public notification APIs
- recipient-only list/get/read/unread semantics
- cross-user direct-object access hidden as 404
- unread count and mark-all recipient isolation
- no B3 role required to read one's own notifications
- internal producer transaction ownership (no implicit commit)
- dedupe-key behavior
- immutable content/ownership and no physical delete
- mutable read state
- unsafe/external/backslash action-path rejection
- resource type/id pairing validation
- inactive-recipient durability
- organization/event filters remain recipient-scoped
- Workflow transition/cancel by another actor notifies the starter

## Frontend deterministic checks
- B6.3 navigation: 12 assertions passed (updated for the intentional always-visible personal Notifications item)
- B6.4 dashboard: 11 passed
- B6.5 organizations: 18 passed
- B6.6 people/users: 37 passed
- B6.7 documents: 40 passed
- B6.8 access: 36 passed
- C1 workflow: 43 passed
- C2 notifications: **29 assertions passed**
- TypeScript/TSX syntax transpile sweep: **100 files, 0 syntax diagnostics**

## Frontend limitation in this environment
`node_modules` is not present. `npm install` was attempted and timed out, so a real Next.js `typecheck`, `lint`, and `build` are **not** claimed as passed. A global `tsc --noEmit` cannot resolve Next/React type packages without installed dependencies and therefore is not a valid project typecheck result here.
