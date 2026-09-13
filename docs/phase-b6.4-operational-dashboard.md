# Phase B6.4 — Operational Dashboard

B6.4 replaces the static dashboard preview with a live, permission-aware Core overview. It is intentionally a frontend/BFF phase: no backend authorization model, database model, migration, or business-domain module is changed.

## Delivered

### Live Core overview

The authenticated dashboard now loads real data from the existing protected Core APIs and summarizes only datasets the current session is allowed to read.

Current dashboard sources:

- Organizations via `GET /api/v1/organizations`
- People via `GET /api/v1/people`
- Users via `GET /api/v1/users`
- Document expiration attention via `GET /api/v1/documents/expiring`
- Recent immutable Audit events via `GET /api/v1/audit`
- Access scope/role summary from the already authenticated session snapshot

The browser never talks to FastAPI directly. New document read proxies remain behind the existing Next.js authenticated BFF boundary.

### Permission-aware data fetching

`lib/dashboard.ts` derives dashboard read capabilities from the exact read permissions used by the backend endpoints:

- `organization.read`
- `people.read`
- `users.read`
- `documents.read`
- `audit.read`

This is an optimization and UX decision only. It prevents unnecessary requests that are expected to fail. It is not an authorization boundary; every BFF request still carries the server-held access token to FastAPI, where B3/B5 authorization remains authoritative.

A client that tampers with the dashboard cannot gain data outside its backend Organization Scope.

### Operational widgets

The dashboard now provides:

- visible organization count
- people count and active-person count
- user count and active-account count
- documents expiring within 30 days plus already-expired documents
- active assignment/role summary
- quick navigation to currently visible Core workspaces
- current authorization scopes
- recent Audit activity
- manual refresh and last-refresh time

Document attention is intentionally bounded at 200 rows. When the response reaches the dashboard cap, the UI displays the count with a `+` marker and explicitly states that the result is a lower bound rather than pretending it is an exact total.

### Partial failure behavior

Dashboard requests are independent. One failed dataset does not blank the rest of the workspace.

- successful sections remain usable
- failed sections are identified in a non-destructive error notice
- metrics for a failed dataset show an unavailable marker instead of a false zero
- 401 handling remains delegated to the B6.2 `apiFetch()` refresh/session-expiry flow

### Shared Core labels

Audit action/resource labels and document-expiration labels are centralized in `lib/core-labels.ts`. The full Audit screen and Dashboard use the same action labels rather than maintaining diverging feature-local mappings.

### New BFF read routes

B6.4 adds:

- `GET /api/core/documents`
- `GET /api/core/documents/expiring`

Both use `proxyAuthenticatedGet()` and therefore require the existing server-side session cookie/access-token flow. The FastAPI Documents service still performs authoritative organization and document-ACL filtering.

## Security properties preserved

- access and refresh tokens remain HttpOnly
- no token is exposed to dashboard JavaScript
- no organization/user/document identifiers are trusted as authorization evidence
- frontend permission checks only suppress unnecessary requests/controls
- FastAPI remains the source of truth for B3 permissions, Organization Scope, and B5 document ACLs
- document ACLs remain restrictive and cannot expand organization-level access
- Audit remains immutable
- no new write endpoint is introduced by B6.4

## Scalability note

Organizations, People, and Users counts currently derive from their existing list APIs. This is correct for the current scale and preserves one source of authorization semantics, but a future high-volume deployment should use a dedicated permission-aware aggregate endpoint rather than transferring full visible lists only to calculate dashboard totals. This is tracked in `docs/technical-debt.md`.

## Verification

See `B6.4_TEST_RESULTS.md`.

## Next

B6.5 can turn the Organization screen into the first write-capable management workspace using the already-approved B5.6 Organization Write APIs and the B6.1/B6.2 authenticated BFF write path.
