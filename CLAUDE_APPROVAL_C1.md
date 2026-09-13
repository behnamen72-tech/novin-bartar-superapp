# Claude Approval — C1 Workflow Core

C1 was reviewed and approved with no blocking finding.

Confirmed review points:
- real state-machine Definition/State/Transition/Instance/TransitionRecord model
- immutable/append-only history
- graph reachability validation before publish
- published definitions immutable with proper versioning and previous-version retirement
- transitions require the exact current state and cannot jump arbitrarily
- row locking on transition
- inaccessible instances/definitions use non-disclosing 404 behavior where appropriate
- Audit is recorded atomically
- organization scope reuses the approved B3 policy

Non-blocking design note retained: cancelling an instance currently requires the same execution permission used to advance it rather than a stricter separate cancellation permission.
