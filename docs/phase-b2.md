# Phase B2 — Authentication

Status: Ready for Claude Review

## Scope
Authentication only:
- password hashing
- login
- JWT access tokens
- current-user identity

Roles and Permissions are intentionally deferred to B3.

## Security decisions

### Passwords
- Plaintext passwords are never stored.
- Passwords are hashed with Argon2id through `argon2-cffi`.
- Successful login checks whether the stored hash needs rehashing and upgrades it automatically.
- Unknown-user login attempts perform a dummy hash verification to reduce basic timing-based user enumeration.

### JWT
- Signed access tokens use HS256.
- Secret key is REQUIRED from environment configuration and has no source-code default.
- The placeholder value from `.env.example` is explicitly rejected by configuration validation.
- Token contains:
  - `sub` = User UUID
  - `type` = access
  - `iat`
  - `exp`
  - `iss`
  - `aud`
- Decode requires all of those claims.
- Default access-token lifetime: 15 minutes.
- Password data is never included in the token.

### Login behavior
- Login identifier can be email or username.
- Email and username are normalized to lowercase.
- Inactive User or inactive linked Person cannot authenticate.
- Login failures use HTTP 401.

### API
- `POST /api/v1/auth/token`
- `GET /api/v1/auth/me`

### Registration
There is intentionally no public registration endpoint.
An internal CLI script creates the initial login user:
`python scripts/create_initial_user.py`

### Not included yet
- Roles
- Permissions
- Organization scope authorization
- Refresh tokens
- Token revocation list
- Password reset
- MFA
- Public signup
