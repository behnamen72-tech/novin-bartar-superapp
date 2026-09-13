# Demo UI 0.2 — Real Core Pages

Status: Ready for practical preview / Claude review

## New clickable Core sections
- Organizations
- People
- Users
- Access

## Security boundary
This release is read-only.

No create/update/delete endpoint was added.

Each Core list is filtered by the existing server-side authorization model:
- organization.read
- people.read
- users.read
- access.read
- Organization Scope

The UI does not decide what data is allowed.
The Backend performs the filtering.

## API
- GET /api/v1/organizations
- GET /api/v1/people
- GET /api/v1/users
- GET /api/v1/access/overview

## Demo seed
`seed_demo.py` now adds extra fictional demo people and a read-only demo user
so the pages contain meaningful sample data.

Existing databases do not require a migration for 0.2.
Re-run:
`python scripts/seed_demo.py`

## Next
After 0.2 is visually approved:
- B4 Audit
- then controlled create/edit flows with Audit + Permission enforcement
