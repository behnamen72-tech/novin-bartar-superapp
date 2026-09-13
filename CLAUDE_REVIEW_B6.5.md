# Claude Review Request — B6.4 + B6.5 checkpoint

B6.1-B6.3 were approved. Please review the cumulative delta from that approved
checkpoint through B6.4 Operational Dashboard and B6.5 Organization Management.

## Highest-priority review areas

### 1. Organization management authorization
Inspect:
- `backend/app/api/v1/routes/organizations.py`
- `backend/app/core/access/service.py`
- `backend/app/core/organization/service.py`
- `frontend/lib/organization-management.ts`
- `frontend/components/core/OrganizationManagementView.tsx`

Confirm that `include_inactive=true` does not create a new access path. Inactive
organizations must only be visible when the actor is authorized through the
existing `has_permission_including_inactive_target()` B3 rule.

### 2. Root Holding lockout guard
B6.5 adds a server-side prohibition on changing the root Holding's active status.
Please confirm this closes the case where a root organization could otherwise be
deactivated and become impossible to reactivate because its own assignments stop
being effective.

### 3. Create/edit/status BFF mutations
Confirm all new frontend mutation routes use `proxyAuthenticatedRequest()` and
therefore inherit the central CSRF/origin check and HttpOnly session boundary.

### 4. Frontend permission logic is UX-only
`organization-management.ts` calculates which controls to display, but backend
service authorization must remain authoritative. Confirm no client assertion is
trusted by FastAPI.

### 5. B6.4 dashboard regression
Please also review the live dashboard introduced after the approved B6.3 baseline:
- permission-gated data fetches
- partial-failure behavior
- document-expiration attention list
- Audit and Role/Scope summaries

## Intentional constraints

- no API creation of root Holdings
- no generic parent/type changes after Organization creation
- no frontend token access
- no weakening of B3 scope semantics
- no new database migration in B6.5

## Verification supplied

See `B6.5_TEST_RESULTS.md` for exact commands/results. The cumulative backend suite
passes, and the final package is re-extracted and rerun before delivery.
