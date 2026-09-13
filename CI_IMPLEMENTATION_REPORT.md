# CI Implementation Report

## What was added

- `.github/workflows/ci.yml`
- `.github/workflows/bootstrap-frontend-lockfile.yml`
- `scripts/ci/backend-tests.sh`
- `scripts/ci/frontend-checks.sh`
- `docs/CI_POLICY.md`
- `D3_CI_GATE_STATUS.md`

## Local validation completed

- GitHub workflow YAML parsed successfully.
- CI shell scripts passed `bash -n`.
- Python compile sweep passed.
- Alembic offline PostgreSQL upgrade SQL generated successfully through head `20260911_0017`.
- D3 partial unique index assertion target was verified in migration SQL.
- Full network-dependent CI could not be executed in this offline environment.
- Ruff/Mypy are not installed locally and require dependency installation.
- Frontend lockfile is intentionally not fabricated; it must be generated from npm in a networked environment.

## Required next action

1. Put this repository in GitHub.
2. Run the manual workflow `Bootstrap Frontend Lockfile` once.
3. Download its `frontend-package-lock` artifact.
4. Commit the generated file as `frontend/package-lock.json`.
5. Re-run `CI`.
6. Configure branch protection so `CI Gate` is required before merge.
7. D3 closes only after the CI Gate is green.
