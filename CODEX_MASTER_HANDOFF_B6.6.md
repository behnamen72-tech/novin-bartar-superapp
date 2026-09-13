# Novin Bartar Super App — Master Handoff for Codex

**Project:** سوپر اپ انفرادی مارکت / Novin Bartar Super App  
**Authoritative coding baseline:** B6.6 People & User Management package  
**Handoff date:** 2026-09-10  
**Baseline package SHA-256:** `ce64e959e98bef70beced2e7cc235a9dd9450280acb240771dd49c0ebc9b8e51`  
**Purpose:** Give Codex enough architectural, security, implementation, review, and workflow context to continue the project without redesigning approved foundations or drifting from scope.

---

## 1) Read this first

Do **not** rebuild or redesign the application from scratch. Continue from the supplied B6.6 source tree.

Before changing code:

1. Read `AGENTS.md`.
2. Read this file completely.
3. Read `docs/architecture.md` and `docs/technical-debt.md`.
4. Read the phase document for the area you are modifying.
5. Inspect the existing service/API/BFF patterns and extend them rather than inventing a parallel architecture.
6. Treat already-approved security invariants as regression constraints.

Current immediate direction: **B6.7 — Documents UI**, followed by **B6.8 — Access / Roles & Permissions UI**. B6.6 is now independently approved by Claude. A non-blocking review recommendation was applied before handoff: `UserPasswordResetRequest.new_password` uses Pydantic `SecretStr` and is unwrapped only at the password hashing boundary.

---

## 2) Product goal

Build a central management and operations super-app for **Novin Bartar / Enferadi Market**, designed to grow into a holding-wide platform.

The current product is a modular management platform. Future modules may include CRM, HR, suppliers, contracts, tasks, operations, e-commerce, accounting, inventory, reporting, and integrations. Do not pull future business-domain complexity into Core prematurely.

The owner is non-technical. Deliver changes in runnable increments, keep setup simple, and provide exact verification results. Never claim a test/build passed unless it actually ran successfully.

---

## 3) Fixed architecture — do not casually change

- **Architecture:** Modular Monolith
- **Backend:** Python + FastAPI
- **Frontend:** Next.js + React + TypeScript
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2
- **Migrations:** Alembic
- **API style:** REST under `/api/v1`
- **Frontend-to-backend boundary:** same-origin Next.js BFF routes
- **Files:** storage separate from the database through `StorageProvider`
- **Authorization:** backend-authoritative Role + Permission + Organization Scope
- **Audit:** immutable, organization-scoped, and transactionally coupled to writes

Do not introduce microservices, CQRS, an event bus, a second authorization engine, or direct cross-module database access in the current phase.

---

## 4) Core domain invariants

### Organization

Hierarchy is:

`HOLDING -> COMPANY -> BRANCH / UNIT`

Valid parent rules:

- Holding: no parent
- Company: parent Holding
- Branch: parent Company
- Unit: parent Company or Branch

Important security rule: creating/changing the root Holding through ordinary APIs is not a normal user operation. Root/bootstrap operations remain bootstrap-only. Generic update flows must not silently permit organization type or parent moves because hierarchy changes alter authorization reachability.

### Person vs User

`Person` and `User` are separate concepts with a one-to-one link when a Person has a system account.

A Person may have flexible organization relationships; do not model mutually exclusive “employee/customer/supplier person types” into the identity Core.

Shared Person fields are global. A write that affects a Person connected to multiple organizations must preserve the backend's multi-organization authorization rules.

### User access

There is no free-floating global role assignment. `UserRoleAssignment` is organization-scoped and has scope mode:

- `SELF`
- `SELF_AND_DESCENDANTS`

Do not invent a separate “User organization membership” model unless a future approved design explicitly requires one.

---

## 5) Canonical permissions

Use the existing B3 permission codes. Do **not** invent granular aliases such as `user.create`, `organization.update`, or `permission.manage` without an explicit architecture decision, migration, compatibility plan, and review.

Canonical Core permissions:

- `organization.read`
- `organization.manage`
- `people.read`
- `people.manage`
- `users.read`
- `users.manage`
- `access.read`
- `access.manage`
- `audit.read`
- `documents.read`
- `documents.manage`

All real enforcement stays in FastAPI services. Frontend capability checks are only UX affordances and must never expand authority.

---

## 6) Authorization and anti-escalation rules

- Deny by default.
- Authentication is required on protected routes.
- Permission + organization scope are evaluated server-side from current database state.
- Do not encode roles/permissions into JWT as the source of authority.
- Cross-organization access must fail closed.
- Use generic 404 where existing code intentionally hides a resource's existence (notably restricted documents).
- `access.manage` is not equivalent to content access.
- System/bootstrap roles are immutable through normal APIs.
- Runtime custom roles are organization-owned.
- Role assignment / permission mutation must preserve backend dominance and capability-based anti-privilege-escalation rules already implemented in `backend/app/core/access/service.py`.
- Never replace those checks with frontend logic.

When touching access code, review the impact of a role mutation on every active assignment that uses that role. Avoid any change that lets a manager grant authority they do not effectively possess.

---

## 7) Authentication/session security invariants

B6.2 introduced persistent rotating sessions without exposing refresh credentials to browser JavaScript.

Keep these invariants:

- Short-lived access JWT remains.
- Refresh token is opaque and randomly generated.
- Only the refresh-token **SHA-256 hash** is stored server-side.
- Successful refresh rotates the token under a row lock.
- Rotation does not extend the absolute session lifetime.
- Refresh cookie is HttpOnly and restricted to the `/api/session` path.
- Browser app must not use `localStorage` for backend tokens.
- Unsafe authenticated BFF requests must pass through the centralized CSRF/origin protection in `frontend/lib/authenticated-backend.ts` / request-security helpers.
- Logout revokes the server-side session.

Claude approved B6.1-B6.3 and specifically validated these session/CSRF properties. A future enhancement for refresh-token reuse family detection is technical debt, not a blocker for current B6 work.

---

## 8) Audit invariants

Every meaningful Core write must record an Audit event in the **same SQLAlchemy transaction** as the state change.

Audit records capture actor, action, organization, resource, timestamps, and appropriate before/after/metadata. They must never record passwords, tokens, secrets, or raw credential material.

Audit records are immutable through both application and database protections. Do not add update/delete flows for Audit events.

---

## 9) Documents platform invariants — critical for B6.7

The Documents backend from B5.1-B5.5 is already approved. B6.7 should primarily expose it safely in the UI/BFF, not redesign it.

### Data/lifecycle

- `Document`, `DocumentVersion`, `DocumentLink`, `DocumentPermission`, retention models are deletion-restrictive.
- Versions are append-only/immutable.
- Links are logically deactivated, not physically deleted.
- Documents are archived/restored; there is no ordinary physical delete.
- Archived documents remain readable/downloadable under the existing rules, but state rules prevent disallowed mutation operations.

### Two-layer authorization

1. B3 organization permission is always the outer security boundary.
2. Optional document ACL can only **restrict** access further.

A document ACL must never grant cross-organization authority or expand B3 permission.

For a restricted document, access requires both the appropriate organization permission and a matching active document-role ACL. Existing resource-hiding 404 semantics must remain intact.

`access.manage` can serve the existing ACL recovery/administration path but **does not itself grant document content read/download**.

### Upload/download

- Uploads go Browser -> BFF/FastAPI -> authorization -> storage.
- No public object URL is the security model.
- Allowed extensions currently include approved PDF/Office/image types in backend policy.
- User filename is sanitized; storage key/path is UUID-derived, not user-controlled.
- Path traversal protections must remain.
- Upload code rechecks authorization/state around the locked document where required to avoid TOCTOU.
- Failed DB transaction after file creation cleans up the uncommitted orphan.
- Download verifies stored checksum and records an Audit event.

### Linking

Current supported link targets are only entities that actually exist in Core, notably Organization and Person. Do not expose fictional future Customer/Supplier targets before those domains exist.

Person linking requires the existing people visibility/relationship rules.

### Retention/expiration

Retention deadline is snapshotted at assignment time. Editing a retention policy does not retroactively recalculate existing document deadlines.

Expiration is informational; it does **not** by itself deny document read/download.

### B6.7 implementation direction

Prefer reusing the approved backend endpoints and add authenticated BFF routes/components for:

- authorized document list/search/filter
- create/upload document
- detail view
- metadata editing
- version upload/history
- secure download
- archive/restore
- links
- categories
- expiration/retention information
- timeline/Audit activity
- restrictive document ACL management where the user's capabilities allow it

Dynamic path identifiers in BFF routes must be safely encoded. Every unsafe BFF method must go through `proxyAuthenticatedRequest()` (or the existing central equivalent) so CSRF/session rules stay uniform.

---

## 10) Frontend/BFF rules

- Frontend routing/permission visibility is UX only.
- Backend must re-authorize every read/write.
- Never send backend access/refresh tokens into React state or browser storage.
- Use the typed shared API helpers instead of ad-hoc fetch patterns where possible.
- Keep BFF mutation routes centralized through `proxyAuthenticatedRequest()`.
- Safely encode dynamic path parameters.
- Preserve responsive RTL/Persian UX and existing desktop/mobile app shell.
- Keep browser Back/Forward and `?view=` deep-link behavior working.
- Partial dashboard failures should not collapse the entire dashboard.
- Avoid creating a second permission/scope model in TypeScript that is treated as authoritative.

---

## 11) Current phase status

### Approved foundations

- Phase A1 — Foundation: approved
- B1 — Organization & Identity: approved
- B2 — Authentication: approved
- B3 — Authorization: approved
- B4 — Audit: approved
- B5.1-B5.5 — Documents platform: approved
- B5.6 — Core Write APIs: approved
- B6.1-B6.3 — Frontend foundation, rotating sessions, main shell/navigation: Claude approved
- B6.4 — Operational Dashboard: Claude approved
- B6.5 — Organization Management UI: Claude approved in the latest user-provided review

### Implemented, review pending

- **B6.6 — People & User Management UI:** Claude approved; minor `SecretStr` hardening applied after review.

B6.6 includes:

- Person create/edit/status
- Person organization relationship create/status
- User create/edit/status
- administrator password reset
- search/filter over authorized result sets
- UX-only scope/capability affordances
- backend self-lockout hardening: actor cannot deactivate the Person linked to their own active User account

B6.6 is approved. Preserve its reviewed authorization and self-lockout protections while continuing B6.7.

### Next

- **B6.7 — Documents UI**
- then **B6.8 — Access / Roles & Permissions UI**

Keep development moving in larger checkpoints to reduce review/package overhead, but do not skip security regression tests.

---

## 12) Claude review history that must constrain future changes

### B6.1-B6.3

Claude confirmed:

- refresh token uses strong randomness and only SHA-256 hash is stored
- refresh rotation is row-locked
- absolute session lifetime is not extended by rotation
- refresh cookie path is minimized
- CSRF/origin guard is centralized
- navigation permissions come from backend-authorized data
- frontend navigation does not become an authorization boundary

Non-blocking future item: refresh-token reuse detection with session-family revocation.

### B6.4

Claude confirmed dashboard behavior is safe even though the BFF can forward raw query strings, because the backend revalidates any explicit organization scope using server-side permission checks. Dashboard aggregates only already-authorized data and introduced no write endpoint.

### B6.5

Claude confirmed:

- Organization PATCH/status BFF paths safely encode dynamic IDs
- writes use the centralized authenticated BFF/CSRF path
- frontend scope logic remains UX-only
- backend independently enforces organization authorization
- root Holding status mutation is bootstrap-only / blocked through normal API
- permission is checked before revealing the specific root-Holding rejection reason

---

## 13) Known technical debt — do not “fix everything” opportunistically

Read `docs/technical-debt.md` for full details. Important current items include:

- authorization organization batching / N+1 patterns
- People/User list SQL filtering and pagination maturity
- future Audit sensitive-field redaction expansion
- failed-login throttling / account lockout policy
- document magic-byte/content verification
- document malware scanning
- LocalStorage streaming for large files
- document ACL visibility-query batching
- session row cleanup and user-visible session management
- refresh-token replay family detection
- dedicated dashboard aggregate API at larger scale
- permission-scoped selector APIs for unusual custom-role combinations

These are not permission to broaden the current task. Fix technical debt only when it is directly relevant, security-critical, or explicitly requested.

---

## 14) Testing / definition of done

For backend changes, run from `backend/`:

```bash
pytest -q
python -m compileall -q app tests scripts
ruff check .
mypy app
```

If Ruff/Mypy are unavailable, report that exact limitation; do not claim they passed.

Verify Alembic against PostgreSQL semantics. At minimum generate/check PostgreSQL offline SQL through current head; prefer a real PostgreSQL migration test when the environment supports it.

For frontend changes, run from `frontend/` after dependencies are installed:

```bash
npm run typecheck
npm run lint
npm run build
```

Do not substitute syntax-only checks for a real Next.js build and call them equivalent. Syntax/semantic shim checks can be supplemental only.

Run focused tests while iterating, then full regression at a checkpoint. To improve speed, do **not** create a review ZIP after every tiny change. Package and fresh-extract verification belong at meaningful checkpoints or when the owner asks for Claude review.

Current B6.6 baseline verification recorded in `B6.6_TEST_RESULTS.md`:

- Backend pytest: **103 passed**
- compileall: passed
- OpenAPI generation: **48 paths**
- Alembic PostgreSQL offline SQL through migration `20260910_0012`: passed
- B6.3 navigation checks: 12 assertions
- B6.4 dashboard checks: 11 assertions
- B6.5 organization checks: 18 assertions
- B6.6 people/user checks: 37 assertions
- TS/TSX syntax parse: 50 files, 0 diagnostics
- dependency-installed `npm typecheck/lint/build`: not claimed because npm install did not complete in the isolated environment

---

## 15) Local development / smoke test

Infrastructure includes `infrastructure/docker-compose.yml` for PostgreSQL.

Backend:

```bash
cd backend
python -m venv .venv
# activate venv
pip install -r requirements.txt
cp ../.env.example .env
# set a strong JWT_SECRET_KEY in .env
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload
```

Frontend in another terminal:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

Development-only seed credentials currently documented in the repository:

- Email: `demo@novinbartar.local`
- Password: `Demo-Only-ChangeMe-123!`

Never reuse demo credentials for production.

---

## 16) Change discipline for Codex

For every task:

1. Inspect the existing implementation before editing.
2. State the narrow goal internally and keep the diff scoped.
3. Reuse approved services/security helpers.
4. Add or update tests for behavior and security invariants.
5. Run focused tests, then checkpoint regression.
6. Update phase docs/technical debt only when the change materially affects them.
7. Produce a concise change summary with exact commands/tests that actually ran.
8. Keep any unresolved limitation explicit.

### Do not do these without explicit approval

- switch framework/language/database
- split into microservices
- add a second auth/session system
- bypass BFF CSRF/session protections
- move authorization trust to the client
- add unscoped/global role assignments
- weaken document ACL to become grant-expanding
- add hard-delete of documents/versions/audit records
- expose public storage URLs as the authorization mechanism
- rewrite Organization hierarchy semantics
- merge Person and User into one model
- introduce new permission-code vocabulary casually
- solve future accounting/CRM/HR concerns inside current Core UI work
- silently change approved status/lifecycle semantics

If an apparently necessary change conflicts with an approved invariant, stop and surface the conflict rather than “fixing” architecture locally.

---

## 17) Recommended first Codex task

Start B6.7 from the current B6.6 source **without modifying approved Documents backend semantics**.

First inspect:

- `backend/app/api/v1/routes/documents.py`
- `backend/app/core/documents/service.py`
- `backend/app/core/documents/schemas.py`
- `backend/app/core/documents/security.py`
- `frontend/lib/authenticated-backend.ts`
- existing BFF route patterns under `frontend/app/api/core/`
- `frontend/components/app/AppShell.tsx`
- `frontend/lib/navigation.ts`
- `docs/phase-b5.2-documents-api.md`
- `docs/phase-b5.3-document-linking-lifecycle.md`
- `docs/phase-b5.4-document-level-access-control.md`
- `docs/phase-b5.5-document-operations.md`

Then implement B6.7 incrementally with backend-authoritative security preserved. Treat the B6.6 Claude approval as part of the baseline. Preserve the post-review `SecretStr` hardening while continuing B6.7.

---

## 18) Source authority

If this handoff conflicts with actual current code in a small implementation detail, inspect the code and phase docs before changing anything. If it conflicts with a security/architecture invariant listed above, treat the invariant as intentional and escalate the discrepancy instead of silently choosing a new design.

The project owner wants speed **without sacrificing the security quality already reviewed by Claude**. Optimize the workflow, not the security model.
