# Shared Artifact Registry

Last reconciled: 2026-09-13

| Artifact | Version | Editing Owner | Consumers | Canonical SHA-256 | Lifecycle | Notes |
|---|---|---|---|---|---|---|
| Virtual Store ↔ Super App Integration Contract | v1.1 | Super App / Joint Integration Architecture owner | Super App + Customer Platform | `903a5c649bf8d3e5f16998405fcb687d8bf07a427f793c35fc9a8b74e608f59f` | **FROZEN** | Claude `APPROVED FOR FREEZE`; hash `542eabec...0b7fa3d` is retired/do-not-use |

## Reserved future shared artifacts

The following are not yet canonical artifacts. When created, each must receive one
Editing Owner before parallel work begins:

- cross-system Event Schema Registry;
- Fulfillment event/payload schemas;
- S2S service identity/profile extensions beyond Contract v1.1;
- DLQ/manual-recovery operating contract;
- shared correlation/error envelope extensions.

A reserved item must not be implemented as two same-version baselines in parallel.
