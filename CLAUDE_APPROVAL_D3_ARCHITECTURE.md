# Claude Architecture Review — D3 Suppliers Foundation

Verdict: **Approved with changes — no blockers.**

Before implementation, the independent architecture review requested four clarifications/hardenings. All four were incorporated into the D3 specification and implementation:

1. **Active-primary representative invariant** — enforce at database level with a partial unique index so a supplier cannot have more than one active primary representative.
2. **Contact privacy beyond Audit** — never use phone/email in URLs, exclude raw values from Audit/logs, and gate unmasked contact release behind a dedicated permission while lower-permission views remain masked.
3. **Tag permission split** — distinguish creating/managing the organization tag catalog from assigning/removing existing tags.
4. **External ID normalization** — define deterministic normalization. D3 uses Unicode NFKC + trim + control-character rejection while preserving case to avoid corrupting potentially case-sensitive external identifiers.

After these changes, implementation proceeded. The current checkpoint is implementation-level independent review; this file is not an implementation approval.
