# Claude Review Request — B5.6 Core Write APIs

## Review instruction
Please review the **actual attached source code**, migration, and tests. Do not
rely only on this summary.

## Baseline
B5.6 is implemented on top of the user-supplied B5.5 full-review package.
B1-B4 previously received an independent security review; B5.1-B5.5 had their
own review cycle. This request is specifically for the B5.6 implementation diff
and regression impact.

## Purpose
Make the Core operational before B6 UI so the future frontend can create and
manage real organizations, people, users, and access state rather than being
read-only.

## Important implementation decisions

### Existing permission model reused
No parallel permission system or new granular create/update permission family
was introduced. Runtime writes use the existing canonical permissions:
- `organization.manage`
- `people.manage`
- `users.manage`
- `access.manage`

### Organization writes
New runtime APIs:
- POST `/api/v1/organizations`
- PATCH `/api/v1/organizations/{organization_id}`
- PATCH `/api/v1/organizations/{organization_id}/status`

Root Holding creation remains bootstrap-only because there is no pre-existing
organization scope against which it can be authorized. Runtime child creation
must pass the existing B1 hierarchy validator and, after flush, the actor must
actually have descendant-effective `organization.manage` on the new child.
Reactivation of an inactive organization uses a dedicated B3 policy helper that
allows only the target itself to be inactive; active ancestor/scope rules remain
required.

### People writes
New APIs:
- POST `/api/v1/people`
- PATCH `/api/v1/people/{person_id}`
- PATCH `/api/v1/people/{person_id}/status`
- POST `/api/v1/people/{person_id}/relationships`
- PATCH `/api/v1/people/{person_id}/relationships/{relationship_id}/status`

A Person is global/shared. Mutating global Person fields/status requires
`people.manage` across every active organization relationship, avoiding one
company mutating shared identity data visible to another. Relationship-specific
writes are authorized against the relationship organization only.

If Person is linked to a privileged User, Person status changes also require the
actor to dominate that User's access footprint, preventing `people.manage` from
becoming a route to disable a higher-privilege account.

An organization relationship cannot be deactivated while an active User role
assignment is rooted at that same organization.

### User writes
New APIs:
- POST `/api/v1/users`
- PATCH `/api/v1/users/{user_id}`
- PATCH `/api/v1/users/{user_id}/status`
- POST `/api/v1/users/{user_id}/password-reset`

No `UserOrganizationMembership` model was added. Business affiliation continues
to use `PersonOrganizationRelationship`; authorization scope continues to use
`UserRoleAssignment` from B3.

Create requires `users.manage` across target Person relationships. Existing
privileged User mutation additionally uses capability-dominance checks across
all effective target access assignments. Self-deactivation is blocked.
Passwords are Argon2 hashed and password/hash material is never sent to Audit.
Usernames containing `@` are rejected because B2 deliberately routes `@`
identifiers as email logins.

### Role ownership and runtime role management
Migration `20260910_0011` adds nullable `Role.organization_id`.
- existing system/legacy global roles remain NULL and immutable via runtime API
- new runtime-created custom roles are organization-owned
- custom roles can be assigned only within the owner organization subtree

New APIs:
- GET `/api/v1/access/roles`
- GET `/api/v1/access/permissions`
- POST `/api/v1/access/roles`
- PATCH `/api/v1/access/roles/{role_id}`
- PATCH `/api/v1/access/roles/{role_id}/status`
- POST `/api/v1/access/roles/{role_id}/permissions/{permission_code}`
- DELETE `/api/v1/access/roles/{role_id}/permissions/{permission_code}`
- POST `/api/v1/access/assignments`
- PATCH `/api/v1/access/assignments/{assignment_id}/status`

### Privilege escalation prevention
No numeric role-level hierarchy was introduced. Delegation is capability-based.
For every active organization covered by an assignment scope:
1. actor must have `access.manage`;
2. actor must already effectively possess every active permission in the target
   role.

Therefore a SELF-only company access manager cannot grant
SELF_AND_DESCENDANTS access if the actor lacks authority in a branch.

Role-definition mutation also evaluates every currently affected assignment
scope, preventing a permission added to an already-used role from silently
escalating users outside the actor's authority.

### Last-manager protection
B5.6 rejects changes that would remove the last effective `access.manage`
holder from an affected organization through assignment deactivation, role
deactivation, or `access.manage` permission removal.

### Audit / transactions
B4 `record_audit_event` is reused in the same SQLAlchemy session before commit.
B5.6 has a dedicated test proving an Organization write is rolled back if Audit
recording fails before commit.

Representative new actions:
- organization.created / updated / status.changed
- person.created / updated / status.changed
- person.relationship.created / status.changed
- user.created / updated / status.changed / password.reset
- role.created / updated / status.changed
- permission.granted / permission.revoked
- role.assigned / role.assignment.reactivated / role.assignment.status.changed

## Verification claimed by ChatGPT runtime
- pytest: **90 passed**
- compileall: passed
- OpenAPI generation: passed (46 paths)
- Alembic PostgreSQL offline SQL generation through 0011: passed
- Ruff/Mypy unavailable in runtime; no pass claim
- no live-PostgreSQL migration execution claim

## Please focus review on
1. IDOR / organization-scope bypass in every new write endpoint
2. capability-based privilege escalation prevention correctness
3. shared Person / global User administration boundaries
4. whether User mutation can still bypass higher privilege through another path
5. role ownership model and legacy/system-role immutability
6. role permission changes when a role already has assignments
7. `SELF_AND_DESCENDANTS` delegation semantics
8. access-assignment reactivation checks
9. last-access-manager protection correctness and edge cases
10. Person relationship vs access-assignment consistency
11. transaction + Audit atomicity
12. migration 0011 safety and impact on B5 document ACL role references
13. any race conditions that require PostgreSQL row locking beyond current locks
14. whether anything should block entering B6

## Status
B5.6 implementation complete in this package; **awaiting Claude code/security review before B6**.
