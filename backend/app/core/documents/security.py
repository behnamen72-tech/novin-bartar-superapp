import mimetypes
from pathlib import PurePosixPath


ALLOWED_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
)

ALLOWED_MIME_BY_EXTENSION: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
    ".xlsx": frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ),
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
}


class DocumentUploadValidationError(ValueError):
    pass


def validate_original_filename(filename: str | None) -> tuple[str, str]:
    if filename is None:
        raise DocumentUploadValidationError("Uploaded file must have a filename.")

    normalized = filename.strip()
    if not normalized or "\x00" in normalized or "\r" in normalized or "\n" in normalized:
        raise DocumentUploadValidationError("Invalid filename.")

    cross_platform = normalized.replace("\\", "/")
    basename = PurePosixPath(cross_platform).name
    if basename != cross_platform or basename in {".", ".."}:
        raise DocumentUploadValidationError("Filename must not contain a path.")

    if len(basename) > 300:
        raise DocumentUploadValidationError("Filename is too long.")

    extension = PurePosixPath(basename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise DocumentUploadValidationError("File extension is not allowed.")

    return basename, extension


def validate_upload_content(
    *,
    filename: str | None,
    declared_content_type: str | None,
    content: bytes,
    max_size_bytes: int,
) -> tuple[str, str, str]:
    safe_filename, extension = validate_original_filename(filename)

    if not content:
        raise DocumentUploadValidationError("Uploaded file is empty.")
    if len(content) > max_size_bytes:
        raise DocumentUploadValidationError("Uploaded file exceeds the maximum size.")

    allowed_mimes = ALLOWED_MIME_BY_EXTENSION[extension]
    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    inferred = (mimetypes.guess_type(safe_filename)[0] or "application/octet-stream").lower()

    if declared and declared != "application/octet-stream" and declared not in allowed_mimes:
        raise DocumentUploadValidationError(
            "Declared content type does not match the allowed file type."
        )

    mime_type = declared if declared in allowed_mimes else inferred
    if mime_type not in allowed_mimes:
        mime_type = next(iter(allowed_mimes))

    return safe_filename, extension, mime_type
