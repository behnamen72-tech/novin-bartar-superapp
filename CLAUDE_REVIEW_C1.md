# Claude Review Request — C1 Workflow Core + Operational UI

Please review C1 cumulatively against the Claude-approved B6.8 baseline. Focus on security boundaries, lifecycle correctness, transaction semantics, and whether the generic Workflow Core remains reusable for future business modules.

## Backend changes to review

### Models / migration
- `backend/app/core/workflow/models.py`
- `backend/app/core/workflow/events.py`
- `backend/alembic/versions/20260911_0013_workflow_core.py`

Confirm:
- definition versioning and immutable published/retired semantics
- instance pinning to an exact definition version
- transition history append-only semantics at ORM + PostgreSQL trigger layers
- restrictive FKs/indexes/uniques are appropriate
- new `workflow.read`, `workflow.manage`, `workflow.execute` permissions integrate with the existing B3 model

### Service / policy integration
- `backend/app/core/workflow/service.py`
- `backend/app/api/v1/routes/workflow.py`
- `backend/app/core/workflow/schemas.py`

Confirm:
- owner-org manage checks for definition mutations
- target-org execute checks for instance actions
- `SELF` / `SELF_AND_DESCENDANTS` applicability is correct
- inaccessible definition/instance object paths fail closed and avoid cross-company disclosure
- publish graph validation is sufficient
- instance transitions lock before current-state validation
- Audit is emitted in the same transaction as every meaningful write
- generic `resource_type` + `resource_id` boundary does not couple Core Workflow to future business tables

### New capability discovery endpoint
`GET /api/v1/workflow/organizations`

Confirm it does not depend on `organization.read`, returns only active organizations where the actor already has at least one effective Workflow permission, and does not create a new authorization bypass. It exposes only basic org selector fields plus `can_read`, `can_manage`, `can_execute`.

## Frontend / BFF changes to review
- `frontend/components/core/WorkflowManagementView.tsx`
- `frontend/lib/workflow-management.ts`
- `frontend/lib/core-types.ts`
- `frontend/lib/navigation.ts`
- `frontend/lib/permissions.ts`
- `frontend/app/api/core/workflow/**`

Confirm:
- frontend capability checks are UX only; Backend remains authoritative
- every unsafe write still passes through `proxyAuthenticatedRequest` and centralized CSRF/origin protection
- dynamic IDs are encoded before being placed in backend paths
- no token/auth material moved into browser state/storage
- users without `workflow.read` do not get definition/instance browsing merely because they have another Workflow capability
- definition edit/publish/version UI respects immutable lifecycle
- instance UI only offers transitions from the current state and treats backend rejection as authoritative

## Verification performed
See `C1_TEST_RESULTS.md`.

Current local results:
- Backend pytest: 116 passed
- Backend compileall: passed
- Alembic offline PostgreSQL SQL: through 0013 passed
- OpenAPI: 62 paths total / 14 Workflow paths
- cumulative frontend invariant scripts: passed
- C1 frontend assertions: 43 passed
- TypeScript syntax scan: 93 files / 0 syntax diagnostics

Real dependency-installed Next.js typecheck/lint/build is not claimed because `node_modules` is absent in the isolated runtime.

Please report blockers separately from non-blocking production/scale recommendations.
