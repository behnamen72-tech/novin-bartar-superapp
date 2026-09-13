# Phase B5.5 — Document Operations

## Purpose
Complete the Documents Core as an operational document platform without
absorbing responsibilities that belong to Workflow, Notifications, global
Search, or future business modules.

## Added capabilities

### Metadata
Documents now support:
- description
- priority (`low`, `normal`, `high`, `critical`)
- optional category
- optional expiration timestamp
- optional retention policy
- snapshotted retention review timestamp

Metadata mutations:
- require existing `documents.manage`
- remain bounded by B3 Organization Scope
- reuse B5.4 restrictive document ACLs
- are blocked while the document is archived
- create `document.metadata.updated` Audit events only when persisted values change

### Categories
Organization-scoped hierarchical categories support:
- stable organization-unique code
- display name and description
- optional parent category
- cycle prevention
- soft deactivation / restore
- no physical delete
- no cross-organization parent or document assignment

Active children must be deactivated before their parent can be deactivated.
Historical documents may continue referencing an inactive category; inactive
categories cannot be newly assigned.

### Expiration
`expires_at` is the source of truth. No periodically-mutated expiration status
is stored in the database.

`GET /api/v1/documents/expiring` derives current state at request time and
retains both Organization Scope and B5.4 document ACL filtering.

Expiration is informational only; it does not gate document read/download access
(the same principle used for archived documents).

B5.5 does not send notifications. The future Notifications Core can consume
expiration queries/events without moving notification logic into Documents.

### Retention
Organization-scoped retention policies support:
- stable organization-unique code
- number of retention days
- basis: `created_at` or `expires_at`
- soft deactivation / restore

Assigning a policy calculates and stores `retention_review_at` as a snapshot.
Changing the policy later does not silently rewrite deadlines on existing
documents. A document deadline is recalculated when that document's assigned
policy or relevant expiration timestamp changes.

Retention never physically deletes a document in B5.5. A due deadline only
means the document is ready for future review/action.

### Timeline
`GET /api/v1/documents/{id}/timeline` reuses immutable B4 Audit data.

Timeline access requires BOTH:
- access to the document through `documents.read` + organization/document ACL
- `audit.read` in the same organization

This avoids introducing a second, weaker Audit surface.

### Search foundation
The existing Documents list API now supports bounded metadata filters:
- `q` across title, document type, and description
- category
- priority
- expiration bounds
- existing document type, status, organization, and entity-link filters

This is not the global Search Core. PostgreSQL full-text/trigram optimization is
deferred until profiling/data volume requires it.

## New/extended API

Documents:
- `GET /api/v1/documents?q=...&category_id=...&priority=...`
- `PATCH /api/v1/documents/{id}/metadata`
- `GET /api/v1/documents/expiring`
- `GET /api/v1/documents/retention-due`
- `GET /api/v1/documents/{id}/timeline`

Categories:
- `GET /api/v1/document-categories`
- `POST /api/v1/document-categories`
- `PATCH /api/v1/document-categories/{id}`
- `DELETE /api/v1/document-categories/{id}` (soft deactivation)
- `POST /api/v1/document-categories/{id}/restore`

Retention policies:
- `GET /api/v1/document-retention-policies`
- `POST /api/v1/document-retention-policies`
- `PATCH /api/v1/document-retention-policies/{id}`
- `DELETE /api/v1/document-retention-policies/{id}` (soft deactivation)
- `POST /api/v1/document-retention-policies/{id}/restore`

## Migrations

### 20260910_0009
Adds the B5.4 review-requested missing index:
- `ix_documents_document_type`

### 20260910_0010
Adds B5.5 category/retention tables and document metadata fields/indexes.

## Deliberately deferred
- automatic deletion from retention rules
- legal hold
- workflow approval state machine
- expiration notifications
- global/federated Search Core
- full-text/trigram search indexes
- large-file/range streaming
- new DocumentLink target types for business modules not yet implemented

Status: Ready for independent Claude review.
