# Claude Approval — C2 Notifications Core

Status: **APPROVED — no blocking findings**.

Claude confirmed:
- list/get/read/unread/read-all are recipient-scoped in SQL by `recipient_user_id == current_user.id`, preventing cross-user IDOR;
- there is no public arbitrary notification-creation endpoint;
- domain modules create notifications internally and in the producer transaction;
- `action_path` is protected by an explicit local-path allowlist against external, protocol-relative, backslash, and control-character redirect tricks;
- Workflow derives the recipient from already-authorized instance data (`started_by_user_id`), not direct client input;
- Workflow transition history is immutable like Audit.

No blocker was reported.
