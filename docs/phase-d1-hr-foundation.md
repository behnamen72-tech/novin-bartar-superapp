# Phase D1 — HR Foundation

## Goal
Provide a reusable Human Resources foundation for future businesses without assuming that any specific hypermarket, factory, restaurant, cafe, company, or branch already exists.

D1 is intentionally a **business foundation**, not a payroll or workforce-operations product. It models reusable job profiles, planned organization positions, and employment history on top of the already-approved Organization and Person cores.

## Deliberate boundary
D1 does **not** implement:
- payroll, salary, benefits, tax, or accounting;
- attendance, shifts, leave, overtime, or time clocks;
- recruitment/applicant tracking;
- performance reviews or training;
- business-specific staffing rules for hypothetical future companies.

These may be added later as separate modules once the real operating requirements exist.

## Domain model

### Job Profile
`HRJobProfile` is a reusable business description of a job such as “Finance Manager” or “Store Supervisor”.

It is **not** an Access `Role` and grants no software permission. Access Roles remain part of the B3/B5.6 authorization model.

A Job Profile is owned by one organization and has an applicability scope:
- `SELF`: only the owner organization may use it.
- `SELF_AND_DESCENDANTS`: active descendant organizations may use it for planned positions.

An inherited profile is read-only from the descendant organization UI; mutations belong to the owner and are subject to impacted-organization authorization.

### Planned Position
`HRPosition` is an organization-owned seat in the future organization chart. A position may exist while vacant; no Person is required when it is created.

A position:
- belongs to exactly one organization;
- references an applicable active Job Profile;
- may report to another active position in the **same organization**;
- cannot report to itself or form a reporting cycle;
- cannot be deactivated while an active child position reports to it or an active employment occupies it.

This lets the holding design a future structure before hiring people.

### Employment
`HREmployment` links an existing `Person` to one organization and optionally to one planned position.

D1 keeps employment history rather than hard-deleting it. Ending an employment sets it inactive and records an end date; reactivation is explicit and revalidates current prerequisites.

Foundation invariants:
- the Person must be active;
- the Person must have an active Person↔Organization relationship applicable on the employment start date;
- one Person may have at most one active employment in the same organization;
- one position may have at most one active occupant;
- the position, when present, must be active and belong to the same organization;
- employment number is unique within the organization when supplied;
- `end_date` cannot precede `start_date`.

Person and employment remain separate concepts: the Core Person record can exist before, during, or after an employment.

## Authorization
Canonical D1 permissions:
- `hr.read`
- `hr.manage`

The backend remains the authorization source of truth. HR organization discovery is based on effective HR permissions and does not require `organization.read` merely to compose the HR UI.

### Shared-profile mutation safety
A descendant-scoped Job Profile can be referenced by positions in multiple organizations. A mutation to that shared profile therefore computes the actual impacted organizations (owner + organizations with active positions using the profile) and requires `hr.manage` over **all** of them.

This prevents a manager with control only over the owner organization from changing shared HR structure that is already in use by a descendant organization outside that manager's effective management scope.

Narrowing a profile from `SELF_AND_DESCENDANTS` to `SELF` is blocked while active descendant positions still use it.

### Resource hiding
Direct resource-ID write attempts against HR resources outside the actor's effective management scope fail as not found where the HR service uses protected resource lookup. This follows the existing Core resource-hiding pattern and avoids cross-company object disclosure.

## Concurrency and integrity
- Employment creation locks the Person row before checking for another active employment in that organization.
- Position assignment locks the position before checking for an existing active occupant.
- Position and profile mutations use row locks where state-dependent invariants are enforced.
- Database constraints and `RESTRICT` foreign keys protect structural references.

## Audit and lifecycle
All meaningful D1 writes use the existing immutable Audit service in the same transaction. Representative actions include:
- `hr.job_profile.created|updated|status.changed`
- `hr.position.created|updated|status.changed`
- `hr.employment.created|updated|status.changed`
- `hr.employment.end_date.corrected`

D1 provides status transitions rather than hard-delete APIs for HR structural/history records.

## API surface
Backend prefix: `/api/v1/hr`

- `GET /organizations`
- `GET|POST /job-profiles`
- `PATCH /job-profiles/{profile_id}`
- `POST /job-profiles/{profile_id}/status`
- `GET|POST /positions`
- `PATCH /positions/{position_id}`
- `POST /positions/{position_id}/status`
- `GET /people`
- `GET|POST /employments`
- `PATCH /employments/{employment_id}`
- `POST /employments/{employment_id}/status`

## Operational UI
The Persian RTL D1 UI exposes three foundation work areas:
- Job Profiles
- Planned Positions
- Employment History

The UI intentionally emphasizes vacant planned positions so a future organization chart can be prepared before the actual workforce exists. Browser writes continue through the authenticated Next.js BFF and centralized CSRF/origin guard; frontend capability checks are UX only.

## Migration
`20260911_0015_hr_foundation.py`
- creates HR Job Profile, Position, and Employment tables;
- adds enum types and indexes/constraints;
- adds `hr.read` and `hr.manage` permissions;
- leaves existing Core/Workflow/Notification/Search schemas unchanged.
