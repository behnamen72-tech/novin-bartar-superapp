# Independent Implementation Review Request — D3 Suppliers Foundation

Please review **D3 at implementation level**, not only the specification.

## Current status

- D2 implementation: independently approved and closed.
- D3 architecture: independently reviewed as `Approved with changes`; all four requested changes were incorporated before/during implementation.
- D3 implementation: locally verified; **not yet closed**.

Read first:

1. `AGENTS.md`
2. `CURRENT_REVIEW_STATUS.md`
3. `docs/phase-d3-suppliers-foundation.md`
4. `CLAUDE_APPROVAL_D3_ARCHITECTURE.md`
5. `D3_TEST_RESULTS.md`
6. migration `backend/alembic/versions/20260911_0017_suppliers_foundation.py`
7. backend supplier module/routes/tests
8. frontend Supplier/BFF/Search changes

## Architecture invariants to verify against code

### Identity/domain separation

- Supplier must not create/merge Internal Organization/User/Person/Employee.
- SupplierRepresentative must remain an external contact, never an Internal Person/User/Employee.
- Supplier must not become Commerce Customer identity.

### Accounting / Inventory / Commerce boundaries

- no direct Accounting/ERP database access or external FK;
- no authoritative AP/balance/payment/bank/ledger data in D3;
- Supplier code cannot directly mutate Inventory;
- Virtual Store does not directly consume supplier/cost/internal-note data;
- Store registration/login/cart/checkout/payment/order creation do not depend on Supplier availability.

### Claude architecture-review corrections

Please directly verify all four corrections:

1. **Primary representative:** DB-enforced partial unique index permits at most one active primary representative per supplier, including concurrent writes.
2. **Contact privacy:** raw phone/email never appear in route identifiers or Audit payloads; lower-permission reads are masked; raw release requires `supplier.representative.contact.read` plus the approved base supplier context.
3. **Tag permissions:** `supplier.tags.catalog.manage` and `supplier.tags.assign` are genuinely separate in backend authorization and BFF/UI behavior.
4. **External ID normalization:** NFKC + trim + control-character rejection + case preservation are applied consistently; DB uniqueness is on normalized value within organization/system; external ID is not used as path ID.

## Authorization/non-disclosure review

Please verify:

- backend service layer remains authoritative;
- specialized permissions do not accidentally become a supplier-discovery bypass;
- cross-organization direct resource access follows established 404 hiding behavior;
- assignment never grants permission;
- assignee must have valid organization context;
- C3 Search reuses the existing authorized read path and filters authorization before LIMIT/aggregation.

## Audit/privacy review

Please inspect actual Audit calls and confirm that arbitrary/sensitive values are excluded where designed, especially:

- `SupplierNote.body`;
- representative phone/email;
- tag free text when unnecessary;
- external ID values.

Check for leakage through exception/error/log payloads as well as normal Audit events.

## DB/migration/invariant review

Review migration 0017 and models for:

- foreign keys and organization scoping;
- active-primary partial unique index;
- external-reference uniqueness;
- optimistic concurrency assumptions;
- archive/restore consistency;
- indexes/constraints and downgrade safety;
- absence of hidden direct coupling to external domains.

## BFF/frontend review

Confirm:

- all unsafe browser mutations traverse the centralized authenticated mutation proxy/CSRF-origin guard;
- read routes do not accidentally expose raw contacts beyond backend permission results;
- browser permission checks are only UX, not security authority;
- Supplier Search navigation uses existing C3 flow;
- no supplier/internal-cost data is surfaced toward the Virtual Store boundary.

## Test evidence

See `D3_TEST_RESULTS.md`.

Important honesty note: a one-process whole pytest run can hang during teardown in this environment. The 169 tests were therefore rerun across independent pytest processes and all 169 passed. Frontend local dependencies are absent, so dependency-aware npm typecheck/lint/build and backend Ruff/Mypy are **not claimed as passed** and should remain CI gates.

## Requested verdict

Please report:

- Blockers
- Security findings
- Architecture/domain findings
- Data-model/migration findings
- Authorization/Audit findings
- Frontend/BFF findings
- Test gaps or CI recommendations
- Final verdict: **Approved / Approved with changes / Rejected**

D3 must remain open until blocking implementation findings are resolved and you issue a final implementation verdict.
