import os
import re
import tempfile
import time
from pathlib import Path
from typing import Literal

from lumlflow.flow.hashing import sha256_bytes

CASArea = Literal["objects", "values", "previews", "logs"]
_AREAS: tuple[CASArea, ...] = ("objects", "values", "previews", "logs")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if os.name != "nt" and attempt == 4:
                raise
            if attempt == 4:
                raise
            time.sleep(0.01 * (2**attempt))


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        _replace_with_retry(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


class ContentAddressedStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        for area in _AREAS:
            (root / area).mkdir(parents=True, exist_ok=True)

    def path_for(self, area: CASArea, content_hash: str) -> Path:
        if area not in _AREAS:
            raise ValueError(f"unknown CAS area: {area}")
        if not _HASH_PATTERN.fullmatch(content_hash):
            raise ValueError("content hash must be a lowercase sha256 digest")
        suffix = ".json" if area == "previews" else ""
        return self.root / area / content_hash[:2] / f"{content_hash}{suffix}"

    def put(self, area: CASArea, data: bytes | str) -> str:
        encoded = data.encode() if isinstance(data, str) else data
        content_hash = sha256_bytes(encoded)
        destination = self.path_for(area, content_hash)
        if not destination.exists():
            atomic_write(destination, encoded)
        return content_hash

    def get(self, area: CASArea, content_hash: str) -> bytes:
        return self.path_for(area, content_hash).read_bytes()

    def contains(self, area: CASArea, content_hash: str) -> bool:
        return self.path_for(area, content_hash).is_file()
