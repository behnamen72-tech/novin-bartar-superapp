# Super App Operational Pilot Runbook

Status: **Prepared; pilot start blocked by D3 green CI gate**

The pilot is a controlled operational deployment of the current Super App for real
staff usage. Its purpose is to convert static design/test evidence into operational
evidence without prematurely treating the system as production-complete.

## Entry criteria

All entry criteria are mandatory:

- D3 `ci-gate` is green on the exact commit selected for pilot.
- `frontend/package-lock.json` is committed and `npm ci` is reproducible.
- PostgreSQL migration job has executed successfully against PostgreSQL 17.
- Ruff, Mypy, backend tests, frontend typecheck/lint/build are green.
- Pilot commit SHA and CI run URL/ID are recorded in `docs/closure/D3_CLOSURE_RECORD.md`.
- Non-development secrets are generated; no example secret is reused.
- Pilot hostname/TLS and backup location are defined.
- A rollback owner and an operational owner are named outside the source repository.

## Pilot scope

Start with a deliberately bounded staff group. Exercise the already-built platform:

- authentication/session flows;
- organizations;
- people/users;
- roles/permissions/organization scope;
- audit;
- documents and document ACL;
- workflow;
- notifications;
- search;
- D1 HR foundation;
- D2 CRM functions only after its implementation evidence is re-verified;
- D3 suppliers after the D3 CI gate is closed.

Do not enable unfinished cross-system Store dependencies during the pilot.

## Deployment sequence

1. Provision PostgreSQL 17 with persistent storage and a tested backup target.
2. Generate deployment secrets (JWT and any enabled integration credentials).
3. Configure explicit CORS origins; wildcard CORS is prohibited.
4. Configure persistent document storage and verify backup coverage for it.
5. Run `scripts/pilot/preflight.sh` from the exact pilot artifact/commit.
6. Run `alembic upgrade head` once against the pilot database.
7. Bootstrap the first administrator using the existing controlled scripts.
8. Start backend and frontend behind TLS/reverse proxy infrastructure.
9. Run the smoke checklist below before staff access is enabled.
10. Enable the bounded staff cohort and begin issue capture.

## Smoke checklist

At minimum verify:

- `GET /api/v1/health` succeeds;
- login succeeds for an authorized pilot admin;
- invalid/inactive login behavior is non-disclosing;
- organization-scoped reads do not leak cross-organization resources;
- create/update actions produce Audit events;
- document upload/download respects ACL and storage persistence;
- role/permission updates take effect without relying on stale frontend state;
- workflow and notification screens load for authorized users;
- search respects existing authorization before result limiting;
- Supplier raw contacts remain masked without the dedicated permission;
- one-active-primary Supplier Representative database invariant remains enforced.

## Operational evidence to capture

Record evidence by pilot commit/version, not as free-form memory:

- deployment timestamp;
- commit SHA;
- CI run reference;
- migration head;
- staff cohort size;
- login/session failures;
- authorization defects;
- data-integrity defects;
- document/storage failures;
- workflow/notification/search failures;
- page/API latency observations;
- operational confusion or missing workflow steps;
- every rollback/restart and its cause.

Never place secrets, tokens, private note bodies, raw supplier contacts, or customer
sensitive data in the pilot issue log.

## Severity and stop conditions

Stop the pilot and rollback/escalate for:

- cross-organization data exposure;
- authentication/session bypass;
- privilege escalation;
- lost/corrupted business data;
- audit immutability failure;
- document ACL bypass;
- migration inconsistency;
- repeated unbounded process/resource failure.

Lower-severity UX defects may be collected while the pilot continues if they do not
create security, integrity, or operational safety risk.

## Rollback principle

Application rollback must never blindly downgrade a database after real writes.
Prefer restoring the prior application version when schema compatibility permits.
Any database restore/downgrade requires an explicit backup/recovery decision and
must preserve Audit/data integrity.

## Exit criteria

Pilot exit is not "zero bugs". A successful pilot produces enough operational evidence
to classify discovered defects, harden the deployment, and decide whether the same
artifact lineage can progress to broader use.
