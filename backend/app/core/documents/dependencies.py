from app.core.config import settings
from app.core.documents.storage.interface import StorageProvider
from app.core.documents.storage.local import LocalStorageProvider


def get_document_storage() -> StorageProvider:
    # B5.2 uses local storage in development. The API/service depend only on the
    # StorageProvider contract, so MinIO/S3 can replace this binding later.
    return LocalStorageProvider(settings.documents_storage_root)
