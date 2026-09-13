# Phase C3 — Search Core

C3 introduces a permission-aware federated search foundation for Core entities.
The first providers are Organization, People, and Documents. Future business modules
can participate through domain-owned provider functions without giving Search direct
ownership of their authorization rules.

## Authorization model

Search does **not** add a standalone `search.read` permission. A result is visible only
when the current user already has the canonical read permission for that domain:

- Organization → `organization.read`
- Person → `people.read`
- Document → `documents.read` plus the existing restrictive document ACL

The backend remains the security boundary. Search cannot broaden organization scope or
Document ACL access. The browser receives only rows returned by those canonical checks.

## API

`GET /api/v1/search`

Parameters:
- `q`: 2–100 characters after validation; whitespace is normalized
- `entity_type`: optional repeatable filter (`organization`, `person`, `document`)
- `limit_per_type`: 1–20, default 8

The response contains a unified list with safe navigation metadata and per-type counts.
Counts are counts of returned authorized results, not global totals.

## Provider behavior

### Organization
The provider computes authorized organization IDs using the approved B3 permission engine,
then applies name/code matching and the result limit in SQL.

### People
The provider first restricts rows in SQL to People having a relationship with an authorized
organization, then applies matching and limiting. Returned relationships are filtered again
to the user's visible organization IDs.

### Documents
Search reuses `list_documents`, preserving both B3 organization scope and B5.4 document ACL
semantics. Restricted documents therefore stay invisible even when their title matches.

## UI

C3 adds:
- an always-available Search entry in the authenticated shell;
- a topbar Search shortcut;
- a Persian RTL Search workspace;
- type filters and per-domain result counts;
- navigation back to the owning Core workspace.

Frontend visibility is UX only. The `/api/core/search` BFF route forwards to the authenticated
FastAPI endpoint and never performs authorization itself.

## Deliberate scope

C3 is a Search Foundation, not a search engine cluster. It intentionally does not add:
- Elasticsearch/OpenSearch;
- PostgreSQL full-text/trigram indexes;
- fuzzy ranking or cross-domain relevance scores;
- content extraction/OCR for document files;
- global User/Access/Audit searching.

Those can be added later when data volume and business needs justify them. Current matching
uses database `LIKE`/normalized text against a small, bounded set of safe metadata fields.
No database migration is required for C3.
