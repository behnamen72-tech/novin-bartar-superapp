# Phase B4 — Audit

Status: Ready for Claude Review

## Goal
Create an immutable, organization-scoped audit trail before enabling real write
operations in Core or Business Modules.

## Audit record
Each event may contain:
- actor User UUID
- actor identifier snapshot
- Organization scope
- action
- resource type
- resource ID
- state before
- state after
- metadata
- source
- request/correlation ID
- timestamp

## Transaction rule
Future business writes must call `record_audit_event(...)` using the SAME
SQLAlchemy Session/transaction as the business mutation.

This ensures the business change and its audit record commit or roll back together.

## Sensitive data
Audit payloads recursively redact keys containing:
- password
- secret
- token
- authorization
- cookie
- api_key
- jwt

Passwords, password hashes, JWTs, cookies, and secrets must never be persisted in
audit payloads.

## Immutability
Two layers are implemented:
1. SQLAlchemy `before_flush` rejects UPDATE/DELETE of persisted AuditEvent objects.
2. PostgreSQL trigger rejects UPDATE/DELETE directly at the database level.

There is no audit update/delete API.

## Authorization
New permission:
`audit.read`

Audit listing is filtered server-side by:
- audit.read
- Organization Scope

Global/null-organization audit events are not exposed by the current Core audit API.

## API
`GET /api/v1/audit`

Optional:
- organization_id
- limit
- offset

Explicit out-of-scope organization requests return 403.

## Demo UI
Users with `audit.read` see a new sidebar item:
`تاریخچه`

The limited viewer demo user intentionally does not receive audit.read.

## Demo seed
The development seed creates one idempotent demonstration audit event.
Its metadata intentionally contains a fake password field to prove redaction.
