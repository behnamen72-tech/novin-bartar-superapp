# Claude Review Request — B6.7 + B6.8 Cumulative UI Checkpoint

Please review the actual cumulative code, using the Claude-approved B6.6 baseline.
B6.7 makes the Documents platform operational in the UI; B6.8 opens the sensitive
Access / Roles / Permissions administration UI and document-ACL recovery surface.

## Review B6.7 first

Primary files:

- `frontend/components/core/DocumentManagementView.tsx`
- `frontend/lib/document-management.ts`
- `frontend/lib/api-client.ts`
- `frontend/lib/authenticated-backend.ts`
- `frontend/app/api/core/documents/**/route.ts`
- `frontend/app/api/core/document-categories/**/route.ts`
- `frontend/app/api/core/document-retention-policies/**/route.ts`
- `docs/phase-b6.7-documents-ui.md`

Confirm:

1. all document writes still traverse the centralized authenticated/CSRF-protected BFF;
2. dynamic identifiers cannot alter backend paths;
3. binary download does not expose bearer credentials and preserves no-store/nosniff behavior;
4. frontend scope/permission checks remain UX-only;
5. B5.4 ACL remains restrictive-only and cannot create cross-organization access;
6. archive/restore/version/link/category/retention/timeline UI matches B5 lifecycle semantics;
7. no IDOR or document-existence disclosure is introduced in the browser/BFF layer.

## Review B6.8 as the higher-risk boundary

Primary files:

- `frontend/components/core/AccessManagementView.tsx`
- `frontend/lib/people-user-management.ts`
- `frontend/app/api/core/access/**/route.ts`
- `frontend/app/api/core/documents/[documentId]/permissions/**/route.ts`
- `backend/app/core/access/service.py`
- `backend/app/api/v1/routes/access.py`
- `backend/app/core/documents/service.py` (document ACL authorization/recovery path)
- `docs/phase-b6.8-access-management-ui.md`

Please confirm specifically:

1. B6.8 does **not** introduce numeric role levels or a second privilege model;
2. FastAPI B5.6 capability-set delegation remains the sole anti-escalation authority;
3. system/legacy-global roles cannot be mutated through runtime UI/API;
4. custom organization-owned roles cannot be used outside their valid subtree;
5. Role Assignment creation cannot be used for cross-company privilege escalation;
6. disabling roles/assignments or removing permissions cannot bypass the last-effective-`access.manage` protection;
7. frontend selectors may fail closed but can never expand authority;
8. document ACL break-glass with `access.manage` allows ACL administration only and does not reveal metadata/file/download content;
9. ACL first-manager / last-manager invariants are still enforced server-side;
10. no CSRF/session/IDOR regression is introduced by the new BFF routes.

## Verification already executed

- backend pytest: **103 passed**
- backend compileall: **passed**
- OpenAPI: **48 paths**
- PostgreSQL Alembic offline SQL through 0012: **passed**
- B6.3: **12 assertions**
- B6.4: **11 assertions**
- B6.5: **18 assertions**
- B6.6: **37 assertions**
- B6.7: **40 assertions**
- B6.8: **36 assertions**
- TS/TSX syntax parse: **77 files / 0 diagnostics**

A dependency-installed `next build`, ESLint run, and full React/Next `tsc --noEmit`
are not claimed in this isolated runtime because npm dependencies are not installed.

Please classify findings as **BLOCKER / SHOULD-FIX / NON-BLOCKING** and state whether
B6.7+B6.8 are approved as the next cumulative UI checkpoint.
