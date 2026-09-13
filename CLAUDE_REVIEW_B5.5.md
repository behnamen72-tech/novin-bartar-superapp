# Claude Review Request — Phase B5.5

Project: Novin Bartar Super App
Phase: B5.5 — Document Operations
Base: Claude-approved B5.4

Please review the actual full source package, not only this summary.

## Implemented

### B5.4 review follow-up
- Migration `20260910_0009` creates the previously missing
  `ix_documents_document_type` index.
- LocalStorage whole-file reads remain unchanged and are explicitly recorded in
  `docs/technical-debt.md` as a future large-file streaming optimization.

### Metadata
Document now supports:
- description
- priority
- category_id
- expires_at
- retention_policy_id
- retention_review_at

Metadata writes reuse B3/B5.4 authorization, lock the document row, are blocked
for archived documents, and write `document.metadata.updated` Audit events only
when values actually change.

### Categories
New organization-scoped hierarchical `DocumentCategory`:
- unique stable code per organization
- optional parent
- same-organization parent validation
- cycle prevention
- soft deactivation/restore
- active-child protection on deactivation
- inactive categories cannot be newly assigned

### Expiration
No mutable expiration-state column is stored. `expires_at` remains the source of
truth and `/documents/expiring` derives current state. The query applies the
same organization + document ACL predicate as normal document listing.

### Retention
New organization-scoped `RetentionPolicy`:
- retention_days
- basis = created_at | expires_at
- soft deactivate/restore

Documents store a snapshotted `retention_review_at`. Updating a policy does NOT
silently recalculate old document deadlines. Assigning/changing the policy or
changing the relevant expiration input recalculates the document snapshot.
No automatic deletion exists.

### Timeline
`/documents/{id}/timeline` reads immutable B4 Audit events. It requires:
- document read access, including B5.4 restrictive ACL
- `audit.read` in the document organization

### Search foundation
`GET /documents` now supports:
- q (title/type/description)
- category_id
- priority
- expires_before / expires_after
plus all existing filters.

This deliberately does not implement the global Search Core or advanced
PostgreSQL full-text/trigram indexing.

## New APIs
- PATCH `/api/v1/documents/{id}/metadata`
- GET `/api/v1/documents/expiring`
- GET `/api/v1/documents/retention-due`
- GET `/api/v1/documents/{id}/timeline`
- CRUD-style soft-lifecycle APIs under `/api/v1/document-categories`
- CRUD-style soft-lifecycle APIs under `/api/v1/document-retention-policies`

## Verification performed
- pytest: **70 passed**
- compileall: **passed**
- PostgreSQL Alembic offline SQL generation through `0010`: **passed**
- Ruff/Mypy unavailable in ChatGPT runtime; no pass claim
- live PostgreSQL migration execution not claimed

## Please focus review on
1. IDOR and Organization Scope for categories/policies/metadata
2. preservation of B5.4 restrictive document ACL semantics in search/expiration/retention queries
3. category hierarchy cycle/deactivation behavior
4. retention snapshot semantics and hidden retroactive-change risks
5. timeline `audit.read` boundary and information disclosure
6. migration 0009/0010 correctness and index duplication/name conflicts
7. concurrency around document metadata updates
8. error semantics / enumeration risks
9. query scalability and whether any index is a merge blocker
10. regression risk against B5.1-B5.4
11. whether B5 can be considered complete after this phase

Status: Ready for Claude Review.
