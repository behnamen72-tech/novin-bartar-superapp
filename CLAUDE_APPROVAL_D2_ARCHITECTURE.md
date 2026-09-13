# Claude Architecture Review — D2 Customer Reference / CRM Foundation

Pre-implementation verdict: **APPROVED WITH CHANGES**.

Mandatory findings from review and their resolution before implementation:

1. `CustomerNote.body` must never enter Audit payloads; implemented as metadata-only note Audit.
2. CRM → Commerce Integration API requires explicit service-to-service identity; implemented as dedicated short-lived scoped JWT over TLS (except localhost development/test).
3. `(organization_id, commerce_customer_ref)` uniqueness must be database-authoritative and race-safe; implemented with a DB UniqueConstraint and `IntegrityError` → 409 handling.

Additional review recommendations were also locked before implementation:

- exact text lengths;
- separate Commerce Activity permission;
- optimistic concurrency for Customer Notes;
- explicit asymmetric dependency direction CRM → Commerce, never Checkout → CRM;
- assigned owner validation against CRM organizational context.

Further implementation hardening added before final review:

- specialized Notes/Commerce Activity access also requires base `crm.customer.read`;
- Commerce refs are path-safe bounded opaque IDs;
- arbitrary Tag name text is excluded from Audit;
- archive/restore cannot produce active+archived contradictory state.
