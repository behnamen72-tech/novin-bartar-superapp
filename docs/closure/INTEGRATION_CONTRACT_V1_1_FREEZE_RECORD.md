# Freeze Record — Integration Contract v1.1

Status: **FROZEN ARCHITECTURE BASELINE**
Freeze confirmed: 2026-09-13

## Canonical artifact

- File: `docs/integration/api-integration-contract-v1.1-FROZEN.md`
- SHA-256: `903a5c649bf8d3e5f16998405fcb687d8bf07a427f793c35fc9a8b74e608f59f`
- Claude primary verdict: `APPROVED FOR FREEZE`
- Scope: both tracks — Novin Bartar Super App and Enferadi Market / Customer Platform.

## Provenance / authority resolution

A competing reconstructed v1.1 candidate was discovered with SHA-256:

`542eabec901129bdb1f34b6155188b955503d3c1d2576553ec0e230960b7fa3d`

That artifact is **RETIRED / DO NOT USE** because it created a competing v1.1
baseline/provenance fork. It is not equivalent to the canonical reviewed artifact.

See:
- `docs/integration/CONTRACT_AUTHORITY_RESOLUTION.md`
- `docs/SHARED_ARTIFACT_GOVERNANCE.md`
- `docs/SHARED_ARTIFACT_REGISTRY.md`

## Open pre-production gates

Architecture freeze does **not** close these gates:

1. Mahak physical-sale ↔ online-reservation concurrency.
2. Replacement / refund / incremental-payment semantics.
3. Single-branch vs split-branch fulfillment policy.
4. PSP selection for production online payment.
5. Concrete DLQ / manual-recovery design and evidence.

## Change control

Any incompatible/material change requires:

- a new version;
- a new primary artifact/hash;
- a new architecture review;
- registry update after approval.

The non-owner track requests changes; it does not publish a competing same-version
canonical artifact.
