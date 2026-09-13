# Phase B6.8 — Access, Roles, Permissions & Document ACL UI

B6.8 makes the B5.6 Access Administration APIs operational in the B6 frontend and
adds a UI for the B5.4 document-level restrictive ACL. No privilege calculation is
moved into the browser; FastAPI remains the authority for every sensitive change.

## Access administration

The Access screen supports:

- viewing active/inactive User Role Assignments
- creating a Role Assignment with Organization Scope (`self` or
  `self_and_descendants`) and optional start/end time
- activating/deactivating an assignment
- listing custom/system roles
- creating organization-owned custom roles
- editing custom role name/description
- activating/deactivating custom roles
- granting/revoking Permission membership on a custom role
- viewing the canonical Permission catalog

System and legacy global roles remain immutable through the runtime UI/API.
Frontend Organization Scope calculations are UX-only. The backend independently
checks `access.manage`, role ownership, affected organizations, target Person
relationship, role activity, and capability delegation.

## Privilege-escalation boundary

B6.8 deliberately does not invent numeric role levels. Existing B5.6
capability-set rules remain authoritative:

- an actor may only delegate a Role permission set they can delegate across the
  entire affected scope
- organization-owned roles cannot be assigned outside their owner subtree
- mutations that would remove the last effective `access.manage` administrator
  are rejected
- role changes are locked/audited transactionally in the backend

The browser may disable obviously impossible operations, but any false-positive UI
affordance fails closed at the backend.

## Document-level ACL

The Documents detail view now exposes an ACL tab to authorized document/access
managers. Semantics remain exactly those approved in B5.4:

- no active ACL rows => inherited organization-level document access
- any active ACL rows => restrictive allowlist mode
- ACL never creates cross-organization access and never substitutes for B3
  `documents.read`/`documents.manage`
- the first ACL row must be a `manage` grant that preserves management control
- restricted mode must retain at least one active `manage` ACL while other ACL
  rows remain
- revoking the final ACL returns the document to inherited mode

Role choices shown by the UI are filtered by the matching document permission
capability where role catalog access is available. The backend additionally
requires the role to have an effective assignment for the document organization.

## Break-glass ACL recovery

Because B5.4 intentionally allows scoped `access.manage` to administer a document
ACL without granting document content access, B6.8 provides an independent recovery
tool on the Access screen. The operator supplies a known document UUID and the UI
calls only the ACL endpoints; it does not fetch or reveal the document title,
metadata, file, or download content.

This preserves the separation between:

- ACL administration/recovery (`access.manage`), and
- content authorization (`documents.read` / `documents.manage` plus any active
  restrictive ACL).

If the actor lacks `access.read`, the UI does not enumerate role choices. Existing
ACL rows can still be presented by role identifier and backend rules remain the
source of truth for any permitted revocation.

## BFF routes

Access administration:
- GET `/api/core/access/permissions`
- GET/POST `/api/core/access/roles`
- PATCH `/api/core/access/roles/{roleId}`
- PATCH `/api/core/access/roles/{roleId}/status`
- POST/DELETE `/api/core/access/roles/{roleId}/permissions/{permissionCode}`
- POST `/api/core/access/assignments`
- PATCH `/api/core/access/assignments/{assignmentId}/status`

Document ACL:
- GET/POST `/api/core/documents/{documentId}/permissions`
- DELETE `/api/core/documents/{documentId}/permissions/{permissionId}`

All unsafe BFF routes use the centralized authenticated proxy and therefore retain
B6.2 CSRF/origin enforcement. Dynamic path parameters are passed through
`encodeURIComponent()` before backend routing.

## Intentional conservative selector behavior

B6.8 uses already-authorized Organization, People/User, Role, and Permission data
to populate selectors. A deliberately unusual role that can perform a write but
cannot read the corresponding selector dataset may see fewer UI affordances. This
is fail-closed UX, not a backend capability change, and is covered by the existing
permission-scoped selector technical-debt item.
