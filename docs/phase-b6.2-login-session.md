# Phase B6.2 — Login & Session

B6.2 turns the B6.1 login preview into a persistent, production-oriented session flow without weakening the B2 short-lived access-token policy.

## Delivered

### Backend authentication lifecycle

- Access JWT lifetime remains short (15 minutes by default).
- Successful password login now also creates an opaque refresh credential.
- Refresh credentials are generated from cryptographically secure random bytes.
- Only SHA-256 hashes of refresh credentials are stored in PostgreSQL; plaintext refresh tokens are never persisted.
- Refresh tokens rotate on every successful refresh. Reusing the previous token is rejected.
- Refresh sessions have an absolute lifetime (`AUTH_REFRESH_TOKEN_EXPIRE_DAYS`, 7 days by default). Rotation does not extend that absolute deadline.
- Logout revokes the refresh session and is idempotent.
- Disabled User or Person records cannot refresh a session.
- New access JWTs include a unique `jti` claim while remaining backward-compatible with existing token validation.
- Login, refresh, and logout produce immutable B4 Audit events. These authentication events are global (`organization_id = null`) and therefore are not exposed by the current organization-scoped Audit UI.

New API endpoints:

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

`POST /api/v1/auth/token` remains compatible with the existing OAuth2 password-form request and now returns additive session-lifetime/refresh fields.

Migration `20260910_0012` creates `user_sessions`.

### Next.js BFF session boundary

The browser never receives the backend tokens in JavaScript-visible storage.

- Access token: HttpOnly cookie, path `/`, short lifetime matching the backend response.
- Refresh token: separate HttpOnly cookie, path `/api/session`, so it is not sent with ordinary `/api/core/*` requests.
- Both cookies use `SameSite=Lax`; `Secure` is enabled in production.
- Login and refresh BFF responses expose only `{ "ok": true }`, never token values.
- Logout removes both browser cookies even when the backend is temporarily unreachable.
- A new `/api/session/state` BFF route loads identity + effective access in one browser request.
- A new `/api/session/refresh` BFF route performs refresh-token rotation server-side.

### Automatic session recovery

The shared browser API client now performs a single-flight silent refresh after a backend `401`, then retries the original BFF operation once.

This matters for B6.4+ write screens: an access JWT can expire while a user is filling a form without forcing the form to be discarded. The refresh credential remains inaccessible to client JavaScript.

If the refresh credential is invalid/expired, the UI transitions to the signed-out state. A temporary refresh-service outage is distinguished from an expired session and does not delete the refresh cookie.

### CSRF hardening

All unsafe requests routed through the generalized authenticated BFF proxy now pass a same-origin mutation check. Login, refresh, and logout use the same protection. Cross-site requests are rejected before credentials or request bodies are forwarded to FastAPI.

Backend bearer-token authorization remains authoritative. Frontend CSRF checks are an additional browser/BFF boundary, not a replacement for B3 authorization.

### Login UX

- Demo credentials are no longer prefilled in the application form.
- Password is cleared from component state immediately after successful login and on logout.
- Browser password-manager attributes remain enabled (`username`, `current-password`).
- Initial session loading distinguishes a first-time signed-out user from an expired session.
- Returning to a visible tab revalidates identity/access state.

## Security properties preserved

- No access or refresh token in `localStorage` / `sessionStorage`.
- No refresh-token plaintext in the database.
- No role/permission claims embedded in JWTs; B3 authorization still reads current DB state.
- User/Person deactivation takes effect on access-token validation and on refresh.
- Refresh rotation is performed under a row lock before commit.
- Authentication audit records and session state changes are committed transactionally.

## Deferred

- Failed-login throttling/account lockout remains in Technical Debt and must be combined with edge rate limiting before public/high-risk production exposure.
- Administrative UI/API for listing and revoking all active sessions/devices is deferred until the account/security settings surface.
- Expired/revoked session-row cleanup is operational maintenance to add before long-running production scale.
- Full refresh-token family/reuse-compromise detection can be added if threat modeling later requires revoking an entire session family after replay.

## Environment

Backend `.env`:

```env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=7
```

No refresh-token secret is configured because refresh tokens are opaque random credentials and only their hashes are stored.
