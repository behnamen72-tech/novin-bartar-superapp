# B5.2 Review Response — Revision 2

## Review findings addressed

### 1. Blocking packaging defect — FIXED
The complete `backend/app/core/documents/storage/` package is now included:
- `__init__.py`
- `interface.py`
- `local.py`

The storage contract was also aligned with the B5.2 service behavior:
- `provider_name`
- provider-relative object keys
- `save()`
- `read()`
- `discard_uncommitted()`

`LocalStorageProvider` now returns/stores canonical provider-relative POSIX-style keys rather than host-specific absolute paths.

Cross-platform path hardening was added for Windows and POSIX path dialects. Windows-style traversal and absolute-drive paths are explicitly rejected.

### 2. Concurrent version-number allocation — FIXED
`create_document_version()` now acquires a row-level `SELECT ... FOR UPDATE` lock on the target `documents` row before calculating `MAX(version_number) + 1`.

This serializes version-number allocation per document on PostgreSQL and prevents two concurrent uploads from both choosing the same next version number.

Authorization is re-checked against the locked document row to avoid a future TOCTOU gap if document ownership/scope becomes mutable.

### 3. PostgreSQL migration 0006 live-data execution — NOT CLAIMED
Offline PostgreSQL SQL generation through revision `20260909_0006` passes. A live PostgreSQL instance is not available in this review runtime, so the fail-closed data migration behavior has not been falsely reported as live-executed.

Risk remains low because B5.1 did not expose the upload API. A live migration smoke test remains a deployment/pre-production check.

## Verification after fixes
- `pytest`: **42 passed**
- `compileall`: **passed**
- Alembic PostgreSQL offline SQL generation through `0006`: **passed**
- `ruff`: not installed in this runtime
- `mypy`: not installed in this runtime

## Packaging verification
The final Revision 2 ZIP is extracted into a fresh directory and the test suite is run from that extracted ZIP tree. This specifically verifies that required modules are present in the delivered archive rather than only in the working tree.

## Requested review focus
Please verify:
1. the storage subpackage is now actually present in the ZIP;
2. provider-relative key behavior and Windows/POSIX path traversal checks;
3. PostgreSQL row-lock approach for version-number concurrency;
4. no regression in B3 organization-scope authorization or B4 audit semantics;
5. whether any issue still blocks B5.2 merge.
