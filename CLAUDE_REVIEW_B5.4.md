# Claude Review Request — Phase B5.4

Project: Novin Bartar Super App
Phase: B5.4 — Document-Level Access Control
Base: Claude-approved B5.3
Status: Ready for independent review

## What changed

B5.4 activates the existing `DocumentPermission` foundation as a restrictive,
role-based document ACL layered on top of B3 authorization.

### Core semantics
- No active ACL rows -> document inherits B3 organization access.
- One or more active ACL rows -> document enters restricted mode.
- Organization permission is always checked first.
- ACL never grants access across organizations and never substitutes for missing
  `documents.read` / `documents.manage`.
- Direct same-org ACL denial is normalized to generic 404 to avoid confidential
  document enumeration.

### ACL types
- `read`
- `manage`

For read, an effective role must currently grant `documents.read` and match an
active document `read` or `manage` ACL row.

For manage, an effective role must currently grant `documents.manage` and match
an active document `manage` ACL row.

### API
- GET `/api/v1/documents/{id}/permissions`
- POST `/api/v1/documents/{id}/permissions`
- DELETE `/api/v1/documents/{id}/permissions/{permission_id}`

Rows are logically revoked (`is_active=false`), not physically deleted.
Re-grant reactivates the durable row.

### Lockout prevention
- First active ACL must be `manage`.
- For a normal document manager, the first manage ACL must target one of that
  actor's currently effective `documents.manage` roles.
- The last manage ACL cannot be removed while other ACL rows remain.
- Removing the final ACL row is allowed and intentionally returns the document
  to inherited organization-level access.

### Break-glass administration
Existing `access.manage`, scoped through B3 to the document organization, can
administer ACL rows even when document-manage ACL access is lost. It does NOT
provide read/download/content access.

Please review whether this is the correct recovery boundary.

### Role target validation
A target Role must:
- be active;
- contain the required active canonical permission;
- have a current effective assignment covering the document organization;
- have at least one such assignment whose User and Person are active.

### List security
Document ACL filtering is part of the SQL query, after determining B3-authorized
organization IDs. Restricted documents are not fetched and then filtered in
Python.

### Existing operations now covered by ACL
- detail
- list/search by link
- download
- version upload
- archive/restore
- link/unlink

### Audit
New actions:
- `document.permission.granted`
- `document.permission.revoked`

### Small B5.2 correctness fix
The upload route no longer performs a post-commit `documents.read` re-fetch only
for response shaping. A user with legitimate `documents.manage` but no separate
`documents.read` permission can now receive the successful 201 response for the
mutation they already committed. Read endpoints remain separately protected.

### Migration 0008
Fails closed if any pre-B5.4 `document_permissions` rows exist, because older rows were never enforced and cannot safely be activated without explicit review. Then adds:
- unique `(document_id, role_id, permission_type)`
- index `(document_id, is_active, permission_type)`
- index `(role_id, is_active)`

## Verification
- pytest: 59 passed
- compileall: passed
- PostgreSQL Alembic offline SQL generation through 0008: passed
- ruff/mypy unavailable in ChatGPT runtime; no pass claim

The final ZIP is extracted into a fresh directory and re-tested before delivery.

## Please review specifically
1. Whether ACL semantics correctly remain restrictive rather than additive.
2. Same-organization IDOR/enumeration behavior (404 vs 403 boundary).
3. Whether exact-role evaluation remains consistent with B3 assignment scope,
   dates, active state, and permission state.
4. SQL list predicate for ACL leakage or incorrect role combination.
5. First-ACL lockout prevention and last-manager invariant.
6. Whether `access.manage` is an appropriately narrow recovery authority.
7. Cross-organization role-target validation.
8. Audit semantics and logical revoke/reactivation history.
9. Migration 0008 safety for an existing B5.3 DB.
10. Any concurrency issue around ACL grant/revoke and other document mutations.
11. Any issue that should block merge.

## Deliberately deferred
- direct per-user ACL entries
- teams/groups as ACL subjects
- expiring grants
- external/public document sharing
- ACL-management frontend UI
