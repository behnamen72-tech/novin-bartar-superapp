# Novin Bartar Super App

Central non-accounting management and operations platform for Novin Bartar / Enferadi Market.

## Architecture
- Modular Monolith
- Backend: Python + FastAPI
- Frontend: Next.js + React + TypeScript
- Database: PostgreSQL
- ORM: SQLAlchemy 2
- Database migrations: Alembic
- API: REST under `/api/v1`

## Current implementation
- Phase A1: approved
- Phase B1: approved
- Phase B2: approved
- Phase B3: approved
- Phase B4: approved
- Phase B5.1: approved
- Phase B5.2: approved
- Phase B5.3: approved
- Phase B5.4: approved
- Phase B5.5: approved
- Phase B5.6: approved
- Phase B6.1: approved checkpoint
- Phase B6.2: approved checkpoint
- Phase B6.3: approved checkpoint
- Phase B6.4: approved
- Phase B6.5: approved
- Phase B6.6: approved
- Phase B6.7: approved
- Phase B6.8: approved
- Phase C1 Workflow Core + UI: approved
- Phase C2 Notifications Core + UI: approved
- Phase C3 Search Core + UI: approved
- Phase C: CLOSED
- Phase D1 HR Foundation + UI: approved
- Virtual Store ↔ Super App Integration Contract v1.1: **FROZEN architecture baseline** (`903a5c649bf8d3e5f16998405fcb687d8bf07a427f793c35fc9a8b74e608f59f`)
- Phase D2 Customer Reference / CRM Foundation + UI: architecture reviewed; **implementation primary artifact directly reviewed and approved by Claude**
- Phase D3 Suppliers Foundation + UI: architecture/implementation reviewed; real CI gate and closure evidence pending

## Artifact-based governance

Phase status is governed by `docs/PROJECT_GOVERNANCE.md`. A phase is not `CLOSED` from a summary alone: primary artifact/version, primary independent review, and relevant executable evidence must be recorded in its closure record.

Current D3 closure record: `docs/closure/D3_CLOSURE_RECORD.md`.

Operational pilot procedure: `docs/PILOT_RUNBOOK.md`.

Shared cross-track artifact ownership: `docs/SHARED_ARTIFACT_GOVERNANCE.md`.

Canonical shared-artifact registry: `docs/SHARED_ARTIFACT_REGISTRY.md`.

Integration Contract freeze record: `docs/closure/INTEGRATION_CONTRACT_V1_1_FREEZE_RECORD.md`.

## Backend setup
```bash
cd backend
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

Before starting the backend, replace `JWT_SECRET_KEY` in `.env` with a random secret.

## Database migration
```bash
cd backend
alembic upgrade head
```

## Create the initial login user
```bash
cd backend
python scripts/create_initial_user.py
```

There is no public signup endpoint.

## Quality checks
```bash
cd backend
ruff check .
mypy app
pytest
```

## Current API
- `GET /api/v1/health`
- `POST /api/v1/auth/token`
- `GET /api/v1/auth/me`

Authorization is modeled as Role + Permission + Organization Scope. B5.6 exposes the approved Core access-management write APIs, and B6.8 now exposes those operations through the authenticated UI/BFF while FastAPI remains authoritative.

## Bootstrap first administrator access
```bash
cd backend
python scripts/bootstrap_access.py
```


## Demo UI 0.1 — first practical preview

After PostgreSQL is running and `.env` is configured:

### 1. Backend
```bash
cd backend
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload
```

### 2. Frontend
In a second terminal:
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open:
`http://localhost:3000`

Development-only demo login:
- Email: `demo@novinbartar.local`
- Password: `Demo-Only-ChangeMe-123!`

The frontend keeps the backend JWT in an HttpOnly cookie through Next.js route handlers instead of localStorage.


## Demo UI 0.2

Core navigation is now functional:
- سازمان‌ها
- اشخاص
- کاربران
- دسترسی‌ها

No database migration is required from Demo 0.1.1 to 0.2.

After updating files, rerun demo seed:
```bash
cd backend
python scripts/seed_demo.py
```

Then restart Backend and Frontend.


## Phase B4 — Audit

After updating from Demo UI 0.2:

```bash
cd backend
alembic upgrade head
python scripts/seed_demo.py
```

Then restart Backend and Frontend.

New admin UI:
- تاریخچه

New API:
- GET `/api/v1/audit`

Audit events are immutable and organization-scoped.


## Phase B5.2 — Documents API

After applying B5.1/B5.2:

```bash
cd backend
alembic upgrade head
```

Current document endpoints:
- GET `/api/v1/documents`
- POST `/api/v1/documents`
- GET `/api/v1/documents/{id}`
- POST `/api/v1/documents/{id}/versions`
- GET `/api/v1/documents/{id}/download`

Local development storage defaults to `backend/storage/documents` relative to the backend working directory.


## Phase B5.4 — Document-Level Access Control

B5.4 adds optional restrictive role-based ACLs per document. Documents without
ACL rows continue to inherit organization-level access. Restricted documents
require both normal B3 organization permission and a matching document role ACL.

New endpoints:
- GET `/api/v1/documents/{id}/permissions`
- POST `/api/v1/documents/{id}/permissions`
- DELETE `/api/v1/documents/{id}/permissions/{permission_id}`

Run:
```bash
cd backend
alembic upgrade head
pytest
```

## Phase B5.5
Document Operations is implemented and ready for Claude review. It adds document metadata, organization-scoped categories, expiration queries, retention policies/deadlines, Audit-backed timeline, and bounded metadata search filters.

## Phase B5.6 — Core Write APIs
B5.6 makes Organization, People, User, and Access administration operational for
B6. It reuses B3 permissions/organization scope, B4 Audit, adds organization-owned
custom roles via migration 0011, and enforces capability-based privilege delegation.
See `docs/phase-b5.6-core-write-apis.md`.


## Phase B6.1 — Frontend Foundation

B6.1 begins the operational UI phase on top of the approved B5.6 Core. It adds a typed browser API client, a generalized authenticated Next.js BFF proxy for future writes, configurable backend request timeouts, shared Core frontend types/permission helpers, permission-aware navigation, reusable error/loading states, and baseline frontend security headers.

Frontend setup remains:
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Recommended frontend checks:
```bash
npm run typecheck
npm run lint
npm run build
```

See `docs/phase-b6.1-frontend-foundation.md`.


## Phase B6.2 — Login & Session

B6.2 keeps short-lived access JWTs while adding persistent server-managed sessions
with rotating opaque refresh tokens. Refresh tokens are stored only as SHA-256 hashes
in the database and remain in HttpOnly cookies at the Next.js BFF boundary.

After updating from B6.1:
```bash
cd backend
alembic upgrade head
pytest
```

New optional backend environment setting:
```env
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=7
```

Frontend startup is unchanged:
```bash
cd frontend
npm install
npm run dev
```

See `docs/phase-b6.2-login-session.md`.

## Phase B6.3 — Main Layout & Navigation

B6.3 introduces the reusable authenticated application shell used by the remaining B6 operational screens. Navigation is centrally permission-aware for UX, while backend B3 authorization remains authoritative.

Delivered:
- responsive desktop sidebar + mobile drawer
- centralized navigation definitions and permission gates
- browser Back/Forward + `?view=` deep-link state
- reusable Login, AppShell, Dashboard, and Core-view components
- active-session/user/scope context in the workspace header
- accessibility basics including skip link and `aria-current`

Optional navigation verification after frontend dependencies are installed:
```bash
cd frontend
npm run check:b63
```

See `docs/phase-b6.3-main-layout-navigation.md`.

## Phase B6.4 — Operational Dashboard

B6.4 replaces the static dashboard preview with a live permission-aware Core overview.
It loads only datasets for which the session advertises the matching backend read
permission, while FastAPI remains authoritative for Organization Scope and document ACLs.

Delivered:
- live Organization / People / User summary metrics
- document expiration attention list
- recent immutable Audit activity
- active Role/Scope summary
- permission-aware quick navigation
- manual refresh with partial-failure handling
- authenticated BFF document read proxies

Optional deterministic dashboard check:
```bash
cd frontend
npm run check:b64
```

See `docs/phase-b6.4-operational-dashboard.md`.


## Phase B6.5 — Organization Management

B6.5 makes Organization Core operational in the UI: authorized users can create
hierarchy-valid descendants, edit name/code, and activate/deactivate non-root
organizations. Inactive descendants remain recoverable in the management view
without weakening B3 authorization.

Delivered safeguards include:
- write operations only through the authenticated/CSRF-protected BFF
- scope-aware frontend affordances with backend authorization still authoritative
- root Holding status locked to bootstrap administration
- active-child and inactive-parent UX guards matching backend invariants
- parent/type structural moves intentionally excluded

Deterministic check:
```bash
cd frontend
npm run check:b65
```

See `docs/phase-b6.5-organization-management.md`.

## Phase B6.6 — People & User Management

B6.6 replaces the read-only People and Users views with operational management
screens using the B5.6 write APIs. It includes Person lifecycle and organization
relationships, User create/edit/status, administrator password reset, and an
additional self-lockout guard preventing an administrator from deactivating their
own Person record. See `docs/phase-b6.6-people-user-management.md`.

## Phase B6.7 — Operational Documents UI

The B5 Documents platform is now available through the operational UI: document
search/filtering, create/edit, archive/restore, version upload/download, links,
timeline, categories, retention policies, and restrictive document ACL management.
See `docs/phase-b6.7-documents-ui.md`.

## Phase B6.8 — Access / Roles / Permissions UI

Access Administration is now operational for custom roles, permission membership,
organization-scoped role assignments, and assignment/role lifecycle. B6.8 also
exposes the B5.4 restrictive document ACL plus an `access.manage` break-glass ACL
recovery tool that does not grant or reveal document content. See
`docs/phase-b6.8-access-management-ui.md`.


## Phase C1 — Workflow Core
C1 adds a reusable organization-scoped workflow engine and an operational UI for designing and running workflows. Definitions are versioned, published definitions are immutable, instances are pinned to a definition version, transitions are row-locked, transition history is immutable, and all meaningful writes are audited.

New permissions:
- `workflow.read`
- `workflow.manage`
- `workflow.execute`

New UI:
- گردش‌کار → طراحی گردش‌کار
- گردش‌کار → اجرا و پیگیری

See `docs/phase-c1-workflow-core.md`.


## Phase C2 — Notifications Core
C2 adds recipient-owned in-app notifications with immutable content, mutable read state, no physical delete, app-local actions, per-recipient unread counts, internal transactional producers, and no public arbitrary-send endpoint. Workflow now demonstrates atomic notification production when another actor transitions or cancels an instance.

New UI:
- اعلان‌ها
- topbar unread badge
- read/unread and read-all controls

Migration: `20260911_0014_notifications_core.py`

See `docs/phase-c2-notifications-core.md`.


## Phase C3 — Search Core
C3 adds a permission-aware federated Search foundation across Organizations, People, and Documents. Search derives visibility from each domain's existing read permission and preserves B5.4 restrictive Document ACLs; it does not introduce a standalone `search.read` privilege.

New UI:
- جستجوی سراسری
- topbar Search shortcut
- per-domain filters and authorized result counts

No database migration is required.

See `docs/phase-c3-search-core.md`.

## Phase D1 — HR Foundation
D1 begins Business Foundations without assuming that any proposed future business already exists. It adds reusable business Job Profiles, vacant/planned organization Positions, and Employment history on the approved Organization + Person Core.

Canonical permissions: `hr.read`, `hr.manage`. Business Job Profiles are intentionally separate from Access Roles and grant no software permission. Shared descendant-scoped profile mutations require control of every actually impacted organization. Employment requires an applicable Person↔Organization relationship, preserves history without hard delete, and enforces one active employment per Person/organization and one active occupant per position.

The operational Persian RTL UI is available under the HR foundation navigation item. See `docs/phase-d1-hr-foundation.md`.


## Continuous Integration

Repository CI is defined in `.github/workflows/ci.yml`. See `docs/CI_POLICY.md` for the merge/phase-closure policy.

The frontend requires a committed `frontend/package-lock.json`. If it is not present yet, run the manual GitHub Actions workflow `.github/workflows/bootstrap-frontend-lockfile.yml`, download the generated artifact, commit the lockfile, and re-run CI.
