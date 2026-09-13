# Claude Review Request — Phase B5.3

Project: Novin Bartar Super App
Phase: B5.3 — Document Linking & Lifecycle
Base: Claude-approved B5.2 Revision 2
Status: Ready for independent review

## What was implemented

### Linking
- GET `/api/v1/documents/{document_id}/links`
- POST `/api/v1/documents/{document_id}/links`
- DELETE `/api/v1/documents/{document_id}/links/{link_id}`
- list filter: `entity_type` + `entity_id`

Enabled link types in B5.3:
- organization
- person

Security/integrity:
- document organization remains the security owner
- organization link must equal the document owner organization
- person link requires `people.read` in the document organization
- person must have a PersonOrganizationRelationship to the document organization
- historical relationships are accepted intentionally
- arbitrary/future entity types fail closed until their modules exist
- duplicate active link -> 409
- unlink is logical (`is_active=false`), never row deletion
- re-link reactivates the same durable row

### Lifecycle
- POST `/api/v1/documents/{id}/archive`
- POST `/api/v1/documents/{id}/restore`

Rules:
- active documents are mutable
- archived documents remain readable/downloadable
- archived documents reject new versions and link/unlink mutation with 409
- restore re-enables mutation
- archive/restore are idempotent without duplicate Audit events
- no physical file deletion
- disabled remains reserved/deferred

### Audit
New actions:
- document.linked
- document.unlinked
- document.archived
- document.restored

### Concurrency
Document lifecycle, link mutation, and version allocation use the Document row
as a PostgreSQL `SELECT ... FOR UPDATE` serialization point. Authorization and
state are re-checked against the locked row.

### Migration
`20260909_0007_documents_linking_lifecycle.py`
- adds `document_links.is_active`
- unique durable link target constraint
- active-link indexes
- organization/status lifecycle index

## Verification in ChatGPT runtime
- pytest: 50 passed
- Python compileall: passed
- Alembic PostgreSQL offline SQL generation through 0007: passed
- ruff/mypy unavailable in this runtime; no success claim is made for them

The final ZIP is also extracted into a fresh directory and tested after packaging
before delivery, to avoid the B5.2 packaging regression.

## Please review specifically
1. IDOR and organization-scope behavior for link APIs.
2. Whether Person target validation is sufficiently fail-closed.
3. Whether requiring `people.read` for Person linking is the correct privilege boundary.
4. Link deactivation/reactivation history semantics.
5. Lifecycle rule: archived = readable/downloadable but immutable.
6. Row-lock ordering/deadlock or TOCTOU concerns.
7. Migration 0007 safety for an existing B5.2 database.
8. Link-based list filtering for data leakage or duplicate result issues.
9. Whether anything should block merge.

## Deliberately not included
- DocumentPermission enforcement
- Customer/Supplier/Contract/Task/Operation links
- Legal Hold / retention engine
- physical deletion
- disabled-state API
- antivirus
- S3/MinIO
