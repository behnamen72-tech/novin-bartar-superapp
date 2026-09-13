# Phase B6.6 — People & User Management UI

B6.6 turns the existing read-only People and Users views into operational Core
management screens on top of the B5.6 write APIs.

## People operations

- create Person with an initial organization relationship
- edit shared Person fields (name/contact data)
- activate/deactivate Person
- add an organization relationship
- activate/deactivate an existing relationship
- search/filter the currently authorized result set

The UI treats Person fields as global/shared fields. It only renders global edit
controls when the visible relationship scope appears manageable, but this is UX
only. The backend remains authoritative and requires `people.manage` across every
active organization relationship that can be affected.

Relationship status is authorized against the one relationship organization.
The backend also prevents deactivating a relationship while active user-access
assignments are rooted at that organization.

## User operations

- create one User account for an eligible active Person
- edit email / optional username
- activate/deactivate User
- administrator password reset
- search/filter the currently authorized result set

User writes reuse the B5.6 `users.manage` service rules and the anti-privilege-
escalation dominance checks. The UI deliberately disables self-deactivation of
the currently signed-in account, matching the backend rule.

Passwords are transient browser form state only. They are sent through the
same-origin authenticated BFF, are never returned by the API, and the backend
Audit event records only password-change metadata rather than password/hash.

## BFF routes

People:
- GET/POST `/api/core/people`
- GET/PATCH `/api/core/people/{personId}`
- PATCH `/api/core/people/{personId}/status`
- POST `/api/core/people/{personId}/relationships`
- PATCH `/api/core/people/{personId}/relationships/{relationshipId}/status`

Users:
- GET/POST `/api/core/users`
- GET/PATCH `/api/core/users/{userId}`
- PATCH `/api/core/users/{userId}/status`
- POST `/api/core/users/{userId}/password-reset`

Every unsafe BFF method uses `proxyAuthenticatedRequest()`, so the centralized
B6.2 CSRF/origin guard and HttpOnly session-cookie design remain unchanged.

## Intentional limitation

The management UI uses the already-authorized Organization and People datasets
to calculate whether a control should be displayed. If a custom role has
`people.manage`/`users.manage` but intentionally lacks the corresponding read
permissions needed to enumerate selector data, the UI stays conservative and
may hide a creation/edit affordance. The backend capability still exists and
continues to enforce the write permission independently. A future reusable
permission-scoped selector API can remove this UX coupling if such role designs
become a real requirement.
