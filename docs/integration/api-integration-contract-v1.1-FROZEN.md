# API Integration Contract v1.1 — Customer Platform ↔ Super App

## Status

**v1.1-FROZEN BASELINE CANDIDATE — FREEZE ACTIVATION PENDING FINAL CLAUDE HASH CONFIRMATION — NOT A PRODUCTION-READINESS CLAIM**

This version incorporates the four-party alignment decisions and the single required change from Claude's primary review. Architecture-baseline freeze becomes active only after Claude confirms this exact artifact/hash. Explicit pre-production gates remain open and are not waived by the architecture freeze.

## 1. System boundaries

### Customer Platform owns

- Commerce Customer identity/authentication/session;
- customer profile and addresses;
- customer-facing catalog/search/files/product images/notifications/audit;
- cart and checkout;
- authoritative Commerce Order and order lines;
- payment orchestration and payment-state interpretation;
- customer-facing order-status projection;
- branch routing for Commerce orders;
- commerce price projection and checkout price revalidation;
- commerce availability/reservation module;
- replacement commercial decision and customer approval.

### Super App owns

- Internal User/Person/Employee identities;
- enterprise authorization and internal organization scopes;
- internal operational fulfillment Workflow;
- staff/internal notifications;
- enterprise Documents/Search/Audit within the Super App boundary;
- internal management/operations UX.

### External system baseline

- Mahak is the current source of truth for physical branch stock.
- Mahak is the current source of truth for product price/discount baseline.
- Mahak integration is isolated behind an Anti-Corruption Layer.

## 2. Non-negotiable identity/data boundaries

- `Internal User / Person / Employee != Commerce Customer`.
- No automatic merge/link by phone, email, or name.
- No shared identity tables.
- No shared database tables between Customer Platform and Super App.
- No direct cross-system database reads/writes.
- Cross-system integration uses versioned APIs/events and opaque external references.
- Customer Platform revenue path must survive temporary Super App outage.

## 3. Shared-capability terminology

A capability being "shared" inside the Super App does **not** make it a shared runtime service across Customer Platform and Super App.

Therefore:

- Enterprise Search != Commerce Search.
- Enterprise Audit != Commerce Audit.
- Enterprise Notifications != Customer Notifications.
- Enterprise Documents != Commerce/customer files.
- Enterprise Identity != Customer Identity.

Patterns/contracts may be reused; runtime/DB sharing is not the default.

Exception: Super App Workflow is intentionally used for **internal operational fulfillment** through this integration contract, without taking Commerce Order authority.

## 4. Order and fulfillment authority

- Customer Platform creates/owns `external_order_id` and authoritative Commerce Order state.
- Super App creates/owns its own `workflow_id` for internal fulfillment and stores the external order reference.
- Commerce transactional state is authoritative in Customer Platform.
- Internal fulfillment state is authoritative in Super App.
- Customer-facing order-status projection is authoritative in Customer Platform.
- Super App does not mutate authoritative commercial totals, payment state, order pricing snapshots, or replacement financial decisions.

Cross-system references bind the source system, relevant commerce tenant, external order ID, and contract/event version as applicable.

## 5. Fulfillment handoff

Customer Platform emits a committed, versioned fulfillment instruction only when the order is explicitly eligible for fulfillment.

Super App must not infer eligibility by reimplementing payment/COD rules.

A handoff should include only operationally necessary data, such as:

- commerce tenant reference;
- external order ID;
- order/fulfillment version;
- event ID and correlation ID;
- selected branch/location reference;
- explicit fulfillment-eligibility fact and reason/version;
- line/SKU references and quantity;
- barcode only where operationally required;
- approved replacement instructions;
- delivery window/preferences;
- minimal delivery-address/contact snapshot needed for fulfillment.

Customer OTP/session/authentication material, CRM notes, unrelated profile data, and full purchase history are excluded.

## 6. Customer-visible state projection

The customer-facing state machine may be intentionally simpler than internal fulfillment.

Current business projection baseline:

1. Order confirmed / being collected.
2. Handed to courier / on the way.
3. Delivered.

The mapping from internal fulfillment events to customer-facing projection is versioned contract behavior owned by Customer Platform.

## 7. Branch routing

- Customer chooses delivery address, not fulfillment branch.
- Customer Platform owns branch routing based on factors such as distance, inventory availability, and delivery capability.
- Selected branch/location reference is sent to Super App.
- Super App does not independently reroute a Commerce Order unless a future explicit contract permits it.

### OPEN BUSINESS DECISION

Single-branch vs split-branch fulfillment is not frozen. Current Super App recommendation for MVP is one Commerce Order -> one fulfillment branch.

## 8. Inventory boundary

### Initial stock policy

Shared Physical Branch Inventory.

There is no dedicated online stock pool in the current business baseline.

### Ownership

- Physical stock source of truth: Mahak.
- Commerce availability/reservation authority: Customer Platform Inventory Module.
- Internal fulfillment workflow: Super App.
- Super App is not Inventory System of Record.

The contract retains abstractions such as `inventory_location_id` / `stock_pool_id` for compatibility and future evolution.

Expected integration direction:

`Checkout -> Inventory Interface -> Customer Platform Inventory Module -> Mahak ACL -> Mahak`

### Reservation

- Add-to-cart: no reservation.
- Checkout: short-lived reservation.
- TTL: configurable; current non-binding operational baseline is approximately 5–10 minutes, subject to real Mahak/checkout runtime evidence.
- Normal release/commit: event-driven.
- Expiry cleanup: recovery mechanism.

Contract/schema terminology must distinguish a commerce reservation becoming attached to a committed order from physical-stock confirmation when these are different facts.

### OPEN PRE-PRODUCTION GATE — physical/online concurrency

Before production checkout/inventory dependency, the implementation must define and test the consistency model between Mahak physical sales and online reservations. Customer Platform database locking alone is not proof that the physical-sale race is solved.

## 9. Price boundary

- Current price source of truth: Mahak.
- Current discount baseline source: Mahak.
- Customer Platform stores/serves commerce projections.
- Cart does not freeze authoritative price.
- Checkout revalidates latest price.
- Committed OrderLine price snapshot is immutable.
- Customer Platform campaign/merchandising capability does not imply independent financial price mutation under the current baseline.

## 10. Payment and PCI

### Payment strategies

- `ONLINE_GATEWAY`
- `CASH_ON_DELIVERY`

Payment strategy is modeled explicitly, not as a generic boolean.

### PCI boundary

PAN/CVV/PIN/raw card credentials must never transit or persist in Customer Platform/Super App application storage or logs. Online payment uses a PSP-hosted flow; Customer Platform retains only provider-safe references/status/verification results.

### Fulfillment eligibility

Payment state != fulfillment eligibility.

- Online: verified/paid order may become fulfillment eligible.
- COD: confirmed order with accepted COD policy may become fulfillment eligible before payment state becomes PAID.

Customer Platform emits an explicit fulfillment-eligibility fact; Super App does not duplicate payment-strategy business logic.

## 11. Replacement

When fulfillment cannot provide a requested line:

1. Super App emits a versioned `fulfillment.item_unavailable`-style event.
2. Customer Platform determines alternatives and obtains customer decision where required.
3. Customer Platform updates the authoritative Commerce Order/version.
4. Customer Platform sends a versioned replacement/fulfillment instruction update.
5. Super App idempotently applies the newest valid instruction.

Super App cannot finalize commercial replacement on its own.

### OPEN PRE-PRODUCTION GATE — financial adjustment

Paid-order replacement/refund semantics are not frozen for removed items, cheaper alternatives, more expensive alternatives, partial refund, incremental payment, and COD adjustment. No wallet assumption is permitted without explicit business decision.

## 12. Reliability and event semantics

- Transactional Outbox is mandatory for committed cross-system handoff where data and event must be atomic.
- Delivery semantics: at least once.
- Events have immutable `event_id`.
- Consumers are idempotent and deduplicate processed events.
- Aggregate/order/fulfillment-instruction versions protect against stale/out-of-order application.
- Mutating APIs require idempotency semantics; same key + same logical request returns/replays the same result, while conflicting reuse is rejected.
- Retry is bounded with backoff.
- Correlation IDs flow across systems.
- Failed events require an operational recovery path (DLQ or equivalent persisted failed-event/manual-recovery mechanism) before production dependency.

## 13. Service-to-service authentication

Browser/customer/employee tokens are not service credentials.

The frozen baseline standard is the already-reviewed D2 service-authentication pattern:

- dedicated service identity;
- short-lived signed JWT bearer tokens;
- explicit `sub`, `iss`, `aud`, `scope`, `iat`, `exp`, and unique `jti` claims;
- receiver validates signature/allowed algorithm, issuer, audience, expiry, and required scope before serving the request;
- credentials/keys are rotatable and never reused as customer or employee credentials;
- HTTPS is mandatory outside local development/test; local plain HTTP is limited to loopback development/test endpoints;
- integration clients reject redirects rather than following them;
- retries are bounded and limited to retryable network/server/rate-limit failures, with bounded backoff and `Retry-After` handling where applicable;
- service-authentication failures are not retried as ordinary transient failures;
- mutating integration operations additionally obey the contract's idempotency requirements; `jti` supplies a unique token identifier and may be used for replay controls where the endpoint risk model requires it;
- internal integration endpoints are not exposed as public Store/customer endpoints.

This standard intentionally reuses the D2 mechanism rather than creating a second S2S scheme for Store ↔ Super App integration. Any future incompatible authentication mechanism requires a versioned contract change and architecture review.

## 14. Audit, files, notifications, search

### Audit

Commerce Audit and Enterprise Audit are independently owned/stored. Correlation IDs may link operational traces; there is no shared Audit DB.

### Customer-facing files

Product images and customer-facing files remain Customer Platform capabilities and do not depend on Enterprise Documents ACL at runtime.

### Notifications

Customer-facing notifications remain Customer Platform capabilities. Staff/internal workflow notifications remain Super App capabilities. Cross-system notification requests, if introduced, are asynchronous and explicitly contracted.

### Search

Commerce catalog search remains independent of Enterprise C3 Search.

## 15. Failure model

Temporary outage of Super App/CRM/Supplier/Enterprise Search/Documents/Notifications must not prevent Customer Platform from completing the revenue path through Order Commit.

Post-commit integration failures are retained/retried through durable integration mechanisms and must not silently create duplicate Orders or Workflows.

Operations requiring new customer decisions (for example replacement approval) may pause at an explicit workflow state rather than bypassing the Customer Platform.

### Customer identity profile-change scope note

Customer mobile-change internals (for example OTP/change-request handling and any `old_mobile_notice` behavior) remain Customer Platform concerns and are not part of this v1.1 cross-system baseline. If Super App later requires a customer-mobile-change notification, that requires an explicit versioned event/API addition rather than implicit coupling.

## 16. Contract governance

This contract becomes a joint architecture gate before real production dependency between Customer Platform and Super App.

It does not block independent repository/foundation development in either track.

After freeze:

- contract version is explicit;
- incompatible changes require a new version or documented backward-compatible evolution;
- cross-system breaking changes require architecture review;
- implementation closure follows the project evidence rule: versioned artifact + primary review + executable evidence.

## 17. Open items before production dependency

The following are intentionally **not** declared solved by this v1.1 candidate:

1. Physical-sale vs online-reservation concurrency semantics with Mahak.
2. Paid-order replacement/refund/incremental-payment semantics.
3. Single-branch vs split-branch fulfillment policy.
4. Concrete PSP/provider selection and provider-specific operational behavior.
5. Concrete DLQ/manual-recovery implementation.

These open items do not block repository/foundation creation, but the relevant ones block production Commerce/Fulfillment dependency until resolved and tested.
