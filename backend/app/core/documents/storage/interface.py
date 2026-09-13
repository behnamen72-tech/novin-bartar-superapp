from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Private object-storage contract used by the Documents core.

    Object paths crossing this boundary are provider-relative keys. Providers
    must never return public URLs or host-specific absolute filesystem paths.
    """

    provider_name: str

    @abstractmethod
    def save(self, path: str, content: bytes) -> str:
        """Persist bytes and return the canonical provider-relative object key."""
        raise NotImplementedError

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read bytes for a provider-relative object key."""
        raise NotImplementedError

    @abstractmethod
    def discard_uncommitted(self, path: str) -> None:
        """Remove only an uncommitted object after a failed DB transaction."""
        raise NotImplementedError
