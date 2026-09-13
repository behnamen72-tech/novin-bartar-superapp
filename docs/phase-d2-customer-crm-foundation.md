# Phase D2 — Customer Reference / CRM Foundation

## Goal

Provide organization-scoped internal CRM metadata for external Virtual Store customers without merging Commerce Customer identity into internal `User` / `Person` / `Employee` identity.

D2 is a CRM foundation, not Customer Auth and not a full CRM/loyalty/marketing platform.

## Domain model

### CustomerCRMRecord

- `organization_id`
- opaque `commerce_customer_ref` (external reference, never a DB FK to Commerce)
- customer type / commercial status / source
- display label
- optional assigned internal owner
- creator
- active/archive lifecycle
- optimistic `version`

Authoritative uniqueness is enforced by the database on:

`(organization_id, commerce_customer_ref)`

A Commerce customer may therefore have independent CRM metadata in multiple authorized organizations.

### CustomerTag

Organization-owned vocabulary with normalized-name uniqueness. Tag names are free text and are intentionally excluded from Audit payload content.

### CustomerNote

Organization-scoped through its CustomerCRMRecord, max 4000 characters, optimistic `version`. Note body is intentionally excluded from Audit payloads.

## Identity boundary

Forbidden D2 coupling:

- Customer → Person FK
- Customer → internal User identity conversion
- Customer → Employee FK
- Customer password/OTP/session storage
- direct Commerce database access

Internal user references are allowed only for operational metadata such as creator/assigned owner and do not merge identities.

## Commerce integration

CRM → Commerce is deliberately one-way from an availability/dependency perspective:

- CRM may validate an external customer reference.
- CRM may read an authorized Commerce activity projection.
- Store registration/login/cart/checkout/payment/order must never require CRM availability.

D2 Commerce calls use a dedicated short-lived service JWT, explicit audience/scope, TLS outside local development, timeout, bounded retry, and strict response schema validation.

Current integration contract paths:

- `GET /internal/integration/v1/customers/{ref}/validation`
- `GET /internal/integration/v1/customers/{ref}/activity`

The actual Virtual Store service is a parallel-track dependency and is not fabricated inside Super App.

## Permissions

- `crm.customer.read`
- `crm.customer.manage`
- `crm.customer.notes.read`
- `crm.customer.notes.manage`
- `crm.customer.assign`
- `crm.customer.tags.manage`
- `crm.customer.commerce_activity.read`

Notes and Commerce Activity require base `crm.customer.read` in addition to their specialized permission. Assignment does not grant read/manage permissions.

Direct resource-ID access uses the established 404 non-disclosure pattern outside authorized scope.

## Search

C3 Search is extended with entity type `customer`. Authorization scope is calculated before LIMIT; D2 does not introduce an independent search authorization path.

## Audit / free-text policy

Meaningful mutations Audit in the same domain transaction.

Arbitrary customer-entered/operator-entered free text is not copied into Audit state/metadata merely for convenience. In particular:

- `CustomerNote.body` is absent from Audit.
- `CustomerTag.name` is absent from Audit.
- Customer display label is not copied into D2 Audit state.

Audit records IDs, enum/state transitions, version changes, actor and organization context instead.

## Lifecycle

Hard delete is not exposed. Archive sets `is_active=false` and commercial status `archived`. Restore reactivates the record and maps an archived status to `inactive`, avoiding the contradictory `active + archived` state.

## Frontend / BFF

Operational UI includes:

- organization capability selection;
- customer list/detail;
- CRM metadata create/edit;
- archive/restore;
- assignee picker constrained to users with CRM context in the organization;
- tags;
- notes;
- separately authorized Commerce Activity.

Unsafe browser mutations go through the existing authenticated BFF and central CSRF/origin protection. Backend authorization remains authoritative.

## Out of scope

- Store Customer registration/login/OTP/password/session
- Cart/Checkout/Payment/Order/Inventory
- loyalty/wallet/credit/pricing/discount logic
- marketing automation/campaigns
- Customer merge
- fraud scoring
- complaints/wholesale approval workflows

These remain separate future specifications or Virtual Store concerns.
