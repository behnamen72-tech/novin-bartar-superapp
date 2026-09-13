# Phase B6.7 — Operational Documents UI

B6.7 exposes the already-approved B5 Documents platform through the operational
B6 frontend. It does not introduce a second authorization model: every document
read/write continues to be authorized by FastAPI using B3 Organization Scope and
B5.4 restrictive document ACL rules.

## User operations

The Documents screen now supports:

- authorized document list/search/filtering by organization, status, and priority
- document creation in a manageable organization
- metadata editing (title, type, description, priority, category, expiry, retention policy)
- archive and restore
- append-only version upload
- download of the latest version
- Person/owner-Organization links and unlinking
- Audit-backed document activity timeline
- organization-scoped category administration
- organization-scoped retention-policy administration

Expiry values entered with `datetime-local` are converted to an ISO-8601 UTC value
before submission so the backend timezone-aware schema contract is preserved.
Expiration remains informational only; it does not block read/download access.
Archived documents remain readable/downloadable but cannot accept content/link
mutations until restored, matching B5 lifecycle semantics.

## BFF routes

Documents:
- GET/POST `/api/core/documents`
- GET `/api/core/documents/{documentId}`
- PATCH `/api/core/documents/{documentId}/metadata`
- POST `/api/core/documents/{documentId}/archive`
- POST `/api/core/documents/{documentId}/restore`
- POST `/api/core/documents/{documentId}/versions`
- GET `/api/core/documents/{documentId}/download`
- GET/POST `/api/core/documents/{documentId}/links`
- DELETE `/api/core/documents/{documentId}/links/{linkId}`
- GET `/api/core/documents/{documentId}/timeline`

Document configuration:
- GET/POST `/api/core/document-categories`
- PATCH/DELETE `/api/core/document-categories/{categoryId}`
- POST `/api/core/document-categories/{categoryId}/restore`
- GET/POST `/api/core/document-retention-policies`
- PATCH/DELETE `/api/core/document-retention-policies/{policyId}`
- POST `/api/core/document-retention-policies/{policyId}/restore`

All unsafe methods use `proxyAuthenticatedRequest()`, preserving the centralized
B6.2 CSRF/origin guard and HttpOnly session architecture.

## Download handling

Binary download uses a dedicated authenticated BFF proxy. It forwards the bearer
access token only server-to-server, never exposes it to browser JavaScript, copies
only the content headers needed for a file response, adds `Cache-Control: no-store,
private`, and preserves `X-Content-Type-Options: nosniff`.

The current BFF implementation buffers the response before returning it to the
browser. This is acceptable under the current 50 MiB upload limit but is tracked as
a production scaling debt; future large-object delivery should stream end-to-end.

## Authorization boundary

Frontend permission/scope checks only control affordances. They can conservatively
hide a button, but they cannot authorize an operation. Backend services always
re-check:

- `documents.read` / `documents.manage`
- Organization Scope
- document lifecycle state
- B5.4 document ACL visibility/management rules
- Person-link `people.read` requirements
- transaction and Audit invariants

This keeps cross-organization isolation and 404 anti-enumeration semantics intact.
