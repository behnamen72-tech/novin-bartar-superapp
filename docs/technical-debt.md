# Technical Debt / Deferred Optimizations

## Authorization organization batching
Current authorized-organization discovery iterates organizations and calls
`has_permission` per organization.

This is correct and safe for the current small organization count, but it may
become inefficient as the holding grows.

Future optimization trigger:
- materially larger Organization tree
- authorization query latency becomes measurable
- profiling confirms this path is a bottleneck

Preferred future direction:
- batch-load current assignments and permissions once
- calculate allowed descendant organization IDs in one traversal/query
- avoid changing authorization semantics

This is intentionally deferred rather than introducing premature complexity.

## Document link target registry
B5.3 deliberately allows only `organization` and `person` links because those
Core entities already have defined organization-boundary rules.

When Customer, Supplier, Contract, Task, or Operation modules are implemented,
each new link type must add an explicit target resolver/validator rather than
allowing arbitrary `entity_type` strings. This prevents dangling links and
cross-organization associations.

## Document ACL subject expansion
B5.4 activates role-based `DocumentPermission` ACLs as a restrictive layer on
top of B3 Role + Permission + Organization Scope. Direct per-user grants,
group/team subjects, time-limited grants, and external/public sharing remain
deferred until a concrete business requirement exists.

`access.manage` is the scoped break-glass path for ACL administration only; it
does not grant document content access.

## Document disabled state
`DocumentStatus.DISABLED` remains reserved and has no public transition in B5.3.
Before exposing it, define whether disabled documents are visible to managers,
downloadable, restorable, or subject to retention/legal-hold rules.


## Local document streaming
B5.2/B5.5 currently cap uploads and downloads at the configured document size
limit and `LocalStorageProvider.read()` returns the committed object as bytes.
This is safe at the current 50 MiB default but is not memory-optimal for future
large-file support.

Future optimization trigger:
- document size limits are materially increased
- concurrent large downloads become common
- profiling shows memory pressure in the API workers

Preferred future direction:
- add a streaming/open interface to `StorageProvider`
- use chunked/streaming backend responses
- add range request support only when a concrete large-file use case requires it

This is a performance optimization, not a current security blocker.

## Document search indexing
B5.5 intentionally implements a bounded metadata search foundation using normal
SQL filters/ILIKE across title, type, and description. It is not the global Search
Core and does not introduce PostgreSQL full-text or trigram indexes yet.

Future optimization trigger:
- document counts/search latency become material
- profiling confirms metadata search is a bottleneck

Preferred future direction:
- PostgreSQL full-text or trigram indexes for Documents
- later integration with the dedicated Search Core


## Core people/user list SQL filtering and pagination
`list_people_for_user` and `list_users_for_user` currently load broader ORM result
sets and perform the final organization visibility reduction in Python. The
response is correctly scope-filtered, so this is not a current data-leak issue,
but it will not scale efficiently to large people/user populations.

Future direction:
- constrain candidate rows by authorized organization IDs at SQL level
- add bounded `limit`/`offset` (or cursor pagination) to People and Users APIs
- preserve the same B3 authorization semantics while optimizing queries

## Audit sensitive-field policy expansion
`sanitize_audit_payload` currently redacts security-secret key names such as
password/token/secret/cookie/API-key fields. Future HR, finance/accounting, and
other sensitive modules must extend the centrally governed redaction/data
classification policy for fields such as national identifiers and bank/account
information before those payloads are audited.

## Authentication failed-login controls
Application-level account lockout / failed-login throttling is not implemented
yet. This is a security backlog item rather than a B5.6 blocker. Before public or
high-risk production exposure, combine application controls with edge/reverse-
proxy rate limiting and operational monitoring. Avoid designs that create easy
account-enumeration or denial-of-service paths.

## Document content-type verification
B5.x currently validates uploaded document types using the filename extension and
client-declared MIME type. Storage paths remain UUID-based and uploads are not
rendered inline, so this is not a B5.6 release blocker; however, production
hardening should add server-side content signature / magic-byte inspection.

Preferred future direction:
- detect the real file type from trusted server-side byte signatures
- compare detected type with the allowed extension/MIME combination
- reject mismatches before committing the document version
- keep detection policy centralized in the Documents upload pipeline

## Document malware scanning
B5.x does not yet perform antivirus/malware scanning on uploaded files. Before
multi-organization production use with broad document exchange, add a malware
scanning stage to the upload lifecycle.

Preferred future direction:
- quarantine newly uploaded objects until scanning succeeds
- use a replaceable scanner integration rather than coupling Core to one vendor
- fail closed on scanner-positive results
- define explicit operational behavior for scanner outage/timeouts
- audit scan outcome without recording sensitive file contents

## Document ACL list batching
`_document_acl_list_condition` can trigger repeated effective-role resolution per
organization while constructing document-list visibility conditions. Current
semantics are correct, but the query pattern can become inefficient as the
number of accessible organizations grows.

Future optimization trigger:
- materially larger organization trees
- document-list latency becomes measurable
- profiling confirms repeated authorization queries dominate request cost

Preferred future direction:
- batch-load effective role/permission data for all candidate organizations
- build the restrictive ACL predicate from the batched authorization context
- preserve the existing rule that document ACLs can only restrict B3 access,
  never expand it

## Authenticated session operations and cleanup
B6.2 adds server-side refresh-session records with rotating opaque refresh tokens and
an absolute session lifetime. The current product does not yet expose a security
settings screen/API to list active sessions, revoke all other sessions, or label
sessions by device. Expired/revoked rows also need an operational cleanup policy as
the installation ages.

Before broad production rollout:
- add bounded cleanup for expired/revoked `user_sessions`
- add "sign out other sessions" / account-session management when the settings UI exists
- avoid storing raw refresh tokens or full authentication request bodies in infrastructure logs

## Refresh-token replay family detection
B6.2 rotates the stored refresh-token hash under a row lock, so an old token becomes
invalid immediately after successful rotation. It does not retain a token-family
history for detecting a later replay and revoking every descendant token in that
family. Add family/reuse detection only if the production threat model requires that
stronger response; keep the current short access-token lifetime and rotation semantics.

## Dashboard aggregate counts
B6.4 intentionally derives Organization, People, and User dashboard totals from the
existing authorization-aware list APIs rather than adding a second counting path with
new security semantics. This is correct for the current data volume but causes more
payload/query work than a mature dashboard should require.

Future optimization trigger:
- people/user populations become materially larger
- dashboard load latency or payload size becomes measurable
- list endpoints gain pagination and therefore stop representing exact full totals

Preferred future direction:
- add a dedicated permission-aware dashboard aggregate service/API
- count only rows visible under the same B3 Organization Scope rules
- preserve document ACL semantics for any document metrics
- return bounded recent/attention lists separately from exact aggregate counters

## Permission-scoped management selectors
B6.6 intentionally builds create/edit selector choices from the already-authorized
Organization and People datasets. This keeps the phase on existing APIs and does
not weaken backend authorization, but a deliberately unusual custom role that has
`people.manage` or `users.manage` while lacking the corresponding read permissions
may not receive every convenient management affordance in the browser.

Future direction, if such roles become a real business requirement:
- expose a minimal reusable permission-scoped selector/capability endpoint
- return only entity identifiers/display labels needed for the requested write
- keep B3 authorization authoritative and avoid broadening read access merely to
  populate a form selector

## BFF document-download streaming
B6.7 routes authenticated document downloads through the same-origin Next.js BFF
and currently buffers the backend response before returning it to the browser.
The current 50 MiB document limit bounds the memory exposure, so this is not a B6.8
blocker, but production support for materially larger objects should stream the
response end-to-end rather than holding the complete file in BFF memory.

Preferred future direction:
- stream backend storage -> FastAPI -> BFF -> browser with backpressure
- preserve `Content-Disposition`, `Content-Type`, `Cache-Control: no-store`, and
  `X-Content-Type-Options: nosniff`
- keep access tokens server-side and preserve download Audit semantics


## Workflow capability discovery batching
C1 `GET /workflow/organizations` evaluates the three Workflow permissions for each active organization using the canonical B3 authorization policy. This preserves correct scope semantics but can become query-heavy in a very large organization tree.

Future optimization trigger:
- materially larger organization hierarchies
- Workflow center load latency becomes measurable
- profiling confirms repeated permission resolution dominates the request

Preferred direction:
- batch effective assignment/permission context for candidate organizations
- derive `can_read` / `can_manage` / `can_execute` from that batched context
- preserve exact B3 active-org, assignment-window, and descendant-scope semantics
