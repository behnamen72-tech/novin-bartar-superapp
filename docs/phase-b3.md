# Phase B3 — Authorization: Roles, Permissions, Organization Scope

Status: Ready for Claude Review

## Goal
Implement server-side authorization after B2 authentication.

## Model
Authorization decision = User + Role + Permission + Organization Scope.

### Role
Reusable access bundle such as `company_reader` or `super_admin`.

### Permission
Atomic action capability, for example:
- organization.read
- organization.manage
- people.read
- people.manage
- users.read
- users.manage
- access.read
- access.manage

### Organization Scope
Every user-role assignment must name an Organization. There is no unscoped/global assignment.

Scope modes:
- SELF: exact organization only
- SELF_AND_DESCENDANTS: exact organization plus its child organizations

A Holding assignment with descendants can span its companies. A Company assignment cannot reach a sibling Company.

## Security properties
- Deny by default.
- Roles/permissions are not stored in JWT.
- Authorization is evaluated from current database state on every protected request.
- Disabled roles/permissions/assignments take effect immediately.
- Expired/not-yet-active assignments do not grant access.
- Inactive organizations do not grant or receive scope.
- Cross-company sibling access is denied unless a higher Organization scope explicitly includes it.

## API
Authenticated self-service inspection only:
- GET /api/v1/access/me
- GET /api/v1/access/organizations/{organization_id}/permissions/{permission_code}

No public/admin Role CRUD endpoint is exposed yet. Administrative access-management endpoints can be added only after the same B3 guards protect them.

## Bootstrap
`python scripts/bootstrap_access.py`
creates/reuses a `super_admin` role, attaches all Core permissions, and assigns it to an existing user under a selected Organization using SELF_AND_DESCENDANTS scope.

## Migration hardening
The prior B2 migration was made safe for pre-existing B1 users: legacy rows receive an intentionally invalid password marker before `password_hash` becomes NOT NULL, so old accounts remain unable to authenticate until explicitly assigned a valid password.
