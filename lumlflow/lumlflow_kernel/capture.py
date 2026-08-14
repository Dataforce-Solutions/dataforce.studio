from __future__ import annotations

import hashlib
import json
import os
import selectors
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import TextIO

from .fs import replace_with_retry

LogEvent = dict[str, int | str]


class FDCapture:
    def __init__(
        self,
        run_id: str,
        emit: Callable[[str, dict[str, object]], None],
        logs_root: Path,
        *,
        limit_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self.run_id = run_id
        self.emit = emit
        self.logs_root = logs_root
        self.limit_bytes = limit_bytes
        self.events: list[LogEvent] = []
        self.truncated = False
        self._saved_fds: dict[int, int] = {}
        self._read_fds: dict[int, str] = {}
        self._thread: threading.Thread | None = None
        self._saved_streams: tuple[TextIO, TextIO] | None = None
        self._capture_streams: tuple[TextIO, TextIO] | None = None
        self._sequence = 0
        self._stored_bytes = 0

    def __enter__(self) -> FDCapture:
        for descriptor, stream in ((1, "stdout"), (2, "stderr")):
            read_fd, write_fd = os.pipe()
            self._saved_fds[descriptor] = os.dup(descriptor)
            os.dup2(write_fd, descriptor)
            os.close(write_fd)
            self._read_fds[read_fd] = stream
        self._saved_streams = (sys.stdout, sys.stderr)
        self._capture_streams = (
            os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8"),
            os.fdopen(os.dup(2), "w", buffering=1, encoding="utf-8"),
        )
        sys.stdout, sys.stderr = self._capture_streams
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._flush_python_streams()
        if self._saved_streams is not None:
            sys.stdout, sys.stderr = self._saved_streams
        if self._capture_streams is not None:
            for stream in self._capture_streams:
                stream.close()
        for descriptor, saved in self._saved_fds.items():
            os.dup2(saved, descriptor)
            os.close(saved)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def persist(self) -> tuple[str, int]:
        encoded = b"".join(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
            + b"\n"
            for event in self.events
        )
        digest = hashlib.sha256(encoded).hexdigest()
        destination = self.logs_root / digest[:2] / digest
        _atomic_write(destination, encoded)
        return digest, len(encoded)

    def record(self, stream: str, data: bytes) -> None:
        self._record(stream, data)

    def _drain(self) -> None:
        selector = selectors.DefaultSelector()
        for descriptor, stream in self._read_fds.items():
            selector.register(descriptor, selectors.EVENT_READ, stream)
        try:
            while selector.get_map():
                for key, _ in selector.select():
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fd)
                        os.close(key.fd)
                        continue
                    self._record(str(key.data), data)
        finally:
            selector.close()

    def _record(self, stream: str, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        event: LogEvent = {
            "run_id": self.run_id,
            "stream": stream,
            "seq": self._sequence,
            "bytes": text,
        }
        self._sequence += 1
        self.emit("log", dict(event))
        if self._stored_bytes >= self.limit_bytes:
            self.truncated = True
            return
        remaining = self.limit_bytes - self._stored_bytes
        encoded_size = self._encoded_size(event)
        if encoded_size > remaining:
            event["bytes"] = self._fit_text(text, event, remaining)
            self.truncated = True
            encoded_size = self._encoded_size(event)
        if encoded_size > remaining:
            return
        self.events.append(event)
        self._stored_bytes += encoded_size

    @staticmethod
    def _encoded_size(event: LogEvent) -> int:
        return len(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
            + b"\n"
        )

    @classmethod
    def _fit_text(cls, text: str, event: LogEvent, limit: int) -> str:
        low = 0
        high = len(text)
        while low < high:
            midpoint = (low + high + 1) // 2
            candidate = dict(event)
            candidate["bytes"] = text[:midpoint]
            if cls._encoded_size(candidate) <= limit:
                low = midpoint
            else:
                high = midpoint - 1
        return text[:low]

    @staticmethod
    def _flush_python_streams() -> None:
        sys.stdout.flush()
        sys.stderr.flush()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
