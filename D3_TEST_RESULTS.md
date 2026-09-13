# D3 Test Results — Suppliers Foundation

Status: **locally verified; awaiting independent implementation review**

## Backend dedicated D3 tests

Command:

```bash
cd backend
pytest -q tests/test_suppliers_api.py
```

Result:

```text
15 passed in 8.28s
```

Coverage includes:

- Supplier/Representative identity separation;
- cross-organization 404 behavior;
- DB-level one-active-primary-representative invariant;
- contact masking and explicit raw-contact permission;
- Note/contact/tag/external-reference Audit minimization;
- tag catalog vs tag assignment permissions;
- NFKC+trim external ID normalization with case preservation;
- control-character rejection;
- base `supplier.read` requirement alongside specialized read permissions;
- optimistic concurrency for Supplier/Representative/Note;
- archive/restore state consistency;
- assignment context without authorization grant;
- C3 Search ACL reuse;
- DB-authoritative external-reference uniqueness.

## Backend compile verification

```bash
python -m compileall -q app tests scripts
```

Result: passed.

## Backend regression

Pytest collection:

```text
169 tests collected
```

A single-process whole-suite invocation reaches test completion but can hang during session teardown in this review environment. It is therefore **not** represented as a reliable one-shot pass.

To obtain deterministic evidence, the test suite was executed in independent processes/groups:

```text
Group 1: 62 passed
Group 2: 66 passed
Notifications: 8 passed
Search: 4 passed
Suppliers/D3: 15 passed
Workflow: 14 passed
---------------------------
Total: 169 passed
```

No test result is inferred from the timed-out combined process.

## Alembic / PostgreSQL migration verification

Current migration head:

```text
20260911_0017
```

PostgreSQL offline SQL generation through Alembic completed successfully. Generated evidence is in `D3_ALEMBIC_OFFLINE.sql`.

The generated SQL includes the partial unique primary-representative index:

```sql
CREATE UNIQUE INDEX uq_supplier_representative_active_primary
ON supplier_representatives (supplier_id)
WHERE is_primary IS TRUE AND is_active IS TRUE;
```

## Frontend deterministic regression

Clean final run:

```text
B6.3 navigation:                 13 assertions passed
B6.4 dashboard:                  11 assertions passed
B6.5 organization management:   18 assertions passed
B6.6 people/users:               37 assertions passed
B6.7 documents:                  40 assertions passed
B6.8 access management:          36 assertions passed
C1 workflow:                     43 assertions passed
C2 notifications:                29 assertions passed
C3 search:                       19 assertions passed
D1 HR:                           47 assertions passed
D2 Customer CRM:                 56 assertions passed
D3 Suppliers:                    57 assertions passed
```

Historical D1/D2 deterministic check scripts previously assumed an exact current phase marker. They were corrected to accept their phase or a later D phase so advancing the product to D3 does not create a false regression failure.

## TS/TSX syntax parser sweep

TypeScript parser sweep using the globally installed compiler:

```text
TS/TSX files checked: 146
Syntax-error files: 0
```

This is a syntax/parser check, **not** a substitute for dependency-aware typecheck/build.

## Environment limitations — not claimed as passed

The review workspace does not contain local frontend dependencies. Therefore the following are not claimed as passed:

- `npm run typecheck` — dependency/type resolution fails because Next/React/@types dependencies are absent;
- `npm run lint` — local ESLint is unavailable;
- `npm run build` — local Next.js build tooling is unavailable.

Backend quality modules are also unavailable locally:

- Ruff: unavailable;
- Mypy: unavailable.

These should be CI gates in a dependency-installed environment before production merge/deploy.
