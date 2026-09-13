# Demo UI 0.1

Status: Ready for practical preview

## Goal
Provide the first clickable visual version of the Super App before continuing to B4 Audit.

## Connected to real backend
The UI uses the existing:
- POST `/api/v1/auth/token`
- GET `/api/v1/auth/me`
- GET `/api/v1/access/me`

## Security
The browser UI does not store the JWT in localStorage.
Next.js acts as a small BFF (Backend-for-Frontend):
- Login is sent to a Next.js route.
- The backend JWT is stored in an HttpOnly cookie.
- Browser JavaScript cannot read the JWT.
- `/me` and `/access/me` are proxied server-side.

This is a demo UI, not a final production security review.

## Visible screens
- Login
- Management dashboard
- Current user
- Active role count
- Organization scopes
- Effective permissions
- Business module placeholders
- Logout

## Demo seed
Development-only:
`python scripts/seed_demo.py`

Default local demo login:
- Email: `demo@novinbartar.local`
- Password: `Demo-Only-ChangeMe-123!`

The seed script refuses to run unless `APP_ENV=development`.
The demo password may be overridden with `DEMO_USER_PASSWORD`.

## Not implemented yet
- Actual HR CRUD
- Customer CRUD
- Supplier CRUD
- Contracts
- Tasks
- Operations
- Audit (B4)
