# Phase B5.6 — Core Write APIs

## Purpose
Make the approved Core operational before B6 UI. B5.6 adds controlled write
operations for Organizations, People, Users, and Access administration while
reusing the existing B3 authorization engine and B4 immutable Audit system.

## Permission model
B5.6 deliberately reuses the existing canonical permissions rather than adding
parallel granular permission codes:

- `organization.manage`
- `people.manage`
- `users.manage`
- `access.manage`

Read APIs continue to use the matching `.read` permissions.

## Organization write APIs

- `POST /api/v1/organizations`
- `PATCH /api/v1/organizations/{organization_id}`
- `PATCH /api/v1/organizations/{organization_id}/status`

Root Holding creation remains bootstrap-only because a new root has no existing
organization boundary against which B3 authorization can be evaluated.
Runtime creation is limited to descendants of an organization the actor can
manage with descendant-capable scope. B1 hierarchy validation remains the
canonical structure validator.

Organization re-parenting/type mutation is deliberately not exposed in B5.6.
It is a higher-risk structural operation and should receive its own explicit
business rules if required later.

## People write APIs

- `POST /api/v1/people`
- `PATCH /api/v1/people/{person_id}`
- `PATCH /api/v1/people/{person_id}/status`
- `POST /api/v1/people/{person_id}/relationships`
- `PATCH /api/v1/people/{person_id}/relationships/{relationship_id}/status`

A Person is global/shared. Therefore modification of global Person fields or
status requires `people.manage` across every active organization relationship
of that Person. Relationship-specific changes are authorized against only that
relationship's organization. This prevents one company from mutating shared
identity data visible to another company.

## User write APIs

- `POST /api/v1/users`
- `PATCH /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}/status`
- `POST /api/v1/users/{user_id}/password-reset`

User remains a one-to-one login identity linked to Person. No separate
`UserOrganizationMembership` model/API was introduced: business affiliation is
represented by `PersonOrganizationRelationship`, while access scope is represented
by `UserRoleAssignment` as established in B1/B3.

User administration requires `users.manage` across the target Person's active
organization relationships. In addition, mutation of an already-privileged User
(email/username/status/password) is blocked unless the actor can dominate the
User's current access footprint, preventing identity administration from becoming
a privilege-escalation path. Passwords/hashes are never included in audit state.
Self-deactivation via the admin status endpoint is blocked.

## Access administration APIs

Read support for B6 selectors:

- `GET /api/v1/access/roles`
- `GET /api/v1/access/permissions`

Custom role management:

- `POST /api/v1/access/roles`
- `PATCH /api/v1/access/roles/{role_id}`
- `PATCH /api/v1/access/roles/{role_id}/status`
- `POST /api/v1/access/roles/{role_id}/permissions/{permission_code}`
- `DELETE /api/v1/access/roles/{role_id}/permissions/{permission_code}`

Assignments:

- `POST /api/v1/access/assignments`
- `PATCH /api/v1/access/assignments/{assignment_id}/status`

### Organization-owned custom roles
Migration `20260910_0011` adds nullable `roles.organization_id`.

- Existing bootstrap/system and legacy global roles remain `NULL` and are
  immutable through runtime APIs.
- New custom roles must have an owning organization.
- Organization-owned roles can be assigned only inside the owner organization's
  subtree.
- System/global role definitions cannot be edited through these APIs.

This adds an administration boundary without rewriting the B3 assignment model.

### Privilege-escalation prevention
B5.6 does **not** introduce numeric role levels. Delegation is capability-based:

1. For every organization covered by the proposed assignment scope, the actor
   must have `access.manage`.
2. For every covered organization, every active permission in the target role
   must already be an effective permission of the actor.
3. `SELF_AND_DESCENDANTS` therefore requires authority across every active
   descendant it would cover, not just the root organization.
4. Role-definition changes are evaluated across every currently affected
   assignment scope, so adding a permission to an already-used role cannot
   silently escalate users in organizations the actor does not control.
5. A target user must have an active Person relationship with the assignment's
   root organization.
6. Operations that would remove the last effective `access.manage` holder from
   an organization are rejected.

## Audit / transaction rule
Every successful Core write records its B4 Audit event in the same SQLAlchemy
session before commit. A failure before commit rolls back both business mutation
and audit mutation.

Representative actions include:

- `organization.created`, `organization.updated`, `organization.status.changed`
- `person.created`, `person.updated`, `person.status.changed`
- `person.relationship.created`, `person.relationship.status.changed`
- `user.created`, `user.updated`, `user.status.changed`, `user.password.reset`
- `role.created`, `role.updated`, `role.status.changed`
- `permission.granted`, `permission.revoked`
- `role.assigned`, `role.assignment.reactivated`, `role.assignment.status.changed`

## Migration

`20260910_0011_core_write_role_ownership.py`

Adds:

- `roles.organization_id` nullable FK -> `organizations.id` (`RESTRICT`)
- `ix_roles_organization_id`

No other B5.6 write flow requires a schema change; existing B1-B4 models already
contain the required state.

## Verification target
B5.6 must pass the complete existing regression suite plus dedicated write tests
covering:

- descendant-only Organization creation
- scope denial and rollback on audit failure
- shared-Person mutation boundaries
- password hashing/audit secret exclusion
- identity-admin privilege escalation prevention
- custom role ownership/system-role immutability
- permission delegation capability bounds
- assignment scope bounds
- last-access-manager protection
