# API Integration Contract v1 — Virtual Store ↔ Super App

## Status
Architecture baseline for the parallel Virtual Store and internal Super App tracks.

## Non-negotiable boundaries

- Internal `User` / `Person` / `Employee` identity is **not** Commerce `Customer` identity.
- Commerce owns Customer registration/authentication, cart, checkout, payment orchestration, and the Commerce Order.
- Super App owns internal identities, internal authorization, operational Workflow/Fulfillment, Audit, and internal management UX.
- Cross-domain access uses versioned API/event contracts and opaque external references; no direct cross-domain database access.
- PAN/CVV/PIN/raw card credentials must never transit or persist in Super App/Commerce application storage or logs. Payment uses the PSP-hosted flow; applications retain only provider-safe references/status.
- Commerce checkout/revenue flow must not depend on CRM availability.

## Reused Super App capabilities

Virtual Store must reuse rather than rebuild:

- Workflow Engine for operational fulfillment;
- Notifications capability through a controlled external-recipient contract;
- Documents capability through controlled Commerce-facing references.

## Order → Workflow ownership

- Commerce creates and owns `external_order_id`.
- Super App creates its own `workflow_id` and stores the Commerce order ID as an external reference.
- Workflow state is authoritative in Super App; Commerce stores only the customer-facing projection it needs.
- Cross-system mutating calls are idempotent.
- Cross-system events are versioned, deduplicated, and designed for at-least-once delivery.
- Transactional Outbox is the expected pattern for committed Commerce Order → fulfillment handoff.

## Inventory boundary

Order contracts use `inventory_location_id` / `stock_pool_id` concepts so the business can later choose physical-branch stock, dedicated online stock, or a hybrid pool without redesigning Order identity.

Inventory Authority alone changes authoritative stock. Reservation/confirm/release are explicit operations.

## Service-to-service identity

Browser/user/customer tokens are not service credentials. Internal integration uses dedicated short-lived service identity with explicit audience/scope and TLS. D2 implements the first consumer of this pattern for CRM → Commerce customer validation/activity.

## Failure model

- Transient integration failures are retried in a bounded manner.
- Consumers must be idempotent.
- Cross-system failures never silently create duplicate Orders/Workflows.
- Internal APIs are never exposed directly as public Store endpoints.

## D2 consequence

Super App CRM stores an opaque `commerce_customer_ref` plus organization-owned CRM metadata. It does not own Customer credentials, sessions, OTP, passwords, registration, or Store profile identity.
