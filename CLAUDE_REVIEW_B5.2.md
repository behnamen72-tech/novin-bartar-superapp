# Claude Review — Phase B5.2 Documents API

## Project constraints
- Modular Monolith first.
- Accounting is outside this project.
- Reuse B3 Authorization and B4 Audit.
- Do not introduce microservices/event bus/CQRS without demonstrated need.

## Base
B5.1 Documents Core foundation with the approved LocalStorage path-traversal hardening,
foreign-key behavior, and indexes.

## Implemented in B5.2

### API
- GET `/api/v1/documents`
- POST `/api/v1/documents`
- GET `/api/v1/documents/{id}`
- POST `/api/v1/documents/{id}/versions`
- GET `/api/v1/documents/{id}/download`

### Authorization
- documents.read → list/detail/download
- documents.manage → create/upload version
- Organization Scope is checked server-side using the existing B3 engine.
- Lists are DB-filtered to authorized organization IDs.

### Upload model
Method A is implemented:
Client → FastAPI → authorization → StorageProvider.
No public storage URL is returned.

### Storage hardening
- StorageProvider remains abstract.
- Local provider returns/stores provider-relative keys instead of absolute filesystem paths.
- Path traversal and absolute paths remain blocked.
- New `discard_uncommitted()` is strictly transaction compensation, not a user deletion API.

### File validation
- Max size defaults to 50 MiB and is config-driven.
- Initial extension allowlist: pdf, docx, xlsx, png, jpg/jpeg.
- Path-like filenames, NUL/CR/LF, disallowed extensions, and declared MIME mismatch are rejected.
- Internal object keys are generated server-side.

### Versioning
- Existing versions are retained.
- Next version number is stored with a DB unique constraint `(document_id, version_number)`.
- B5.2 adds `DocumentVersion.created_by` for provenance.

### File integrity
- SHA-256 and byte size stored in StorageObject.
- Download verifies size + checksum.

### Audit
- `document.created`
- `document.version.created`
- `document.downloaded`

Per user-approved policy, every successful download is audited and the audit commit occurs
before file bytes are returned.

### Migration correction
B5.1 migration now explicitly seeds:
- documents.read
- documents.manage

B5.2 migration `0006` adds DocumentVersion.created_by.
It deliberately fails closed if experimental pre-existing document_versions lack an actor,
rather than inventing attribution.

## Deliberately not implemented in B5.2
- DocumentPermission enforcement / person-specific sharing
- DocumentLink public APIs
- archive endpoint
- antivirus scanning
- MinIO/S3 implementation
- direct-to-storage upload
- large-file range streaming

## Requested review areas
1. IDOR / cross-company isolation.
2. Authorization consistency with B3.
3. Upload validation weaknesses/bypasses.
4. Storage abstraction and path safety.
5. Transaction compensation and orphan-file risk.
6. Audit-before-download semantics.
7. Migration safety, especially 0005 permission seed and 0006 actor attribution.
8. Concurrency risk around next version number.
9. File integrity validation.
10. Whether any deferred item is actually blocking for merge.

## Acceptance tests
The package includes API tests for:
- authorized create/list
- cross-company filtering
- missing manage permission
- two-version preservation
- version creator attribution
- version Audit events
- successful download + download Audit
- cross-company download denial
- path-like filename rejection
- executable extension rejection
- LocalStorage traversal blocking and provider-relative keys

Status: Ready for independent review after the reported test run.
