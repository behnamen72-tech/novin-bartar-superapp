from pathlib import Path, PurePosixPath, PureWindowsPath

from .interface import StorageProvider


class LocalStorageProvider(StorageProvider):
    provider_name = "local"

    def __init__(self, root: str = "storage/documents") -> None:
        self.root = Path(root).resolve()

    def _safe_target(self, path: str) -> tuple[str, Path]:
        if not path or "\x00" in path or "\\" in path:
            raise ValueError("Unsafe storage path.")

        posix_path = PurePosixPath(path)
        windows_path = PureWindowsPath(path)

        # Check both path dialects because development may run on Windows while
        # production runs on Linux. Provider keys are canonical POSIX-style paths.
        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError("Unsafe storage path.")

        key = posix_path.as_posix()
        if key in {"", "."}:
            raise ValueError("Unsafe storage path.")

        target = (self.root / Path(*posix_path.parts)).resolve()
        if self.root != target and self.root not in target.parents:
            raise ValueError("Storage path escapes root directory.")

        return key, target

    def save(self, path: str, content: bytes) -> str:
        key, target = self._safe_target(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def read(self, path: str) -> bytes:
        _, target = self._safe_target(path)
        return target.read_bytes()

    def discard_uncommitted(self, path: str) -> None:
        _, target = self._safe_target(path)
        try:
            target.unlink()
        except FileNotFoundError:
            return
