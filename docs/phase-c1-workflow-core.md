# Phase C1 — Workflow Core

## Goal
Provide a reusable, organization-scoped workflow engine for Core and future business modules without coupling Workflow to domain tables.

## Security model
- Canonical permissions: `workflow.read`, `workflow.manage`, `workflow.execute`.
- Every API requires authentication.
- Organization scope is enforced server-side with the existing B3 authorization policy.
- Workflow definitions are owned by one organization and use `SELF` or `SELF_AND_DESCENDANTS` applicability.
- Definition management is authorized against the owner organization.
- Instance execution is authorized against the target organization.
- Cross-organization direct object access fails closed; instance/definition lookup paths hide inaccessible objects as not found where appropriate.

## Definition lifecycle
- New definitions start as `draft`.
- Draft states/transitions may be edited.
- Publish validates exactly one initial state, at least one terminal state, no outgoing transitions from terminal states, no non-terminal dead ends, and reachability of every state from the initial state.
- Published definitions are immutable.
- A new version clones the published/retired version into a new draft with new state/transition IDs.
- Publishing a new version retires the previously published version for the same owner+code.
- Retired definitions cannot start new instances, while existing instances continue against their pinned definition version.

## Instance lifecycle
- Generic domain references use `resource_type` + `resource_id`; Workflow does not directly query another module's tables.
- One instance per workflow-version + organization + resource reference.
- Transitions lock the instance row before validating the current state.
- Reaching a terminal state completes the instance.
- Active instances may be cancelled; completed instances cannot be cancelled.
- Transition history is append-only and immutable at both ORM level and PostgreSQL trigger level.

## Audit
Writes are recorded in the existing immutable Core Audit transaction:
- `workflow.definition.created`
- `workflow.definition.updated`
- `workflow.definition.published`
- `workflow.definition.retired`
- `workflow.definition.version.created`
- `workflow.state.created|updated|deleted`
- `workflow.transition.created|updated|deleted`
- `workflow.instance.started|transitioned|cancelled`

## Migration
`20260911_0013_workflow_core.py`
- Creates workflow tables and enum types.
- Adds workflow permissions.
- Updates canonical `super_admin` with the new Core permissions during upgrade.
- Adds PostgreSQL immutability trigger for transition history.

## Deliberate boundary
The generic Workflow API stores an opaque resource reference and does not validate business-domain resource existence. Domain modules must validate their own entity before calling Workflow. This preserves the Modular Monolith rule that Core Workflow must not directly access business-module tables.


## Operational UI
C1 also exposes the Workflow engine through the authenticated Next.js UI/BFF:
- permission-aware Workflow navigation
- workflow-specific organization capability discovery that does not require `organization.read`
- draft definition create/edit, states, transitions, publish/retire, and version cloning
- published-instance start, state transition, cancel, status filtering, and immutable history display
- dynamic BFF path parameters are encoded and every unsafe browser mutation continues through the centralized CSRF/origin guard
- frontend capability checks are UX only; FastAPI remains the authorization source of truth

`GET /api/v1/workflow/organizations` returns only active organizations where the current user already has at least one effective Workflow permission and exposes `can_read` / `can_manage` / `can_execute` booleans for UI composition. It intentionally does not broaden Organization read access.
