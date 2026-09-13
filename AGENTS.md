# AGENTS.md — Novin Bartar Super App

Read `CODEX_MASTER_HANDOFF_B6.6.md` before editing.

## Non-negotiable project rules

- Continue from this repository; do not rebuild from scratch.
- Modular Monolith: FastAPI + Next.js/React/TypeScript + PostgreSQL + SQLAlchemy/Alembic.
- REST backend stays under `/api/v1`.
- Backend service layer is the authorization source of truth; frontend permission logic is UX only.
- Use current permission codes (`*.read` / `*.manage`); do not invent a new permission vocabulary casually.
- All user role assignments are organization-scoped. Preserve anti-privilege-escalation/dominance rules.
- Unsafe browser writes go through the authenticated BFF and centralized CSRF/origin guard.
- Do not expose access/refresh tokens to browser storage/React state.
- Every meaningful Core write must Audit in the same transaction.
- Documents ACL can only restrict B3 access, never expand it. Preserve 404 resource-hiding behavior where implemented.
- No hard delete of documents/versions/audit history.
- Root Holding management remains bootstrap-only where current code enforces it.
- Person and User remain separate models.
- Avoid unrelated refactors and technical-debt scope creep.
- Never claim a test/build passed unless it actually ran.

## Current checkpoint

Phase B and Phase C are closed. D1 HR Foundation and D2 Customer Reference / CRM Foundation are Claude-approved and closed. D3 Suppliers Foundation is the active implementation-review checkpoint.

D3 preserves the back-office domain boundaries: Supplier is not an Internal Organization, SupplierRepresentative is not an Internal Person/User/Employee, and Supplier data is not authoritative accounting/inventory/Commerce data. The Virtual Store must not directly consume supplier contacts, internal notes, purchase cost, or internal supplier status, and Store registration/login/cart/checkout/payment/order creation must never depend on Supplier-module availability.

The four D3 architecture-review corrections are mandatory implementation invariants: one active primary representative per supplier enforced at DB level; raw representative contact gated by explicit permission and never used in URLs/Audit; tag-catalog management separated from tag assignment; external IDs normalized with NFKC+trim/control-character rejection while preserving case.

D1 remains foundation-only: do not add payroll/attendance/recruitment scope without a separate approved phase, and revisit Audit redaction before future sensitive HR fields are introduced.

D2 remains closed; do not weaken the Commerce Customer vs Internal User/Person/Employee identity boundary.

## Required verification at meaningful checkpoints

Backend: `pytest -q`, `python -m compileall -q app tests scripts`, and migration validation.  
Frontend: dependency-installed `npm run typecheck`, `npm run lint`, `npm run build` when available.  
Report any environment limitation exactly.
