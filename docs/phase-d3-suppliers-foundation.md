# Phase D3 — Suppliers Foundation

Status: **Implemented and locally verified; awaiting independent implementation review.**

## Goal

D3 adds the internal operational foundation for supplier relationships without turning the Super App into an accounting, procurement, inventory, or vendor-identity system.

The domain covers:

- organization-owned supplier profiles;
- external supplier representatives / visitors;
- internal owner assignment;
- tags and notes;
- external-system references;
- audited lifecycle and optimistic concurrency;
- C3 Search integration.

## Hard domain boundaries

These concepts remain separate:

```text
Supplier != Internal Organization
SupplierRepresentative != Internal Person/User/Employee
Supplier != Commerce Customer
```

No supplier or representative creation creates or merges an Internal Organization, Person, User, Employee, or Commerce Customer.

D3 is not authoritative for:

- accounts payable, balances, bank accounts, payments, ledgers or tax accounting;
- purchase orders, goods receipts, supplier invoices or quotations;
- inventory quantities or reservations;
- supplier/product sourcing, purchase price, lead time, pack size or minimum order;
- vendor login/authentication;
- supplier contracts (reserved for the Contracts phase).

The Virtual Store must not directly read supplier identity, supplier contacts, internal notes, purchase cost, or internal supplier status. Commerce availability and sell-price are downstream outputs of future inventory/pricing domains, not SupplierProfile data.

## Core models

### SupplierProfile

Organization-owned operational relationship with:

- `supplier_kind`
- `display_name`
- `commercial_status`
- `source`
- `assigned_owner_user_id`
- `created_by_user_id`
- `is_active`
- optimistic `version`

Hard delete is not used. Archive produces `ARCHIVED + is_active=false`; restore produces a consistent non-archived active state.

### SupplierRepresentative

External contact/visitor belonging to one supplier. It is not an Internal Person or User.

Fields include:

- display name and job title;
- phone/email;
- primary/active flags;
- optimistic version.

#### Claude architecture-review correction: primary representative invariant

At most one **active primary** representative can exist per supplier. This is enforced in the database with a partial unique index, not only by application pre-checks:

```text
uq_supplier_representative_active_primary
ON supplier_representatives(supplier_id)
WHERE is_primary IS TRUE AND is_active IS TRUE
```

### SupplierNote

Organization-scoped through its supplier and uses optimistic concurrency. `note.body` is bounded and is never copied into Audit payloads or structured logs.

### SupplierTag / SupplierProfileTag

Tags are organization-owned classification metadata only. Tag names do not create hidden business rules.

### SupplierExternalReference

Controlled integration extension point for systems such as accounting/ERP/procurement. It does not create a foreign key to an external database and does not authorize direct external DB access.

Uniqueness is DB-authoritative over:

```text
organization_id + system + normalized_external_id
```

## External ID normalization

Architecture-review correction:

1. Unicode **NFKC** normalization;
2. trim leading/trailing whitespace;
3. reject control characters;
4. preserve case — **no case-folding** because external systems may use case-sensitive identifiers.

The external ID is never used as a route identifier. API paths use the internal reference UUID.

## Contact privacy

Architecture-review correction: phone/email protection goes beyond Audit minimization.

- raw phone/email are never placed in URL paths;
- Audit/log payloads exclude their values;
- `supplier.representative.contact.read` is required to receive raw contact values;
- users with representative read permission but without contact-read receive masked values;
- contact-read alone does not bypass the base supplier context/read requirement.

Masking is a presentation/data-release boundary. Backend authorization remains authoritative.

## Permissions

D3 permissions:

```text
supplier.read
supplier.manage
supplier.representative.read
supplier.representative.manage
supplier.representative.contact.read
supplier.notes.read
supplier.notes.manage
supplier.assign
supplier.tags.catalog.manage
supplier.tags.assign
supplier.external_reference.read
supplier.external_reference.manage
```

Architecture-review correction: tag vocabulary management and tag assignment are separate capabilities:

- `supplier.tags.catalog.manage` creates/manages the organization tag catalog;
- `supplier.tags.assign` attaches/removes existing tags.

Specialized read capabilities do not become an independent resource-discovery path; base supplier access/context remains required. Assignment never grants authorization.

## Organization isolation and non-disclosure

Resource lookup is organization-scoped. Unauthorized cross-organization resource access follows the established project resource-hiding behavior and returns 404 where the approved patterns require it.

C3 Search is reused; D3 does not create a parallel authorization/search path. Authorization filtering happens before LIMIT/OFFSET/result aggregation.

## Audit minimization

Meaningful mutations are audited in the same transaction using existing Audit infrastructure. Audit records prefer IDs, enums, state transitions and changed-field names.

Raw arbitrary/sensitive values are excluded, including:

- SupplierNote body;
- representative phone/email;
- unnecessary tag free text;
- external ID value.

## Concurrency and DB authority

`SupplierProfile`, `SupplierRepresentative`, and `SupplierNote` use optimistic versions and reject stale writes with deterministic conflict behavior.

Database constraints/indexes are the final authority for invariants such as active-primary uniqueness and external-reference uniqueness, including concurrent requests.

## API/BFF/UI

Backend REST stays under `/api/v1/suppliers`.

The Next.js frontend uses the existing authenticated BFF. Unsafe browser writes use the centralized mutation proxy and CSRF/origin protections; browser UI permission checks are usability controls only.

Main UI areas:

- supplier list/detail and lifecycle;
- owner assignment;
- representatives/visitors with masked/raw contact behavior;
- tag catalog and assignment;
- notes;
- external references;
- C3 global search integration.

## Virtual Store invariant

Supplier is a back-office domain. A Supplier-module or Super-App outage must not become a required dependency for Store registration, login, catalog browsing, cart, checkout, payment, or order creation.

Future flow should be conceptually:

```text
Supplier -> Procurement/Sourcing -> Inventory/Pricing -> Commerce
```

not:

```text
Virtual Store -> Supplier DB
```

## Local verification summary

- D3 dedicated backend tests: 15 passed.
- Backend regression: 169 collected tests passed across independent pytest executions; the environment can hang during session teardown when the whole suite is invoked as one process, so the review evidence records the independent executions instead of falsely claiming a one-shot pass.
- Python compileall: passed.
- Alembic head: `20260911_0017`.
- PostgreSQL offline migration SQL generation: passed.
- Frontend deterministic regression checkpoints B6.3 through D3: all passed.
- D3 frontend deterministic checks: 57 assertions passed.
- TS/TSX parser sweep: 146 files, 0 syntax-error files.
- Full dependency-based frontend typecheck/lint/build are not claimed because the supplied review workspace does not contain local Next/React/ESLint dependencies.
- Ruff/Mypy are not claimed because those modules are unavailable in this environment.

## Definition of done

D3 is not closed until independent implementation review verifies code, migration, authorization/privacy behavior, Audit minimization, Search reuse, BFF boundaries and tests, and all blocking findings are resolved.
