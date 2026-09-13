# Phase C2 — Notifications Core

## Goal
Provide a reusable in-app notification foundation that Core and future business modules can call without exposing a public arbitrary-send API.

## Security and ownership model
- Notifications are recipient-owned, not organization-permission-owned.
- Every public notification API is authenticated and operates only on `current_user.id`.
- A user without any B3 organization role can still read their own notifications.
- Direct access to another user's notification returns `404`.
- `organization_id` is contextual metadata for filtering and traceability; it does not grant access to other users' notifications.
- Notification destinations use app-local `action_path` values only. External URLs, scheme URLs, backslash-based redirect forms, and control characters are rejected.
- Following an action never transfers authorization. The destination Core/business endpoint re-runs its own authorization checks.
- Notification producers must keep title/body as non-sensitive summaries; protected resource data remains behind the target module's authorization boundary.

## Persistence model
`Notification` stores:
- recipient user
- optional organization context
- `event_code` and `source`
- severity (`info`, `success`, `warning`, `critical`)
- title/body
- optional generic `resource_type` + `resource_id`
- optional app-local action path
- optional per-recipient dedupe key
- immutable creation timestamp
- mutable `read_at`

Notification content/ownership are immutable after creation. Physical delete is forbidden. Only `read_at` may change.

This invariant is enforced twice:
1. SQLAlchemy ORM listeners for application/test paths.
2. PostgreSQL trigger `trg_notifications_protected` for database-level protection.

## Producer contract
`create_notification(...)` is an internal service, not a public REST endpoint.

Important behavior:
- it flushes but does **not** commit;
- the calling domain operation owns the transaction;
- domain write + notification can therefore commit atomically;
- optional `dedupe_key` prevents duplicate durable notifications for a recipient under normal retries, while a database unique constraint remains the final integrity guard;
- inactive recipients may still receive durable notification history, but cannot read it while authentication is disabled.

## Public API
- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `GET /api/v1/notifications/{notification_id}`
- `POST /api/v1/notifications/{notification_id}/read`
- `POST /api/v1/notifications/{notification_id}/unread`
- `POST /api/v1/notifications/read-all`

List filters:
- unread only
- organization context
- event code
- bounded limit/offset pagination

There is deliberately no public endpoint that lets a browser/user manufacture arbitrary notifications.

## Workflow integration
C2 proves cross-Core usage without adding an event bus:
- if one user advances another user's workflow instance, the instance starter receives an in-app notification;
- if one user cancels another user's active workflow instance, the starter receives a warning notification;
- self-actions do not create redundant self-notifications;
- Workflow Audit + Workflow write + Notification creation occur in the same database transaction.

## Operational UI
The authenticated frontend now includes:
- always-available personal `اعلان‌ها` navigation
- topbar notification bell with unread badge
- unread-count refresh on login, visibility return, and a bounded 60-second foreground refresh
- list/all-vs-unread view
- mark read / mark unread
- mark all read
- app-local action button
- severity/source presentation
- loading, empty, and error states

Unsafe mutations continue through the centralized Next.js authenticated BFF/CSRF guard. Dynamic notification IDs are URL-encoded.

## Demo behavior
`seed_demo.py` creates idempotent sample notifications for the demo administrator so the C2 UI is visible immediately after reseeding.

## Migration
`20260911_0014_notifications_core.py`

## Deliberate boundary
C2 is **in-app notification core only**. Email, SMS, push providers, templates, delivery retries, and scheduled campaigns remain outside this checkpoint and can be added later behind a channel/provider abstraction without changing recipient ownership semantics.
