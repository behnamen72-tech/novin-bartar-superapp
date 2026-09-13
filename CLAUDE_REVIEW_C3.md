# Claude Review Request — C3 Search Core

Please review C3 against the Claude-approved C2 baseline, focusing on Search as a potential
authorization side channel.

## Expected security properties

1. Search must not introduce a standalone privilege that bypasses domain permissions.
2. Organization results require canonical `organization.read` scope.
3. Person matching must be restricted by authorized organization relationships in SQL before `LIMIT`; it must not enumerate unrelated People in Python and then filter.
4. Document results must preserve B5.4 restrictive ACL semantics exactly; a matching restricted document must remain invisible without the matching role ACL.
5. Cross-company matches must not affect visible result IDs or counts.
6. Search must be authenticated and exposed through the existing BFF authenticated GET proxy.
7. `q`, entity filters, and per-type limits must be bounded/validated.
8. Search is read-only and should not create Audit/Notification side effects.
9. Search should call domain-owned services/providers rather than reimplementing their authorization rules centrally where practical.
10. UI navigation/filters are convenience only; backend checks remain authoritative.

## Files to inspect first

- `backend/app/core/search/schemas.py`
- `backend/app/core/search/service.py`
- `backend/app/api/v1/routes/search.py`
- `backend/app/core/organization/service.py` (`search_organizations_for_user`)
- `backend/app/core/people/service.py` (`search_people_for_user`)
- `backend/app/core/documents/service.py` (`list_documents` and ACL condition)
- `backend/tests/test_search_api.py`
- `frontend/components/core/SearchManagementView.tsx`
- `frontend/app/api/core/search/route.ts`
- `frontend/lib/navigation.ts`
- `docs/phase-c3-search-core.md`

## Deliberate design choices to challenge

- No `search.read` permission: visibility derives only from underlying domain read permissions.
- Initial providers are Organization, Person, and Document only.
- Result counts are only the bounded returned authorized rows, not global totals.
- Search returns safe metadata and no document-body/file-content snippets.
- PostgreSQL FTS/pg_trgm or external search infrastructure is deferred until scale warrants it.

Please report any blocker, cross-tenant leak, Document ACL bypass, result-count side channel,
unauthorized People enumeration, or unsafe BFF behavior.
