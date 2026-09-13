# Claude Review Request — B6.6 People & User Management

Please review B6.6 as a security/architecture checkpoint, using B6.5 as the
baseline. Focus on the actual code rather than only this note.

## Files to inspect first

- `frontend/components/core/PeopleManagementView.tsx`
- `frontend/components/core/UserManagementView.tsx`
- `frontend/lib/people-user-management.ts`
- `frontend/app/page.tsx`
- `frontend/app/api/core/people/**/route.ts`
- `frontend/app/api/core/users/**/route.ts`
- `backend/app/core/people/service.py`
- `backend/app/core/identity/admin_service.py`
- `backend/app/core/access/service.py` (dominance / privilege-escalation rules)
- `frontend/lib/authenticated-backend.ts`

## Questions for review

1. Confirm no People/User write route bypasses the authenticated BFF or the
   centralized CSRF/origin guard.
2. Confirm frontend scope calculations are UX-only and cannot expand backend
   authority.
3. Confirm shared Person edits are ultimately protected by backend authorization
   across every relevant organization relation.
4. Confirm relationship activation/deactivation preserves the B5.6 access
   assignment conflict rule.
5. Confirm User create/edit/status/password-reset operations remain protected by
   `users.manage` plus backend anti-privilege-escalation dominance checks.
6. Confirm passwords are not logged, rendered after submission, stored in app
   data, or included in Audit payloads.
7. Check for IDOR, stale-state, unsafe client trust, session/CSRF regression, and
   cross-organization disclosure introduced by B6.6.

## Additional backend hardening discovered during B6.6

While wiring the Person lifecycle UI, B6.6 found an indirect self-lockout path:
`users/{id}/status` already blocked self-deactivation, but `people/{person_id}/status`
could deactivate the Person attached to the actor's own account. B6.6 now rejects
that operation with `409`, and a regression test confirms the Person remains active.
Please review this change in `backend/app/core/people/service.py` as part of the checkpoint.

## Expected security boundary

The browser decides only whether to show an affordance. FastAPI services remain
the source of truth for authorization, scope, invariants, transactions, and
Audit. A frontend false-positive should therefore fail closed at the backend.

Please classify findings as BLOCKER / SHOULD-FIX / NON-BLOCKING and state
whether B6.6 is approved to proceed to the next UI module.
