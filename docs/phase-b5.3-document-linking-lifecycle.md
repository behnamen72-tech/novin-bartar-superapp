# Phase B5.3 — Document Linking & Lifecycle

Status: Ready for Claude Review

## Purpose
B5.3 turns the B5.2 file/document API into a reusable document domain that can
attach documents to existing Core entities and archive them without destructive
deletion.

## Scope implemented

### DocumentLink API
- `GET /api/v1/documents/{document_id}/links`
- `POST /api/v1/documents/{document_id}/links`
- `DELETE /api/v1/documents/{document_id}/links/{link_id}`
- `GET /api/v1/documents?entity_type=...&entity_id=...`

B5.3 enables only target types whose ownership rules already exist:
- `organization`
- `person`

Future business modules can extend the allowlist only when their domain model
and organization-scope validation are available. Arbitrary entity types are not
accepted.

### Link integrity rules
- The document's real `organization_id` remains its ownership/security boundary.
- An `organization` link can only target that same owner organization.
- A `person` link requires `people.read` in the document organization.
- The Person must have a PersonOrganizationRelationship with that organization.
- Historical Person relationships remain valid link targets so old records are not broken.
- Duplicate active links return `409`.
- Unlinking is non-destructive: `DocumentLink.is_active` becomes false.
- Re-linking reactivates the same durable row instead of creating a duplicate.

### Lifecycle API
- `POST /api/v1/documents/{document_id}/archive`
- `POST /api/v1/documents/{document_id}/restore`

Lifecycle semantics:
- `active` -> mutable
- `archived` -> readable/downloadable but frozen against new versions or link changes
- restore returns an archived document to `active`
- archive/restore calls are idempotent and do not create duplicate Audit events
- no physical file deletion is introduced
- `disabled` remains an internal/future state and is not exposed as a B5.3 transition

### Audit events
- `document.linked`
- `document.unlinked`
- `document.archived`
- `document.restored`

Existing B5.2 events remain:
- `document.created`
- `document.version.created`
- `document.downloaded`

### Concurrency
Lifecycle, link mutation, and version creation serialize on the Document row with
`SELECT ... FOR UPDATE` in PostgreSQL. Authorization and active-state checks are
performed against the locked row before mutation.

### Migration 0007
Adds:
- `document_links.is_active`
- unique durable link constraint on `(document_id, entity_type, entity_id)`
- active-link lookup indexes
- `(organization_id, status)` document lifecycle index

## Explicitly deferred
- Customer/Supplier/Contract/Task/Operation link types until those modules exist
- DocumentPermission enforcement and person-specific sharing
- destructive deletion
- Legal Hold / retention schedule engine
- disabled-state public API
- antivirus/malware scanning
- S3/MinIO implementation

## Acceptance tests
B5.3 adds coverage for:
- scoped Person links
- cross-organization Person target rejection
- people.read requirement for Person linking
- organization-link ownership boundary
- duplicate link conflict
- non-destructive unlink/re-link
- link-based document filtering
- archive freezes mutation
- archived download still works
- restore enables mutation again
- archive/restore Audit behavior
- link filter input validation
