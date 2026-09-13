# Claude Review Request — C2 Notifications Core

Please review C2 against the approved C1 baseline, with emphasis on security boundaries and transactional behavior.

## Expected architecture
1. Personal notification reads are recipient-bound (`current_user.id`) rather than B3 organization-permission-bound.
2. No public API can create arbitrary notifications. Producers call `app.core.notifications.service.create_notification` internally.
3. Notification content and ownership are immutable; only `read_at` is mutable. PostgreSQL trigger + ORM listener enforce this.
4. Physical notification deletion is prohibited.
5. `action_path` accepts only app-local paths and must not become an open-redirect surface.
6. Destination authorization is not inferred from a notification; destination APIs must reauthorize normally.
7. Cross-user direct-object access must fail as `404`.
8. `create_notification` must not commit; notification creation participates in the producer's transaction.
9. Workflow transition/cancel notifications to the instance starter are atomic with the Workflow write and Audit event, and self-actions should not create redundant self-notifications.
10. BFF mutation routes must use the existing centralized CSRF/authenticated proxy and dynamic IDs must be encoded.

## Files to inspect first
- `backend/app/core/notifications/models.py`
- `backend/app/core/notifications/service.py`
- `backend/app/core/notifications/events.py`
- `backend/app/api/v1/routes/notifications.py`
- `backend/app/core/workflow/service.py`
- `backend/alembic/versions/20260911_0014_notifications_core.py`
- `backend/tests/test_notifications_api.py`
- `backend/tests/test_workflow_api.py`
- `frontend/components/core/NotificationManagementView.tsx`
- `frontend/components/app/AppShell.tsx`
- `frontend/app/api/core/notifications/**`
- `docs/phase-c2-notifications-core.md`

## Deliberate choices to challenge
- Inactive users may accumulate durable notifications, but cannot authenticate to read them until reactivated. This prevents notification side effects from blocking domain transactions merely because the original recipient was later disabled.
- `organization_id` is context/filter metadata, not the authorization boundary for a personal notification.
- Notification title/body should be non-sensitive summaries; this is a producer contract because persistent notifications can outlive later resource-access revocation.
- External channels (email/SMS/push), templates, delivery queues, and retry workers are intentionally out of scope for C2.

Please report any blocker, privilege/privacy leak, transaction-coupling issue, open-redirect issue, immutability bypass, or cross-user IDOR.
