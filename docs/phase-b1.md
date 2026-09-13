# Phase B1 — Organization, People, User Foundation — Revision 3

Status: Ready for Claude Review

## Purpose
Persistence foundation for:
- Organization hierarchy
- People
- Person ↔ Organization business relationships
- System users

No management CRUD endpoints are exposed yet.

## Revision 3 fix

### Real application listener wiring
The Organization hierarchy `before_flush` listener is no longer dependent on
tests or Alembic importing `app.db.models`.

`app.db.session` imports the central model registry, which registers ORM events.
The real FastAPI entry point (`app.main`) imports the DB session layer during
startup.

Therefore these paths all initialize the hierarchy rule:
- real FastAPI application startup
- production code importing `get_db` / DB session layer
- tests
- Alembic

A dedicated isolated-process test verifies that importing `app.main` alone
registers the SQLAlchemy listener.

## CORS
Standard format remains comma-separated:
`CORS_ALLOWED_ORIGINS=http://localhost:3000,https://admin.example.com`

## Security decision
Organization/People/User CRUD APIs remain unexposed until Authentication and
Authorization are implemented.
