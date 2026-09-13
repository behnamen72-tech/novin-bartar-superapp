# Phase B5.4 — Document-Level Access Control

## Purpose
B5.4 activates the `DocumentPermission` foundation created in B5.1 and layers
role-based document ACLs on top of the existing B3 authorization model.

The key rule is:

> A document ACL can only restrict an authority that already exists through
> Role + Permission + Organization Scope. It never grants cross-organization
> access or bypasses a missing `documents.read` / `documents.manage` permission.

## Access model

### Inherited mode
A document with no active `DocumentPermission` rows inherits the normal B3
organization-level behavior.

### Restricted mode
The moment a document has at least one active `DocumentPermission` row, it is
restricted to matching effective roles:

- `read` ACL permits document read/list/download for a role that currently grants
  `documents.read` in that document's organization scope.
- `manage` ACL permits document mutation for a role that currently grants
  `documents.manage` in that organization scope.
- A `manage` ACL can also satisfy the document-level part of a read check, but
  the user still needs the base `documents.read` permission through that same
  effective role.

Users inside the organization who fail only the document ACL receive a generic
404 for direct document access, preventing confidential-document enumeration.
Users who fail the outer organization permission boundary still receive 403.

## ACL administration API

- `GET /api/v1/documents/{document_id}/permissions`
- `POST /api/v1/documents/{document_id}/permissions`
- `DELETE /api/v1/documents/{document_id}/permissions/{document_permission_id}`

Create payload:

```json
{
  "role_id": "<uuid>",
  "permission_type": "read | manage"
}
```

ACL rows are logically revoked with `is_active=false`; they are not physically
deleted. Re-granting the same role/type reactivates the durable row.

## Safe activation / lockout prevention

To enter restricted mode, the first active ACL row must be `manage` and normally
must target one of the current actor's effective `documents.manage` roles. This
prevents a manager from accidentally restricting a document and immediately
locking themselves out.

While a document is restricted, revoking the last `manage` row is rejected if
other ACL rows would remain. Removing the final ACL row entirely is allowed and
returns the document to inherited mode.

## Recovery path

`access.manage` is an explicit, organization-scoped break-glass permission for
ACL administration only. It can list/grant/revoke document ACL rows but it does
**not** grant content read/download or normal document-management authority.

This prevents permanent ACL lockout when role assignments change outside the
Documents module while preserving separation between security administration
and document content access.

## Role target validation

A role can be added to a document ACL only when:

1. the role is active;
2. it contains the required active base permission (`documents.read` or
   `documents.manage`);
3. it has at least one current effective assignment covering the document's
   organization; and
4. that effective assignment belongs to an active User and active Person.

This prevents cross-company or dead-role ACL entries.

## List-query security

Document list filtering is performed in SQL. The query first applies the set of
organizations authorized by B3, then applies the document ACL predicate. A
restricted document is therefore absent from list responses for non-allowlisted
roles; the application does not load all documents and filter them afterward.

## Audit

New immutable audit actions:

- `document.permission.granted`
- `document.permission.revoked`

Audit metadata records reactivation and whether revocation leaves the document
in `restricted` or `inherited` ACL mode.

## Migration

Migration `20260910_0008_document_level_access_control.py` fails closed if any pre-B5.4 `document_permissions` rows already exist (because those rows were previously unenforced and cannot safely be assumed intentional), then adds:

- unique `(document_id, role_id, permission_type)` constraint;
- `(document_id, is_active, permission_type)` index;
- `(role_id, is_active)` index.

No new permission codes are introduced. B5.4 reuses:

- `documents.read`
- `documents.manage`
- `access.manage` for ACL recovery only.

## Deliberately deferred

- direct per-user document grants;
- group/team ACL subjects beyond Role;
- public/external sharing links;
- time-limited document grants;
- approval workflow for ACL changes;
- UI for ACL management.
