# Phase B6.5 — Organization Management UI

B6.5 turns the Organization screen into the first operational Core management
screen. It uses the B5.6 write APIs and keeps FastAPI/B3 authorization as the
security authority.

## Delivered operations

- create Company / Branch / Unit under hierarchy-valid parents
- edit organization name and code
- activate/deactivate organizations with hierarchy-aware UX guards
- retain inactive descendants in the management list when an active ancestor
  manager is authorized to reactivate them
- keep root Holding status bootstrap-only to prevent irreversible API self-lockout
- preserve read-only rendering for organizations outside the actor's manage scope

## Security model

The browser receives no new authority. Frontend manage-scope calculations only
control affordances. Every mutation travels through the authenticated BFF and is
re-authorized by the existing B5.6 service layer using B3 scope semantics.

`GET /api/v1/organizations?include_inactive=true` is an operational management
view. It returns:
- active organizations readable under `organization.read`, plus
- active/inactive organizations manageable under canonical
  `organization.manage` scope, including the existing inactive-target recovery
  rule.

The normal `GET /api/v1/organizations` behavior is unchanged.

## Structural mutations intentionally excluded

B6.5 does not allow changing `parent_id` or `organization_type` after creation.
Moving an organization changes authorization reachability and remains a separate
future security-sensitive operation rather than a generic edit field.

## BFF routes

- GET/POST `/api/core/organizations`
- PATCH `/api/core/organizations/{organizationId}`
- PATCH `/api/core/organizations/{organizationId}/status`

All unsafe BFF methods reuse the centralized B6.2 CSRF/origin guard through
`proxyAuthenticatedRequest()`.
