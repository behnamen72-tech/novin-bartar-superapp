# Claude Review Request — D2 Customer Reference / CRM Foundation

Please perform an **implementation-level independent review** of D2 against the approved D1/C3 baseline, the D2 architecture review, and `docs/api-integration-contract-v1-virtual-store-superapp.md`.

D2 architecture was previously **Approved with changes**. The mandatory architecture findings were incorporated before implementation. Please now inspect actual code/migration/tests rather than re-reviewing only the specification.

## Highest-priority review targets

### 1. Identity/domain boundary

Verify that Commerce Customer remains separate from internal `User` / `Person` / `Employee`:

- `commerce_customer_ref` is opaque and has no Commerce DB FK;
- no Customer→Person/User/Employee identity merge exists;
- internal User FKs are only operational metadata (creator/assignee);
- no Customer credential/session/OTP/password fields were introduced.

### 2. Organization authorization / non-disclosure

Verify all CRM resources are organization-scoped under the established B3 authorization model:

- list scope uses explicit permission;
- direct guessed resource IDs return 404 outside authorized scope;
- Notes and Commerce Activity require both base `crm.customer.read` and specialized permissions;
- assignment never grants access;
- assignee picker does not require/broaden generic `users.read` and only returns valid CRM-context users.

### 3. DB invariants and concurrency

Verify:

- DB UniqueConstraint `(organization_id, commerce_customer_ref)` is authoritative;
- concurrent duplicate writes map safely to 409;
- CustomerCRMRecord and CustomerNote optimistic version checks are correct;
- row locking/update flow does not permit lost updates;
- archive/restore never leaves `active + archived` inconsistent state;
- migrations 0016 constraints/indexes/enums and downgrade are sane for PostgreSQL.

### 4. Free-text / Audit leakage

This was the primary preimplementation security finding.

Verify actual Audit calls do **not** copy:

- `CustomerNote.body`;
- `CustomerTag.name`;
- arbitrary customer display-label text.

Audit should retain IDs/state/version/actor/organization context only where possible. Look for any secondary logging/error path that would accidentally serialize Note content.

### 5. CRM → Commerce S2S client

Review `app/modules/customers/integration.py` and config:

- dedicated secret/service identity rather than employee/customer/browser token;
- short token lifetime;
- issuer/audience/scope/jti correctness;
- HTTPS enforcement outside localhost development/test;
- timeout + bounded retry behavior;
- no unsafe redirects;
- path handling/encoding;
- strict response schema validation;
- fail-closed behavior when Commerce is unavailable/malformed;
- whether shared-secret HS256 is acceptable for v1 or any change is required now rather than as later hardening.

The Virtual Store service itself is a parallel project and is intentionally not fabricated in this repository.

### 6. C3 Search reuse

Verify customer search extends C3 without creating a parallel authorization path and that organization authorization is applied before LIMIT/result aggregation.

### 7. Frontend/BFF boundary

Verify D2 browser writes use the existing authenticated BFF + central CSRF/origin protections, dynamic path segments are encoded, and UI permission gates are UX only while Backend remains authoritative.

Review the operational CRM UI for accidental Customer/Internal Identity conflation.

### 8. Parallel Virtual Store alignment

Verify D2 does not make Store registration/login/cart/checkout/payment/order creation dependent on CRM availability. Dependency is intentionally asymmetric: CRM may call Commerce; Commerce revenue path must not require CRM.

## Tests reported locally

See `D2_TEST_RESULTS.md`.

Headline results:

- Backend: **154 passed**
- Dedicated D2 tests: **15 passed**
- Alembic head: **0016**
- PostgreSQL offline migration SQL generated through D2
- D2 deterministic frontend: **56 assertions passed**
- all prior deterministic B6.3→D1 checks also passed
- TS/TSX syntax transpile: **128 source files passed**

Do **not** treat dependency-based frontend typecheck/lint/build as passed: local `frontend/node_modules` was absent and this limitation is documented explicitly.

## Requested verdict

Please separate:

1. Blockers
2. Security findings
3. Architecture/integration findings
4. Data model/migration findings
5. Frontend/BFF findings
6. Test gaps
7. Recommended corrections
8. Final verdict: **Approved / Approved with changes / Rejected**

Please call out any issue that must be fixed before D2 can be closed.
