# Integration Contract Authority Resolution

Date: 2026-09-13
Scope: Novin Bartar Super App + Enferadi Market / Customer Platform
Status: CANONICAL AUTHORITY DECISION

## Canonical baseline

The one and only active `Integration Contract v1.1-FROZEN` is:

- File: `api-integration-contract-v1.1-FROZEN.md`
- SHA-256: `903a5c649bf8d3e5f16998405fcb687d8bf07a427f793c35fc9a8b74e608f59f`
- Claude verdict: `APPROVED FOR FREEZE`

This artifact was derived from the historical v1 primary artifact, reviewed as v1.1, corrected only for the requested S2S/TTL/mobile-change items, hash-verified, and then explicitly approved for freeze by Claude.

## Fork resolution

A separate reconstructed document appeared with:

- Name observed: `api-integration-contract-v1.1-FROZEN-CANDIDATE.md`
- SHA-256 observed: `542eabec...0b7fa3d` (as reported in the cross-track review)
- Pack SHA-256 observed: `2edffcee...358267`

That reconstructed document is **NOT** an approved `v1.1-FROZEN` baseline.

It is classified as:

`REJECTED AS FREEZE CANDIDATE / SUPERSEDED DRAFT`

It must not be used as the contract authority, must not be renamed to `v1.1-FROZEN`, and must not be cited as the active baseline in either repository, roadmap, closure record, or implementation task.

## Versioning rule

If the reconstructed structure is preferred later, it may only return as a **new version** (for example `v1.2`) and must go through a fresh primary architecture review and receive its own hash and explicit approval.

No incompatible edit may overwrite the canonical v1.1 file while retaining the same version label.

## Open pre-production gates remain open

Freezing v1.1 does not close these gates:

1. Mahak physical-sale vs online-reservation concurrency.
2. Replacement/refund/incremental-payment semantics.
3. Single-branch vs split-branch fulfillment policy.
4. PSP selection for production online payment.
5. Concrete DLQ/manual-recovery mechanism before production cross-system dependency.

## Repository rule

Both Tracks must vendor or reference the **exact canonical bytes** above. A copied contract is valid only if its SHA-256 equals the canonical hash.

Any hash mismatch means the file is not the frozen baseline and must be treated as a different artifact.
