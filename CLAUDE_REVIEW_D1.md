# Claude Review Request — D1 HR Foundation

Please review D1 against the approved C3 baseline. D1 is intentionally a **foundation for possible future businesses**, not an assumption that those businesses already exist.

## Primary review targets

1. **Authorization and cross-company isolation**
   - Verify `hr.read` / `hr.manage` reuse the existing B3 organization-scope policy correctly.
   - Verify direct guessed HR resource IDs cannot expose or mutate cross-company resources.
   - Verify `/hr/organizations` discovers effective HR capabilities without accidentally broadening `organization.read`.

2. **Shared Job Profile impact authorization**
   - A profile owned by one organization may be `SELF_AND_DESCENDANTS` and used by descendant positions.
   - Verify profile mutation computes all real impacted organizations (owner + active position organizations) and requires actor management over all of them.
   - Verify narrowing descendant applicability is blocked while active descendant positions depend on the profile.
   - Confirm this business Job Profile cannot grant software Access permissions and is not conflated with B3/B5.6 `Role`.

3. **Planned Position integrity**
   - Same-organization reporting parent only.
   - No self-reporting or reporting cycle.
   - Active parent/profile prerequisites on create/reactivate.
   - Deactivation blocked while active child positions or active employment depend on the position.

4. **Employment integrity / concurrency**
   - Person must have an applicable Person↔Organization relationship on the employment start date.
   - Future planned start dates should be valid only when the relationship covers that future date.
   - Verify Person and Position row locks are sufficient for the application-layer single-active-employment / single-active-occupant invariants in PostgreSQL transactions.
   - Position must be active and in the same organization.
   - End/reactivate keeps history; no hard-delete endpoint.

5. **Audit and transaction behavior**
   - Meaningful writes Audit in the same transaction.
   - No write path commits domain state and Audit separately.

6. **Frontend/BFF boundary**
   - All unsafe browser writes use `proxyAuthenticatedRequest` and the central CSRF/origin protection.
   - Dynamic path IDs use `encodeURIComponent`.
   - Frontend permissions are UX composition only; backend remains authoritative.

7. **Scope discipline**
   - D1 should not introduce payroll, attendance, leave, recruitment, accounting, or business-specific assumptions.
   - Planned positions may remain vacant and are usable before future businesses are staffed.

Please report blockers separately from non-blocking hardening or future-domain suggestions.
