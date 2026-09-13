# Claude Review Request — B6.2 Login & Session

Please review the actual code in this package. B6.2 is built directly on the B6.1 package and changes the authentication/session lifecycle plus its Next.js BFF integration.

## What changed

### Backend

Files of primary interest:

- `backend/app/core/identity/models.py`
- `backend/app/core/identity/session_service.py`
- `backend/app/core/identity/schemas.py`
- `backend/app/core/identity/security.py`
- `backend/app/core/identity/service.py`
- `backend/app/api/v1/routes/auth.py`
- `backend/app/core/config.py`
- `backend/app/db/models.py`
- `backend/alembic/versions/20260910_0012_user_sessions.py`
- `backend/tests/test_auth_session_api.py`
- `backend/tests/test_auth_security.py`

### Frontend / BFF

Files of primary interest:

- `frontend/lib/session.ts`
- `frontend/lib/request-security.ts`
- `frontend/lib/api-client.ts`
- `frontend/lib/authenticated-backend.ts`
- `frontend/app/api/session/login/route.ts`
- `frontend/app/api/session/refresh/route.ts`
- `frontend/app/api/session/logout/route.ts`
- `frontend/app/api/session/state/route.ts`
- `frontend/app/page.tsx`

## Backend session design

### Access token

- Existing HS256 JWT design remains.
- Default access lifetime remains 15 minutes.
- Current DB User/Person active-state checks remain on every protected backend request through `get_current_user`.
- Roles/permissions are still **not** placed in JWTs.
- New access tokens include a random `jti` so repeated issuance in the same second does not create identical JWTs.

### Refresh token

Refresh token is intentionally opaque rather than another JWT:

1. Generate 48 random bytes via `secrets.token_urlsafe(48)`.
2. Return plaintext only to the immediate API caller (the Next.js server for the browser flow).
3. Persist only `SHA-256(refresh_token)` in `user_sessions`.
4. On refresh, select by hash under `SELECT ... FOR UPDATE`.
5. Reject missing/revoked/expired sessions and inactive User/Person.
6. Generate a new opaque token and replace the stored hash before commit.
7. Old token is therefore unusable after a successful rotation.

Refresh lifetime is an **absolute** session lifetime (7 days default). Rotation does not extend `expires_at`; the response reports remaining refresh lifetime so the BFF cookie follows the same deadline.

### Logout

`POST /api/v1/auth/logout` revokes the refresh session and returns 204. Repeated logout is intentionally idempotent and does not reveal whether a session record exists.

### Authentication-route authorization note

`/auth/refresh` and `/auth/logout` do not use `get_current_user` by design: the access JWT may already be expired, and the refresh credential is the authenticator for these two session-lifecycle operations. They cannot perform Core business writes. All existing protected Core routes continue to use `get_current_user` and B3/B5.6 service-layer authorization.

## Audit / transaction behavior

- Successful password login: `auth.login.succeeded`
- Successful rotation: `auth.session.refreshed`
- First successful logout/revocation: `auth.logout`

Authentication state change + Audit are committed in the same SQLAlchemy transaction.

Events use `organization_id = null`, so they are retained by B4 immutable Audit but are intentionally not exposed by the current organization-scoped Audit listing.

No password or refresh-token value is included in Audit payloads.

## Next.js BFF design

### Cookies

Access token:

- HttpOnly
- `SameSite=Lax`
- `Secure` in production
- path `/`
- max-age from backend `expires_in`

Refresh token:

- HttpOnly
- `SameSite=Lax`
- `Secure` in production
- path `/api/session`
- max-age from backend remaining absolute refresh lifetime

The path restriction means refresh credentials are not sent with ordinary `/api/core/*` browser requests.

Tokens are never returned from BFF login/refresh responses to browser JavaScript. Browser receives `{ok:true}` only.

### Silent refresh

`apiFetch()` handles a `401` with a module-level single-flight refresh request, then retries the original BFF request once. Single-flight avoids concurrent browser requests racing rotation of the same refresh token.

- refresh 200 -> retry original request
- refresh 401 -> emit session-expired event and sign out UI
- refresh service/network 5xx -> report temporary unavailability without deleting refresh cookie

Initial `/api/session/state` distinguishes "no session at all" from an expired access token, avoiding an incorrect "session expired" message on a first visit.

### CSRF boundary

Unsafe BFF mutations require same-origin evidence using `Sec-Fetch-Site` and/or exact `Origin` matching. This is applied to:

- login
- refresh
- logout
- generalized authenticated BFF write proxy for B6.4+ writes

Backend bearer authorization remains authoritative; this is BFF/browser defense-in-depth.

## Login UX changes

- removed prefilled demo email/password from component state
- password cleared after login/logout
- required/max length constraints added
- session snapshot loads identity + effective access in one browser call
- returning to a visible tab revalidates current identity/access

## Migration 0012

Creates `user_sessions`:

- UUID PK
- `user_id` -> users.id, `ON DELETE RESTRICT`
- unique indexed SHA-256 refresh token hash
- `expires_at`
- `last_used_at`
- `revoked_at`
- timestamps

## Tests performed

See `B6.2_TEST_RESULTS.md`.

Current backend result: **99 passed**.

Also passed:

- Python compileall
- PostgreSQL Alembic offline SQL through 0012
- OpenAPI generation (48 paths)
- TypeScript parser: 28 TS/TSX files, 0 syntax diagnostics
- static session-security invariants

npm dependencies could not be installed in the execution environment, so no claim is made for Next.js typecheck/lint/build. Please treat that as an environment limitation, not a passed check.

## Specific review questions

Please focus on blockers, especially:

1. Any flaw in opaque refresh-token storage/rotation/absolute expiry semantics?
2. Any replay/TOCTOU issue around `SELECT ... FOR UPDATE` and hash replacement?
3. Any cookie path/lifetime/security concern at the BFF boundary?
4. Any CSRF bypass or legitimate same-origin browser flow likely to be rejected?
5. Any unsafe behavior in single-flight refresh + one retry, especially upcoming write requests?
6. Any transaction/Audit inconsistency introduced by moving `authenticate_user` commit responsibility into the route?
7. Any migration/model mismatch or regression against B1-B5.6 authorization?

Nonblocking future work is already documented for session cleanup, account-session management UI, failed-login throttling, and optional refresh-token-family replay detection.
