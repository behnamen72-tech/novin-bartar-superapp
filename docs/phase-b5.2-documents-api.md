# Phase B5.2 — Documents API + Authorization + Upload Flow

Status: Ready for Claude Review

## Scope
This phase turns the B5.1 Documents Core foundation into a usable, secure API.

## Locked decisions implemented
- Upload Method A: Client → FastAPI → Storage Provider.
- No public file URL.
- Backend authorizes every list/read/upload/download operation.
- B3 Authorization and Organization Scope are reused; no parallel ACL engine.
- B4 Audit is reused.
- Every successful download records `document.downloaded` before bytes are returned.
- Local filesystem is the development provider behind `StorageProvider`.

## API
- `GET /api/v1/documents`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `POST /api/v1/documents/{document_id}/versions`
- `GET /api/v1/documents/{document_id}/download`

## Authorization
- `documents.read`: list, detail, download.
- `documents.manage`: create document, upload new version.
- Explicit organization filters outside scope return 403.
- Direct document access outside scope returns 403.
- List queries fetch only documents from authorized organizations.

## Upload security
Initial allowlist:
- PDF
- DOCX
- XLSX
- PNG
- JPG/JPEG

Default maximum file size: 50 MiB (configuration-driven).

The client never supplies a storage path. The service generates an internal object key.
Filename paths, traversal, null bytes, CR/LF header injection, disallowed extensions, and
mismatched declared MIME types are rejected.

This phase does not claim malware scanning or cryptographic file-type identification.
Those are future production hardening items.

## Storage abstraction
B5.2 tightens the storage contract:
- DB stores provider-relative object keys, not machine-specific absolute filesystem paths.
- `discard_uncommitted()` exists only to compensate a failed DB transaction after a new
  object was written. It is not a business deletion operation.
- Committed document versions remain physically retained.

## Transaction behavior
- Document creation and its Audit event commit in one DB transaction.
- Version metadata and its Audit event commit together.
- If a version DB transaction fails after writing the new file, the uncommitted file is discarded.
- Download Audit commits before the API returns file bytes.

## Integrity
Each uploaded StorageObject records:
- SHA-256 checksum
- size
- provider-relative key

Download validates size and checksum before returning bytes.

## B5.2 model correction
`DocumentVersion.created_by` is added so version provenance exists in domain data, not only Audit.
Migration `20260909_0006` adds this column with a fail-closed remediation guard for pre-existing
experimental rows.

## Deliberately deferred
- DocumentLink APIs for Person/Customer/Supplier/Contract/Task.
- DocumentPermission enforcement / individual sharing semantics.
- Archive endpoint.
- Antivirus/malware scanning.
- MinIO/S3 provider.
- Direct-to-object-storage upload URLs.
- Range requests/streaming from provider for very large files.

These are deferred rather than hidden inside B5.2.
