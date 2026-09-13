# D2 Test Results — Customer Reference / CRM Foundation

Verified after final D2 security/lifecycle hardening.

## Backend

- `python -m compileall -q app tests scripts`: **passed**
- `pytest -q`: **154 passed**
- Dedicated D2 CRM/integration tests: **15 passed**
- Alembic head: **`20260911_0016`**
- PostgreSQL offline `alembic upgrade head --sql`: **generated successfully through D2** (948 lines in this verification run)

D2-specific coverage includes:

- external Commerce reference remains opaque and organization-scoped;
- DB-authoritative uniqueness of `(organization_id, commerce_customer_ref)`;
- path-unsafe Commerce references rejected;
- archived-on-create rejected;
- archive → restore lifecycle returns to a consistent active/inactive state;
- direct cross-organization resource access hidden as 404;
- Note body absent from Audit on create/update;
- Tag free text absent from Audit;
- Customer and Note optimistic concurrency;
- assigned owner must have valid CRM context and assignment grants no permission;
- C3 Search reuses CRM ACL before LIMIT;
- missing Commerce customer and Commerce outage fail closed;
- Commerce Activity has separate permission;
- specialized Note/Commerce Activity permissions still require base CRM read;
- dedicated S2S JWT contains expected subject/audience/scope/short lifetime;
- Commerce HTTP base URL rejected outside local development; HTTPS required.

## Frontend deterministic regression checks

- B6.3 navigation: **13 assertions passed**
- B6.4 dashboard: **11 passed**
- B6.5 organizations: **18 passed**
- B6.6 people/users: **37 passed**
- B6.7 documents: **40 passed**
- B6.8 access: **36 passed**
- C1 workflow: **43 passed**
- C2 notifications: **29 passed**
- C3 search: **19 passed**
- D1 HR: **47 passed**
- D2 Customer CRM: **56 passed**
- TypeScript/TSX syntax transpile sweep: **128 source files passed** (excluding `.d.ts` declaration files)

## Frontend dependency limitation

`frontend/node_modules` is not present in this execution environment. Therefore dependency-based checks are **not claimed as passed**:

- `npm run typecheck`: could invoke global `tsc`, but failed because Next/React packages/type declarations are unavailable (`next/server`, React types, etc.).
- `npm run lint`: local `eslint` unavailable.
- `npm run build`: local `next` unavailable.

This is an environment/dependency limitation, not a successful build result.

## Backend lint limitation

A local `ruff` executable is unavailable in this environment, so no Ruff pass is claimed.
