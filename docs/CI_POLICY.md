# CI Policy — Novin Bartar Super App

## Purpose

CI is a mandatory merge gate. Architecture/code review approval does not close a phase until the relevant automated quality, test, migration, and frontend build jobs pass.

## Required jobs

1. **Backend / Ruff + Mypy**
   - Python 3.12
   - install `backend/requirements.txt`
   - `ruff check app tests`
   - `mypy app`
   - Python compile sweep

2. **Backend / Pytest isolated files**
   - every `backend/tests/test_*.py` file is executed in a separate pytest process
   - this is intentional: the current consolidated local suite can hang during process teardown even after individual files pass
   - any file timeout/failure fails CI

3. **Database / PostgreSQL migrations**
   - PostgreSQL 17 service
   - `alembic upgrade head` against a real PostgreSQL database
   - assert a single Alembic head
   - generate offline SQL as a secondary check

4. **Frontend / Typecheck + Lint + Build**
   - Node.js 22
   - a committed `frontend/package-lock.json` is mandatory
   - install with `npm ci`
   - deterministic phase checks B6.3 through D3
   - `npm run typecheck`
   - `npm run lint`
   - `npm run build`

5. **CI Gate**
   - succeeds only when all required jobs succeed
   - configure branch protection so this job is required before merge

## One-time frontend lockfile bootstrap

The D3 review package did not contain `frontend/package-lock.json` and the offline review environment could not reach npm.

Run the GitHub Actions workflow **Bootstrap Frontend Lockfile** once. It generates `frontend/package-lock.json` and uploads it as the `frontend-package-lock` artifact.

Download that artifact, place `package-lock.json` in `frontend/`, commit it, and re-run CI.

After the lockfile is committed, normal CI uses `npm ci`; the bootstrap workflow should only be needed when intentionally regenerating the dependency graph.

## D3 closure rule

D3 may be marked `CLOSED` only after:

- Claude implementation review: Approved
- Backend Ruff: Pass
- Backend Mypy: Pass
- Backend tests: Pass
- PostgreSQL migration job: Pass
- Frontend deterministic checks: Pass
- Frontend TypeScript typecheck: Pass
- Frontend ESLint: Pass
- Frontend Next.js production build: Pass
- CI Gate: Pass

Until then, D3 remains `CODE/ARCHITECTURE APPROVED — CI GATE PENDING`.
