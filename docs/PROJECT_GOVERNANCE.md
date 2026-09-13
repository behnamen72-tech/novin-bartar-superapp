# Project Governance — Artifact-Based Closure

Effective: 2026-09-12

This policy is the authoritative closure rule for the Novin Bartar Super App track.
It was adopted after the four-party architecture alignment review found that phase
status summaries could drift from the evidence actually reviewed.

## Closure rule

A phase or gate may be marked `CLOSED` only when the closure record points to all
of the following evidence for the same artifact/version:

1. **Primary artifact** — code, schema, migration, contract, or other actual deliverable.
2. **Artifact version/hash** — immutable version, commit SHA, package SHA-256, or equivalent.
3. **Primary independent review** — Claude must have reviewed the primary artifact, not only a summary.
4. **Relevant executable evidence** — tests, CI, migration, runtime, race/concurrency, or operational evidence appropriate to that phase.

Where real runtime behavior is material to the phase, static review alone cannot
close the phase.

## Status vocabulary

- `DRAFT`: design is incomplete or not yet submitted for independent review.
- `ARCHITECTURE_APPROVED`: architecture/specification reviewed; implementation is not implied.
- `IMPLEMENTATION_CANDIDATE`: code exists but has not completed the closure evidence chain.
- `IMPLEMENTATION_APPROVED`: primary implementation artifact was independently reviewed.
- `CI_PENDING`: implementation review is complete but required CI/runtime evidence is incomplete.
- `PILOT`: technically deployable evidence exists and controlled operational use is underway.
- `CLOSED`: the full closure rule above is satisfied.

A summary or handoff may report status, but it must never promote a phase from one
status to another without evidence recorded in the phase closure record.

## Closure record minimum fields

Every closure record must contain:

- phase/gate name;
- primary artifact name/version;
- artifact SHA/commit;
- architecture review reference, if applicable;
- implementation review reference, if applicable;
- test/CI/runtime references;
- current closure status;
- closure date when closed;
- open non-blocking findings;
- blockers preventing closure.

## Cross-track architecture rules

The following ecosystem decisions are treated as frozen baselines unless changed
by explicit management decision plus architecture review:

- Internal `User` / `Person` / `Employee` identity is not Commerce `Customer` identity.
- Super App and Customer Platform do not share identity tables or business-domain database tables.
- Direct cross-system database access is prohibited.
- Commerce Order authority remains in the Customer Platform.
- Internal fulfillment workflow authority remains in the Super App.
- Physical stock system of record is Mahak; Super App is not the inventory authority.
- Initial commerce stock policy is shared physical branch inventory.
- Customer Platform owns commerce branch routing and the customer-facing status projection.
- Store revenue path must survive Super App outages.
- Same-named capabilities across the two systems (Audit, Search, Notifications, Files) are not shared runtime services by default.

## Change control

A frozen architecture baseline may change only through an explicit versioned
artifact and a new architecture review. Backward compatibility requirements must
be stated whenever an integration contract changes.

## Shared artifact editing ownership

Cross-track artifacts have exactly one Editing Owner. The other track may request
changes but must not publish a competing artifact with the same canonical version.
A post-freeze material/incompatible change requires a new version, new artifact/hash,
and new architecture review. Retired hashes remain recorded for detection.

Authoritative details and current ownership are maintained in:

- `docs/SHARED_ARTIFACT_GOVERNANCE.md`
- `docs/SHARED_ARTIFACT_REGISTRY.md`
